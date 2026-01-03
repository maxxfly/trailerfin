"""Scanner module for processing IMDb folders and monitoring changes."""

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from lib.cache import (
    load_expiration_times,
    load_ignored_titles,
    save_expiration_times,
    save_ignored_titles,
)
from lib.config import base_path, video_filename
from lib.file_manager import (
    create_or_update_strm_file,
    format_duration,
    get_expiration_time,
)
from lib.imdb_scraper import get_direct_video_url_from_page, get_trailer_video_page_url

try:
    import schedule
except ImportError:
    schedule = None


def process_imdb_folder(
    root: str,
    imdb_id: str,
    expiration_times: dict[str, int],
    ignored_titles: dict[str, Any],
) -> None:
    """Process a single IMDb folder to refresh its trailer."""
    try:
        # Check if this title is in the ignore list
        if imdb_id in ignored_titles:
            logging.info(f"Skipping ignored title {imdb_id} in {root}")
            return

        backdrops_path = os.path.join(root, "backdrops")
        strm_path = os.path.join(backdrops_path, video_filename)

        # Check if we need to refresh based on expiration time
        current_time = int(time.time())
        expiration_time = expiration_times.get(strm_path)

        if expiration_time and current_time < expiration_time:
            time_until_expiry = expiration_time - current_time
            formatted_duration = format_duration(time_until_expiry)
            logging.info(
                f"Trailer link still valid for {imdb_id} in {root} (expires in {formatted_duration})"
            )
            return

        logging.info(f"Refreshing trailer for {imdb_id} in {root}")
        video_page_url = get_trailer_video_page_url(imdb_id)
        if video_page_url:
            video_url = get_direct_video_url_from_page(video_page_url)
            if video_url:
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
            logging.info(f"Added {imdb_id} to ignored titles list")
    except Exception as e:
        logging.error(f"Worker error for {imdb_id} in {root}: {e}")


def scan_and_refresh_trailers(
    scan_path: str | None = None, worker_count: int = 4
) -> None:
    """Scan all IMDb folders and refresh trailers."""
    path_to_scan = scan_path if scan_path else base_path
    if not os.path.exists(path_to_scan):
        logging.error(f"Provided path does not exist: {path_to_scan}")
        return

    # Load existing expiration times and ignored titles
    expiration_times = load_expiration_times()
    ignored_titles = load_ignored_titles()

    imdb_folders = []
    for root, dirs, files in os.walk(path_to_scan):
        match = re.search(r"\{imdb-(tt\d+)\}", root)
        if match:
            if not root.rstrip(os.sep).endswith(f"{{imdb-{match.group(1)}}}"):
                continue
            imdb_id = match.group(1)
            imdb_folders.append((root, imdb_id))

    if not imdb_folders:
        logging.info("No IMDb folders found to process.")
        return

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_folder = {
            executor.submit(
                process_imdb_folder, root, imdb_id, expiration_times, ignored_titles
            ): (root, imdb_id)
            for root, imdb_id in imdb_folders
        }
        for future in as_completed(future_to_folder):
            root, imdb_id = future_to_folder[future]
            try:
                future.result()
            except Exception as exc:
                logging.error(f"Exception in worker for {imdb_id} in {root}: {exc}")


def run_scheduler(scan_path: str | None = None, worker_count: int = 4) -> None:
    """Run scanner on a scheduled basis."""
    if not schedule:
        logging.error(
            "schedule module not installed. Please install with 'pip install schedule'."
        )
        return

    from lib.config import schedule_days

    def job():
        scan_and_refresh_trailers(scan_path, worker_count)

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
) -> None:
    """Check for links that are about to expire and refresh them."""
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
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                future_to_folder = {
                    executor.submit(
                        process_imdb_folder,
                        root,
                        imdb_id,
                        expiration_times,
                        ignored_titles,
                    ): (root, imdb_id)
                    for root, imdb_id in imdb_folders
                }
                for future in as_completed(future_to_folder):
                    root, imdb_id = future_to_folder[future]
                    try:
                        future.result()
                    except Exception as exc:
                        logging.error(
                            f"Exception in worker for {imdb_id} in {root}: {exc}"
                        )


def initialize_expiration_database(scan_path: str | None = None) -> dict[str, int]:
    """Initialize the expiration database by scanning existing .strm files."""
    path_to_scan = scan_path if scan_path else base_path
    if not os.path.exists(path_to_scan):
        logging.error(f"Provided path does not exist: {path_to_scan}")
        return {}

    expiration_times = {}
    strm_files_found = False

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
        scan_and_refresh_trailers(scan_path)
        # Reload expiration times after full scan
        expiration_times = load_expiration_times()

    return expiration_times


def watch_for_new_media(
    scan_path: str | None = None, worker_count: int = 4
) -> set[str]:
    """Watch for new media folders and process them."""
    path_to_scan = scan_path if scan_path else base_path
    if not os.path.exists(path_to_scan):
        logging.error(f"Provided path does not exist: {path_to_scan}")
        return set()

    # Get current folders
    current_folders = set()
    for root, dirs, files in os.walk(path_to_scan):
        match = re.search(r"\{imdb-(tt\d+)\}", root)
        if match and root.rstrip(os.sep).endswith(f"{{imdb-{match.group(1)}}}"):
            # Verify this is a media folder by checking for video files
            has_video = any(
                f.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".wmv"))
                for f in files
            )
            if has_video:
                current_folders.add(root)
                logging.debug(f"Found media folder: {root}")

    return current_folders


def run_continuous_monitor(scan_path: str | None = None, worker_count: int = 4) -> None:
    """Run continuous monitoring for expiring links and new media."""
    logging.info("Starting continuous monitor for expiring links")

    # Initialize the database
    expiration_times = initialize_expiration_database(scan_path)
    save_expiration_times(expiration_times)

    # Load ignored titles
    ignored_titles = load_ignored_titles()

    # Get initial set of folders
    last_known_folders = watch_for_new_media(scan_path, worker_count)
    logging.info(f"Initial scan found {len(last_known_folders)} media folders")

    while True:
        try:
            # Check for new media
            current_folders = watch_for_new_media(scan_path, worker_count)
            new_folders = current_folders - last_known_folders

            if new_folders:
                logging.info(f"Found {len(new_folders)} new media folders")
                for root in new_folders:
                    match = re.search(r"\{imdb-(tt\d+)\}", root)
                    if match:
                        imdb_id = match.group(1)
                        logging.info(f"Processing new media: {root}")
                        process_imdb_folder(
                            root, imdb_id, expiration_times, ignored_titles
                        )
                last_known_folders = current_folders
                save_expiration_times(expiration_times)

            # Check for expiring links
            check_expiring_links(
                expiration_times, scan_path, worker_count, ignored_titles
            )

            # Sleep for 5 minutes before next check
            time.sleep(300)
        except KeyboardInterrupt:
            logging.info("Continuous monitor stopped by user")
            break
        except Exception as e:
            logging.error(f"Error in continuous monitor: {e}")
            time.sleep(60)  # Wait a minute before retrying on error
