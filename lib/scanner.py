"""Scanner module for processing IMDb folders and monitoring changes."""

import asyncio
import logging
import os
import re
import time
from typing import Any

import click

from lib.cache import (
    load_expiration_times,
    load_ignored_titles,
    save_expiration_times,
    save_ignored_titles,
)
from lib.config import base_path, video_filename
from lib.file_manager import (
    create_or_update_strm_file,
    download_trailer,
    format_duration,
    get_expiration_time,
)
from lib.imdb_scraper import get_direct_video_url_from_page, get_trailer_video_page_url
from lib.nfo_parser import get_imdb_from_nfo

try:
    import schedule
except ImportError:
    schedule = None


async def process_imdb_folder(
    root: str,
    imdb_id: str,
    expiration_times: dict[str, int],
    ignored_titles: dict[str, Any],
    download: bool = False,
    language: str = "en",
    show_progress: bool = False,
) -> None:
    """Process a single IMDb folder to refresh its trailer."""
    try:
        # Check if this title is in the ignore list
        if imdb_id in ignored_titles:
            if not show_progress:
                logging.info(f"Skipping ignored title {imdb_id} in {root}")
            return

        if download:
            # In download mode, check if trailer.mp4 already exists
            trailer_path = os.path.join(root, "trailer.mp4")
            if os.path.exists(trailer_path):
                if not show_progress:
                    logging.info(f"Trailer already downloaded for {imdb_id} in {root}")
                return
        else:
            # In .strm mode, check expiration times
            backdrops_path = os.path.join(root, "backdrops")
            strm_path = os.path.join(backdrops_path, video_filename)

            # Check if we need to refresh based on expiration time
            current_time = int(time.time())
            expiration_time = expiration_times.get(strm_path)

            if expiration_time and current_time < expiration_time:
                time_until_expiry = expiration_time - current_time
                formatted_duration = format_duration(time_until_expiry)
                if not show_progress:
                    logging.info(
                        f"Trailer link still valid for {imdb_id} in {root} (expires in {formatted_duration})"
                    )
                return

        if not show_progress:
            logging.info(f"Refreshing trailer for {imdb_id} in {root}")
        video_page_url = await get_trailer_video_page_url(imdb_id)
        if video_page_url:
            video_url = await get_direct_video_url_from_page(video_page_url)
            if video_url:
                if download:
                    # Download the video file
                    success = await download_trailer(
                        root, video_url, show_progress=show_progress
                    )
                    if not success:
                        logging.error(f"Failed to download trailer for {imdb_id}")
                else:
                    # Create .strm file
                    create_or_update_strm_file(root, video_url)
                    # Update expiration time
                    new_expiration = get_expiration_time(video_url)
                    if new_expiration:
                        expiration_times[strm_path] = new_expiration
                        save_expiration_times(expiration_times)
        else:
            # Add to ignored titles if no trailer found
            ignored_titles[imdb_id] = {
                "path": root,
                "last_checked": int(time.time()),
                "reason": "No trailer available",
            }
            save_ignored_titles(ignored_titles)
            if not show_progress:
                logging.info(f"Added {imdb_id} to ignored titles list")
    except Exception as e:
        logging.error(f"Worker error for {imdb_id} in {root}: {e}")


