"""Metrics collection and export for Village."""

import logging
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

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

        completion_rate = len([e for e in completed_events if e.result == "ok"]) / len(
            completed_events
        )

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
        lines.append(
            f"village_average_task_duration_seconds {report.average_task_duration_seconds}"
        )

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
        lines.append(
            f"village.average_task_duration_seconds:{report.average_task_duration_seconds}|g"
        )

        return StatsDMetrics(metrics=lines)

    def start_prometheus_server(self, port: int) -> None:
        """
        Start Prometheus HTTP server on specified port.

        Args:
            port: HTTP port to listen on
        """
        raise NotImplementedError("Prometheus server not yet implemented")

    def start_statsd_client(self, host: str, port: int) -> None:
        """
        Start StatsD client for periodic metric export.

        Args:
            host: StatsD server host
            port: StatsD server port
        """
        raise NotImplementedError("StatsD client not yet implemented")

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
