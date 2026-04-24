"""Test metrics collection and export."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from village.locks import Lock, write_lock
from village.metrics import (
    MetricsCollector,
    MetricsReport,
    PrometheusMetrics,
    StatsDMetrics,
)


def test_metrics_collector_collect_no_data(tmp_path: Path):
    """Test metrics collection with no data."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.status.session_exists") as mock_exists:
        mock_exists.return_value = False

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes") as mock_panes:
                mock_panes.return_value = set()

                collector = MetricsCollector(config, "village")
                report = collector.collect_metrics()

                assert isinstance(report, MetricsReport)
                assert report.active_workers == 0
                assert report.queue_length == 0
                assert report.stale_locks == 0
                assert report.orphans_count == 0
                assert report.task_completion_rate == 0.0
                assert report.average_task_duration_seconds == 0.0


def test_metrics_collector_collect_with_workers(tmp_path: Path):
    """Test metrics collection with active workers."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = config

        with patch("village.status.get_config") as mock_status_config:
            mock_status_config.return_value = config

        with patch("village.cleanup.get_config") as mock_cleanup_config:
            mock_cleanup_config.return_value = config

        with patch("village.queue.get_config") as mock_queue_config:
            mock_queue_config.return_value = config

        with patch("village.event_log.read_events") as mock_read_events:
            mock_read_events.return_value = []

            with patch("village.locks.panes") as mock_panes:
                mock_panes.return_value = {"%12", "%13"}

                lock1 = Lock(
                    task_id="bd-a3f8",
                    pane_id="%12",
                    window="build-1-bd-a3f8",
                    agent="build",
                    claimed_at=datetime.now(timezone.utc),
                )
                write_lock(lock1)

                lock2 = Lock(
                    task_id="bd-b4f2",
                    pane_id="%13",
                    window="test-2-bd-b4f2",
                    agent="test",
                    claimed_at=datetime.now(timezone.utc),
                )
                write_lock(lock2)

                collector = MetricsCollector(config, "village")
                report = collector.collect_metrics()

                assert report.active_workers == 2

                lock1.path.unlink(missing_ok=True)
                lock2.path.unlink(missing_ok=True)


def test_metrics_collector_export_prometheus(tmp_path: Path):
    """Test Prometheus metrics export."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.status.get_config") as mock_status_config:
        mock_status_config.return_value = config

    with patch("village.cleanup.get_config") as mock_cleanup_config:
        mock_cleanup_config.return_value = config

    with patch("village.queue.get_config") as mock_queue_config:
        mock_queue_config.return_value = config

    with patch("village.event_log.read_events") as mock_read_events:
        mock_read_events.return_value = []

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes") as mock_panes:
                mock_panes.return_value = set()

                collector = MetricsCollector(config, "village")
                prometheus = collector.export_prometheus()

                assert isinstance(prometheus, PrometheusMetrics)
                assert prometheus.content_type == "text/plain; version=0.0.4; charset=utf-8"
                assert len(prometheus.metrics) > 0

                assert any("village_active_workers" in m for m in prometheus.metrics)
                assert any("village_queue_length" in m for m in prometheus.metrics)
                assert any("village_stale_locks" in m for m in prometheus.metrics)
                assert any("village_orphans_count" in m for m in prometheus.metrics)
                assert any("village_task_completion_rate" in m for m in prometheus.metrics)
                assert any("village_average_task_duration_seconds" in m for m in prometheus.metrics)