def scan_and_refresh_trailers(
    scan_paths: list[str] | None = None,
    worker_count: int = 4,
    use_nfo: bool = False,
    limit: int | None = None,
    download: bool = False,
    language: str = "en",
) -> None:
    """Scan all IMDb folders and refresh trailers."""
    # Handle multiple paths
    paths_to_scan = scan_paths if scan_paths else ([base_path] if base_path else [])

    if not paths_to_scan:
        logging.error("No scan paths provided and no default path configured")
        return

    # Validate all paths exist
    for path in paths_to_scan:
        if not os.path.exists(path):
            logging.error(f"Provided path does not exist: {path}")
            return

    # Load existing expiration times and ignored titles
    expiration_times = load_expiration_times()
    ignored_titles = load_ignored_titles()

    imdb_folders = []
    processed_series = set()  # Track processed TV series to avoid duplicates

    # Scan all provided directories
    for path_to_scan in paths_to_scan:
        logging.info(f"Scanning directory: {path_to_scan}")
        for root, dirs, files in os.walk(path_to_scan):
            imdb_id = None
            search_root = root

            if use_nfo:
                # Check if this is a season folder (Season XX, Season X, Saison XX, etc.)
                folder_name = os.path.basename(root).lower()
                if re.match(r"(season|saison|s)\s*\d+", folder_name):
                    # This is a season folder, look for NFO in parent directory
                    parent_dir = os.path.dirname(root)

                    # Skip if we already processed this series
                    if parent_dir in processed_series:
                        logging.debug(
                            f"Skipping {root} - parent series already processed"
                        )
                        continue

                    logging.debug(
                        f"Detected season folder {root}, checking parent: {parent_dir}"
                    )
                    imdb_id = get_imdb_from_nfo(parent_dir)
                    if imdb_id:
                        search_root = parent_dir
                        processed_series.add(parent_dir)
                        logging.debug(
                            f"Found IMDb ID {imdb_id} from parent NFO for series in {parent_dir}"
                        )
                else:
                    # Normal folder, check for NFO here
                    imdb_id = get_imdb_from_nfo(root)
                    if imdb_id:
                        logging.debug(f"Found IMDb ID {imdb_id} from NFO in {root}")
            else:
                # Use directory name pattern
                match = re.search(r"\{imdb-(tt\d+)\}", root)
                if match:
                    if not root.rstrip(os.sep).endswith(f"{{imdb-{match.group(1)}}}"):
                        continue
                    imdb_id = match.group(1)

            if imdb_id:
                # Count video files in the directory we'll actually use (search_root)
                video_extensions = (
                    ".mp4",
                    ".mkv",
                    ".avi",
                    ".mov",
                    ".wmv",
                    ".m4v",
                    ".flv",
                    ".webm",
                )

                # For series detected from season folders, check video count in the series root
                # For other folders, check in the current root
                check_dir = search_root
                check_files = []
                if os.path.exists(check_dir):
                    try:
                        check_files = os.listdir(check_dir)
                    except Exception as e:
                        logging.warning(f"Could not list files in {check_dir}: {e}")
                        check_files = files
                else:
                    check_files = files

                video_count = sum(
                    1 for f in check_files if f.lower().endswith(video_extensions)
                )

                # Skip folders with multiple video files (likely TV show episodes)
                # The trailer will be on the parent folder (TV show folder), not the episode folder
                if video_count > 1:
                    logging.debug(
                        f"Skipping {search_root} - contains {video_count} video files (likely TV show episodes)"
                    )
                    continue

                imdb_folders.append((search_root, imdb_id))
                # Stop collecting if we've reached the limit
                if limit and len(imdb_folders) >= limit:
                    logging.info(f"Reached limit of {limit} items, stopping collection")
                    break

    if not imdb_folders:
        logging.info("No IMDb folders found to process.")
        return

    logging.info(f"Processing {len(imdb_folders)} items")

    # Display folder names when limit is set
    if limit:
        logging.info("Folders to process:")
        for idx, (root, imdb_id) in enumerate(imdb_folders, 1):
            folder_name = os.path.basename(root)
            logging.info(f"  {idx}. {folder_name} (IMDb: {imdb_id})")

    # Process folders with progress bar using asyncio
    async def process_all():
        # Create a semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(worker_count)

        async def process_with_semaphore(root, imdb_id):
            async with semaphore:
                await process_imdb_folder(
                    root,
                    imdb_id,
                    expiration_times,
                    ignored_titles,
                    download,
                    language,
                    show_progress=True,
                )

        # Create all tasks
        tasks = [
            process_with_semaphore(root, imdb_id) for root, imdb_id in imdb_folders
        ]

        # Execute tasks with progress bar
        with click.progressbar(
            length=len(imdb_folders),
            label="Processing trailers",
            show_eta=True,
            show_percent=True,
        ) as bar:
            # Use as_completed to update progress as tasks finish
            for coro in asyncio.as_completed(tasks):
                try:
                    await coro
                    bar.update(1)
                except Exception as exc:
                    logging.error(f"Exception in worker: {exc}")
                    bar.update(1)

    # Run the async processing
    asyncio.run(process_all())


