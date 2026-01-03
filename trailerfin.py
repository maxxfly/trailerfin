"""TrailerFin - IMDb trailer manager for Plex/ Jellyfin media libraries."""

import click

from lib.config import default_worker_count
from lib.scanner import run_continuous_monitor, run_scheduler, scan_and_refresh_trailers


@click.command()
@click.option(
    "--dir",
    multiple=True,
    type=str,
    help="Directory to scan (can be specified multiple times). Defaults to /mnt/plex if none specified",
)
@click.option("--schedule", is_flag=True, help="Run as a weekly scheduled job")
@click.option(
    "--workers",
    type=int,
    default=default_worker_count,
    help=f"Number of worker threads (default: {default_worker_count})",
)
@click.option("--monitor", is_flag=True, help="Run in continuous monitoring mode")
@click.option(
    "--use-nfo",
    is_flag=True,
    help="Parse .nfo files to find je vIMDb ID instead of using directory names",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit the number of items to process (useful for testing)",
)
@click.option(
    "--download",
    is_flag=True,
    help="Download trailer as trailer.mp4 instead of creating .strm file",
)
@click.option(
    "--language",
    type=str,
    default="en",
    help="Preferred trailer language (ISO 639-1 code: en, fr, es, etc.). Defaults to 'en'",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force download/refresh even if trailer already exists",
)
def main(
    dir: tuple[str, ...],
    schedule: bool,
    workers: int,
    monitor: bool,
    use_nfo: bool,
    limit: int | None,
    download: bool,
    language: str,
    force: bool,
) -> None:
    """Scan and refresh IMDb trailers."""
    # Convert tuple to list, use default if empty
    directories = list(dir) if dir else None

    if monitor:
        run_continuous_monitor(directories, workers, use_nfo, download, language, force)
    elif schedule:
        run_scheduler(directories, workers, use_nfo, download, language, force)
    else:
        scan_and_refresh_trailers(
            scan_paths=directories,
            worker_count=workers,
            use_nfo=use_nfo,
            limit=limit,
            download=download,
            language=language,
            force=force,
        )


if __name__ == "__main__":
    main()
