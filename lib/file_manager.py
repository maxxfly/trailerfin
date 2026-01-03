"""File management module for .strm files and URLs."""

import logging
import os
import time
import urllib.parse

from lib.config import video_filename


def create_or_update_strm_file(folder_path: str, video_url: str) -> None:
    """Create or update a .strm file with the video URL."""
    backdrops_path = os.path.join(folder_path, "backdrops")
    os.makedirs(backdrops_path, exist_ok=True)
    strm_path = os.path.join(backdrops_path, video_filename)
    with open(strm_path, "w") as f:
        f.write(video_url)
    logging.info(f"Updated {strm_path}")


def is_strm_expired(strm_path: str) -> bool:
    """Check if a .strm file's URL has expired."""
    if not os.path.exists(strm_path):
        return True
    try:
        with open(strm_path, "r") as f:
            url = f.read().strip()
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        expires_list = query.get("Expires")
        if not expires_list:
            return True
        expires = int(expires_list[0])
        now = int(time.time())
        return now >= expires
    except Exception as e:
        logging.error(f"Error checking expiration for {strm_path}: {e}")
        return True


def get_expiration_time(url: str) -> int | None:
    """Extract expiration timestamp from URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        expires_list = query.get("Expires")
        if not expires_list:
            return None
        return int(expires_list[0])
    except Exception as e:
        logging.error(f"Error parsing expiration time from URL: {e}")
        return None


def format_duration(seconds: int) -> str:
    """Format seconds into minutes and seconds."""
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}min {remaining_seconds}sec"