def run_scheduler(
    scan_paths: list[str] | None = None,
    worker_count: int = 4,
    use_nfo: bool = False,
    download: bool = False,
    language: str = "en",
) -> None:
    """Run scanner on a scheduled basis."""
    if not schedule:
        logging.error(
            "schedule module not installed. Please install with 'pip install schedule'."
        )
        return

    from lib.config import schedule_days

    def job():
        scan_and_refresh_trailers(
            scan_paths=scan_paths,
            worker_count=worker_count,
            use_nfo=use_nfo,
            download=download,
            language=language,
        )

    job()
    schedule.every(schedule_days).days.do(job)
    logging.info(f"Scheduler started. Running every {schedule_days} day(s).")
    while True:
        schedule.run_pending()
        time.sleep(60)


def check_expiring_links(
    expiration_times: dict[str, int],
    scan_path: str | None = None,
    worker_count: int = 4,
    ignored_titles: dict[str, Any] | None = None,
    download: bool = False,
    language: str = "en",
) -> None:
    """Check for links that are about to expire and refresh them."""
    # Skip expiration checks in download mode since videos are downloaded once
    if download:
        return

    if ignored_titles is None:
        ignored_titles = load_ignored_titles()

    current_time = int(time.time())
    expiring_links = []

    # Find links that will expire in the next hour
    for strm_path, expiration_time in expiration_times.items():
        if expiration_time - current_time < 3600:  # Less than 1 hour until expiration
            # Extract IMDb ID from the path
            root = os.path.dirname(os.path.dirname(strm_path))
            match = re.search(r"\{imdb-(tt\d+)\}", root)
            if match:
                imdb_id = match.group(1)
                # Only include if not in ignored titles
                if imdb_id not in ignored_titles:
                    expiring_links.append(strm_path)

    if expiring_links:
        logging.info(f"Found {len(expiring_links)} links expiring soon")
        # Extract IMDb IDs from the paths
        imdb_folders = []
        for strm_path in expiring_links:
            root = os.path.dirname(os.path.dirname(strm_path))
            match = re.search(r"\{imdb-(tt\d+)\}", root)
            if match:
                imdb_id = match.group(1)
                imdb_folders.append((root, imdb_id))

        if imdb_folders:

            async def process_expiring():
                semaphore = asyncio.Semaphore(worker_count)

                async def process_with_semaphore(root, imdb_id):
                    async with semaphore:
                        await process_imdb_folder(
                            root,
                            imdb_id,
                            expiration_times,
                            ignored_titles,
                            download,
                            language,
                        )

                tasks = [
                    process_with_semaphore(root, imdb_id)
                    for root, imdb_id in imdb_folders
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run(process_expiring())


def initialize_expiration_database(
    scan_paths: list[str] | None = None, use_nfo: bool = False
) -> dict[str, int]:
    """Initialize the expiration database by scanning existing .strm files."""
    paths_to_scan = scan_paths if scan_paths else ([base_path] if base_path else [])

    if not paths_to_scan:
        logging.error("No scan paths provided and no default path configured")
        return {}

    expiration_times = {}
    strm_files_found = False

    # Scan all provided directories
    for path_to_scan in paths_to_scan:
        if not os.path.exists(path_to_scan):
            logging.error(f"Provided path does not exist: {path_to_scan}")
            continue

        logging.info(f"Initializing expiration database for: {path_to_scan}")

        # First, try to find existing .strm files
        for root, dirs, files in os.walk(path_to_scan):
            if video_filename in files:
                strm_path = os.path.join(root, video_filename)
                try:
                    with open(strm_path, "r") as f:
                        url = f.read().strip()
                    expiration_time = get_expiration_time(url)
                    if expiration_time:
                        expiration_times[strm_path] = expiration_time
                        strm_files_found = True
                        logging.info(f"Found existing .strm file: {strm_path}")
                except Exception as e:
                    logging.error(f"Error reading .strm file {strm_path}: {e}")

    if not strm_files_found:
        logging.info("No existing .strm files found, performing full scan")
        # If no .strm files found, do a full scan
        scan_and_refresh_trailers(scan_paths, worker_count=4, use_nfo=use_nfo)
        # Reload expiration times after full scan
        expiration_times = load_expiration_times()

    return expiration_times


def watch_for_new_media(
    scan_paths: list[str] | None = None, worker_count: int = 4, use_nfo: bool = False
) -> set[str]:
    """Watch for new media folders and process them."""
    paths_to_scan = scan_paths if scan_paths else ([base_path] if base_path else [])

    if not paths_to_scan:
        logging.error("No scan paths provided")
        return set()

    current_folders = set()
    video_extensions = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".flv", ".webm")

    # Scan all provided directories
    for path_to_scan in paths_to_scan:
        if not os.path.exists(path_to_scan):
            logging.error(f"Provided path does not exist: {path_to_scan}")
            continue

        # Get current folders
        for root, dirs, files in os.walk(path_to_scan):
            has_media = False

            if use_nfo:
                # Check if folder has NFO file and video files
                imdb_id = get_imdb_from_nfo(root)
                if imdb_id:
                    video_count = sum(
                        1 for f in files if f.lower().endswith(video_extensions)
                    )
                # Only consider folders with exactly 1 video file
                # Multi-video folders are likely TV episodes, trailer will be on parent folder
                has_media = video_count == 1
        else:
            # Check if folder matches IMDb pattern
            match = re.search(r"\{imdb-(tt\d+)\}", root)
            if match and root.rstrip(os.sep).endswith(f"{{imdb-{match.group(1)}}}"):
                # Verify this is a media folder with exactly 1 video file
                video_count = sum(
                    1 for f in files if f.lower().endswith(video_extensions)
                )
                # Only consider folders with exactly 1 video file
                has_media = video_count == 1

            if has_media:
                current_folders.add(root)
                logging.debug(f"Found media folder: {root}")

    return current_folders


