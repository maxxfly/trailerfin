"""TrailerFin - IMDb trailer manager for Plex/ Jellyfin media libraries."""

import click

from lib.config import default_worker_count
from lib.scanner import run_continuous_monitor, run_scheduler, scan_and_refresh_trailers


@click.command()
@click.option(
    "--dir", type=str, default=None, help="Directory to scan (defaults to /mnt/plex)"
)
@click.option("--schedule", is_flag=True, help="Run as a weekly scheduled job")
@click.option(
    "--workers",
    type=int,
    default=default_worker_count,
    help=f"Number of worker threads (default: {default_worker_count})",
)
@click.option("--monitor", is_flag=True, help="Run in continuous monitoring mode")
def main(dir: str, schedule: bool, workers: int, monitor: bool) -> None:
    """Scan and refresh IMDb trailers."""
    if monitor:
        run_continuous_monitor(dir, workers)
    elif schedule:
        run_scheduler(dir, workers)
    else:
        scan_and_refresh_trailers(dir, workers)


if __name__ == "__main__":
    main()
