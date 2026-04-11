"""Dashboard and metrics commands."""

import sys

import click

from village.config import get_config
from village.errors import EXIT_ERROR
from village.logging import get_logger

logger = get_logger(__name__)


@click.command()
@click.option("--watch", is_flag=True, help="Auto-refresh mode")
@click.option(
    "--refresh-interval",
    type=int,
    default=None,
    help="Refresh interval in seconds (default: from config)",
)
def dashboard(watch: bool, refresh_interval: int | None) -> None:
    """
    Show real-time dashboard of Village state.

    Displays active workers, task queue, lock status, and orphans.
    Auto-refreshes every 2 seconds by default (configurable).

    \b
    Non-mutating. Probes actual state, doesn't create directories.

    Examples:
        village dashboard
        village dashboard --watch
        village dashboard --watch --refresh-interval 5
        village dashboard --refresh-interval 10
    \b

    Flags:
        --watch: Enable auto-refresh mode
        --refresh-interval: Set refresh interval in seconds

    Default: Static dashboard view (no auto-refresh)
    """
    from village.dashboard import VillageDashboard

    config = get_config()

    interval = refresh_interval or config.dashboard.refresh_interval_seconds
    enabled = config.dashboard.enabled

    if not enabled:
        click.echo("Dashboard is disabled. Enable with DASHBOARD_ENABLED=true")
        sys.exit(EXIT_ERROR)

    if watch:
        dash = VillageDashboard(config.tmux_session)
        dash.start_watch_mode(interval)
    else:
        from village.dashboard import render_dashboard_static

        output = render_dashboard_static(config.tmux_session)
        click.echo(output)


@click.command()
@click.option("--backend", type=click.Choice(["prometheus", "statsd"]), help="Metrics backend")
@click.option("--port", type=int, help="Port for metrics export")
@click.option("--interval", type=int, help="Export interval in seconds")
@click.option("--reset", is_flag=True, help="Reset all metrics counters to 0")
def metrics(backend: str, port: int | None, interval: int | None, reset: bool) -> None:
    """
    Export Village metrics.

    Exports metrics to Prometheus (HTTP) or StatsD (UDP).
    Metrics include workers, queue length, locks, orphans.

    \b
    Non-mutating. Collects metrics from Village state.

    Examples:
        village metrics                           # Export with config defaults
        village metrics --backend prometheus --port 9090
        village metrics --backend statsd
        village metrics --reset                      # Reset counters (future)

    Backend options:
        --backend prometheus: Prometheus HTTP endpoint
        --backend statsd: StatsD UDP socket

    Other options:
        --port: Port for Prometheus server (default: from config)
        --interval: Export interval in seconds (default: from config)
        --reset: Reset all metrics counters to 0 (for testing)

    Default: One-time export using configured backend
    """
    if reset and backend:
        click.echo(
            "Error: --reset and --backend are mutually exclusive. "
            "Use --reset to clear counters, or --backend to export metrics.",
            err=True,
        )
        sys.exit(EXIT_ERROR)

    from village.metrics import MetricsCollector

    config = get_config()

    if reset:
        collector = MetricsCollector(config, session_name=None)
        collector.reset_all()

        click.echo("Metrics counters reset to 0")
        return

    backend_choice = backend or config.metrics.backend

    collector = MetricsCollector(config)

    if backend_choice == "prometheus":
        prometheus_metrics = collector.export_prometheus()
        click.echo(f"Prometheus metrics:\n{prometheus_metrics}")
    elif backend_choice == "statsd":
        statsd_metrics = collector.export_statsd()
        click.echo(f"StatsD metrics:\n{statsd_metrics}")
    else:
        click.echo(f"Unknown backend: {backend_choice}")
        sys.exit(EXIT_ERROR)
