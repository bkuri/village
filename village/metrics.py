"""Metrics collection and export for Village."""

import logging
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from village.cleanup import find_stale_locks
from village.config import Config
from village.event_log import read_events
from village.queue import extract_ready_tasks
from village.status import collect_full_status

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Single metric value with labels."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricsReport:
    """Complete metrics report."""

    active_workers: int
    queue_length: int
    stale_locks: int
    orphans_count: int
    task_completion_rate: float
    average_task_duration_seconds: float
    collected_at: str


@dataclass
class PrometheusMetrics:
    """Prometheus-formatted metrics."""

    metrics: list[str]
    content_type: str = "text/plain; version=0.0.4; charset=utf-8"


@dataclass
class StatsDMetrics:
    """StatsD-formatted metrics."""

    metrics: list[str]


class MetricsCollector:
    """Collect and export Village metrics."""

    def __init__(self, config: Config, session_name: str | None = None) -> None:
        """
        Initialize metrics collector.

        Args:
            config: Village config
            session_name: Tmux session name (optional for reset mode)
        """
        self.config = config
        self.session_name = session_name or config.tmux_session
        self._lock = threading.Lock()

    def collect_metrics(self) -> MetricsReport:
        """
        Collect all Village metrics.

        Returns:
            MetricsReport with current metrics
        """
        if not self.session_name:
            raise RuntimeError("Session name required to collect metrics")

        with self._lock:
            full_status = collect_full_status(self.session_name)

            active_workers = sum(1 for w in full_status.workers if w.status == "ACTIVE")
            queue_length = len(extract_ready_tasks(self.config))
            stale_locks = len(find_stale_locks(self.session_name))
            orphans_count = len(full_status.orphans)

            task_completion_rate, avg_duration = self._compute_completion_metrics(self.config)

            report = MetricsReport(
                active_workers=active_workers,
                queue_length=queue_length,
                stale_locks=stale_locks,
                orphans_count=orphans_count,
                task_completion_rate=task_completion_rate,
                average_task_duration_seconds=avg_duration,
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.debug(f"Collected metrics: active={active_workers}, queue={queue_length}")
            return report

    def _compute_completion_metrics(self, config: Config) -> tuple[float, float]:
        """
        Compute task completion metrics from event log.

        Args:
            config: Config object

        Returns:
            Tuple of (completion_rate, avg_duration_seconds)
        """
        events = read_events(config.village_dir)

        completed_events = [e for e in events if e.cmd in ("resume", "queue")]

        if not completed_events:
            return 0.0, 0.0

        durations: list[float] = []
        for event in completed_events:
            if event.result == "ok":
                durations.append(1.0)

        if not durations:
            return 0.0, 0.0

        completion_rate = len([e for e in completed_events if e.result == "ok"]) / len(completed_events)

        return completion_rate, 0.0

    def export_prometheus(self) -> PrometheusMetrics:
        """
        Export metrics in Prometheus format.

        Returns:
            PrometheusMetrics with formatted output
        """
        report = self.collect_metrics()

        lines = []
        lines.append("# HELP village_active_workers Number of active workers")
        lines.append("# TYPE village_active_workers gauge")
        lines.append(f"village_active_workers {report.active_workers}")
        lines.append("")

        lines.append("# HELP village_queue_length Number of tasks in queue")
        lines.append("# TYPE village_queue_length gauge")
        lines.append(f"village_queue_length {report.queue_length}")
        lines.append("")

        lines.append("# HELP village_stale_locks Number of stale locks")
        lines.append("# TYPE village_stale_locks gauge")
        lines.append(f"village_stale_locks {report.stale_locks}")
        lines.append("")

        lines.append("# HELP village_orphans_count Number of orphaned resources")
        lines.append("# TYPE village_orphans_count gauge")
        lines.append(f"village_orphans_count {report.orphans_count}")
        lines.append("")

        lines.append("# HELP village_task_completion_rate Task completion rate")
        lines.append("# TYPE village_task_completion_rate gauge")
        lines.append(f"village_task_completion_rate {report.task_completion_rate}")
        lines.append("")

        lines.append("# HELP village_average_task_duration_seconds Average task duration")
        lines.append("# TYPE village_average_task_duration_seconds gauge")
        lines.append(f"village_average_task_duration_seconds {report.average_task_duration_seconds}")

        return PrometheusMetrics(metrics=lines)

    def export_statsd(self) -> StatsDMetrics:
        """
        Export metrics in StatsD format.

        Returns:
            StatsDMetrics with formatted output
        """
        report = self.collect_metrics()

        lines = []
        lines.append(f"village.active_workers:{report.active_workers}|g")
        lines.append(f"village.queue_length:{report.queue_length}|g")
        lines.append(f"village.stale_locks:{report.stale_locks}|g")
        lines.append(f"village.orphans_count:{report.orphans_count}|g")
        lines.append(f"village.task_completion_rate:{report.task_completion_rate}|g")
        lines.append(f"village.average_task_duration_seconds:{report.average_task_duration_seconds}|g")

        return StatsDMetrics(metrics=lines)

    def start_prometheus_server(self, host: str = "0.0.0.0", port: int | None = None) -> None:
        port = port or self.config.metrics.port
        collector = self

        class _PrometheusHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/metrics":
                    try:
                        prom = collector.export_prometheus()
                        body = "\n".join(prom.metrics).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", prom.content_type)
                        self.end_headers()
                        self.wfile.write(body)
                    except Exception as e:
                        logger.error(f"Error generating Prometheus metrics: {e}")
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = HTTPServer((host, port), _PrometheusHandler)
        self._prometheus_server: HTTPServer | None = server
        self._prometheus_thread = threading.Thread(
            target=server.serve_forever, name="prometheus-server", daemon=True
        )
        self._prometheus_thread.start()
        logger.info(f"Prometheus server started on {host}:{port}")

    def stop_prometheus_server(self) -> None:
        server = getattr(self, "_prometheus_server", None)
        if server is not None:
            server.shutdown()
            self._prometheus_server = None
            logger.info("Prometheus server stopped")

    def start_statsd_client(self, host: str | None = None, port: int | None = None) -> None:
        host = host or self.config.metrics.statsd_host
        port = port or self.config.metrics.statsd_port
        interval = self.config.metrics.export_interval_seconds
        stop_event = threading.Event()
        self._statsd_stop_event: threading.Event | None = stop_event

        def _loop() -> None:
            while not stop_event.is_set():
                try:
                    self.send_statsd(host, port)
                except OSError as e:
                    logger.warning(f"StatsD send error: {e}")
                stop_event.wait(timeout=interval)

        self._statsd_thread = threading.Thread(target=_loop, name="statsd-client", daemon=True)
        self._statsd_thread.start()
        logger.info(f"StatsD client started (interval={interval}s, target={host}:{port})")

    def stop_statsd_client(self) -> None:
        stop_event = getattr(self, "_statsd_stop_event", None)
        if stop_event is not None:
            stop_event.set()
            self._statsd_stop_event = None
            logger.info("StatsD client stopped")

    def send_statsd(self, host: str, port: int) -> None:
        """
        Send metrics to StatsD server via UDP.

        Args:
            host: StatsD server host
            port: StatsD server port
        """
        metrics = self.export_statsd()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for metric in metrics.metrics:
                sock.sendto(metric.encode("utf-8"), (host, port))
            sock.close()
            logger.debug(f"Sent {len(metrics.metrics)} metrics to {host}:{port}")
        except OSError as e:
            logger.error(f"Failed to send StatsD metrics to {host}:{port}: {e}")

    def reset_all(self) -> None:
        """
        Reset all metrics counters to 0.

        Note: Current implementation uses real-time probes,
        so there are no internal counters to reset.
        This method is a stub for future counter-based metrics.
        """
        logger.info("Metrics reset requested (no-op - metrics are real-time probes)")
        # Future: Reset persistent counters if we implement cumulative metrics