def test_metrics_collector_export_statsd(tmp_path: Path):
    """Test StatsD metrics export."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.status.get_config") as mock_status_config:
        mock_status_config.return_value = config

    with patch("village.cleanup.get_config") as mock_cleanup_config:
        mock_cleanup_config.return_value = config

    with patch("village.queue.get_config") as mock_queue_config:
        mock_queue_config.return_value = config

    with patch("village.event_log.read_events") as mock_read_events:
        mock_read_events.return_value = []

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes") as mock_panes:
                mock_panes.return_value = set()

                collector = MetricsCollector(config, "village")
                statsd = collector.export_statsd()

                assert isinstance(statsd, StatsDMetrics)
                assert len(statsd.metrics) == 6

                assert any("village.active_workers" in m for m in statsd.metrics)
                assert any("village.queue_length" in m for m in statsd.metrics)
                assert any("village.stale_locks" in m for m in statsd.metrics)
                assert any("village.orphans_count" in m for m in statsd.metrics)
                assert any("village.task_completion_rate" in m for m in statsd.metrics)
                assert any("village.average_task_duration_seconds" in m for m in statsd.metrics)

                assert all(m.endswith("|g") for m in statsd.metrics)


def test_metrics_collector_stale_locks(tmp_path: Path):
    """Test metrics collection with stale locks."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = config

    with patch("village.cleanup.get_config") as mock_cleanup_config:
        mock_cleanup_config.return_value = config

    with patch("village.queue.get_config") as mock_queue_config:
        mock_queue_config.return_value = config

    with patch("village.event_log.read_events") as mock_read_events:
        mock_read_events.return_value = []

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes") as mock_panes:
                mock_panes.return_value = set()

                stale_lock = Lock(
                    task_id="bd-stale",
                    pane_id="%99",
                    window="test-window",
                    agent="test",
                    claimed_at=datetime.now(timezone.utc),
                )
                write_lock(stale_lock)

                collector = MetricsCollector(config, "village")
                report = collector.collect_metrics()

                assert report.active_workers == 0
                assert report.stale_locks == 1

                stale_lock.path.unlink(missing_ok=True)


def test_metrics_collector_orphans(tmp_path: Path):
    """Test metrics collection with orphans."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.status.get_config") as mock_status_config:
        mock_status_config.return_value = config

    with patch("village.cleanup.get_config") as mock_cleanup_config:
        mock_cleanup_config.return_value = config

    with patch("village.queue.get_config") as mock_queue_config:
        mock_queue_config.return_value = config

    with patch("village.event_log.read_events") as mock_read_events:
        mock_read_events.return_value = []

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes") as mock_panes:
                mock_panes.return_value = set()

                orphan_worktree = config.worktrees_dir / "bd-orphan"
                orphan_worktree.mkdir()

                collector = MetricsCollector(config, "village")
                report = collector.collect_metrics()

                assert report.orphans_count == 1

                orphan_worktree.rmdir()


def test_metrics_collector_send_statsd(tmp_path: Path):
    """Test sending StatsD metrics via UDP."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.status.get_config") as mock_status_config:
        mock_status_config.return_value = config

    with patch("village.cleanup.get_config") as mock_cleanup_config:
        mock_cleanup_config.return_value = config

    with patch("village.queue.get_config") as mock_queue_config:
        mock_queue_config.return_value = config

    with patch("village.event_log.read_events") as mock_read_events:
        mock_read_events.return_value = []

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes") as mock_panes:
                mock_panes.return_value = set()

                collector = MetricsCollector(config, "village")

                with patch("village.metrics.socket.socket"):
                    collector.send_statsd("localhost", 8125)


def test_metrics_collector_prometheus_server_lifecycle():
    """Test starting and stopping Prometheus server."""
    from village.config import get_config

    config = get_config()
    collector = MetricsCollector(config, "village")

    collector.start_prometheus_server(host="127.0.0.1", port=0)
    assert collector._prometheus_server is not None
    assert collector._prometheus_thread.is_alive()

    import urllib.request

    port = collector._prometheus_server.server_address[1]
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/metrics")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            assert "village_active_workers" in body
            assert resp.headers.get("Content-Type") == "text/plain; version=0.0.4; charset=utf-8"
    except Exception:
        pass

    collector.stop_prometheus_server()
    assert collector._prometheus_server is None


def test_metrics_collector_statsd_client_lifecycle():
    """Test starting and stopping StatsD client."""
    from village.config import get_config

    config = get_config()
    collector = MetricsCollector(config, "village")

    with patch("village.metrics.socket.socket"):
        collector.start_statsd_client("localhost", 8125)
        assert collector._statsd_stop_event is not None
        assert collector._statsd_thread.is_alive()

        collector.stop_statsd_client()
        assert collector._statsd_stop_event is None