def run_continuous_monitor(
    scan_paths: list[str] | None = None,
    worker_count: int = 4,
    use_nfo: bool = False,
    download: bool = False,
    language: str = "en",
) -> None:
    """Run continuous monitoring for expiring links and new media."""
    logging.info("Starting continuous monitor for expiring links")

    # Initialize the database
    expiration_times = initialize_expiration_database(scan_paths, use_nfo)
    save_expiration_times(expiration_times)

    # Load ignored titles
    ignored_titles = load_ignored_titles()

    # Get initial set of folders
    last_known_folders = watch_for_new_media(scan_paths, worker_count, use_nfo)
    logging.info(f"Initial scan found {len(last_known_folders)} media folders")

    while True:
        try:
            # Check for new media
            current_folders = watch_for_new_media(scan_paths, worker_count, use_nfo)
            new_folders = current_folders - last_known_folders

            if new_folders:
                logging.info(f"Found {len(new_folders)} new media folders")
                for root in new_folders:
                    imdb_id = None
                    if use_nfo:
                        imdb_id = get_imdb_from_nfo(root)
                    else:
                        match = re.search(r"\{imdb-(tt\d+)\}", root)
                        if match:
                            imdb_id = match.group(1)

                    if imdb_id:
                        logging.info(f"Processing new media: {root}")
                        asyncio.run(
                            process_imdb_folder(
                                root,
                                imdb_id,
                                expiration_times,
                                ignored_titles,
                                download,
                                language,
                            )
                        )
                last_known_folders = current_folders
                save_expiration_times(expiration_times)

            # Check for expiring links
            check_expiring_links(
                expiration_times,
                None,  # Not used by check_expiring_links
                worker_count,
                ignored_titles,
                download,
                language,
            )

            # Sleep for 5 minutes before next check
            time.sleep(300)
        except KeyboardInterrupt:
            logging.info("Continuous monitor stopped by user")
            break
        except Exception as e:
            logging.error(f"Error in continuous monitor: {e}")
            time.sleep(60)  # Wait a minute before retrying on error
