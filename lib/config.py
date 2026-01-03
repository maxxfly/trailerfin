"""Configuration module for trailerfin."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# Environment variables
base_path: str | None = os.getenv("SCAN_PATH")
video_filename: str | None = os.getenv("VIDEO_FILENAME")
schedule_days: int = int(os.getenv("SCHEDULE_DAYS", 1))
video_start_time: int = int(os.getenv("VIDEO_START_TIME", 10))
tmdb_api_key: str | None = os.getenv("TMDB_API_KEY")

# HTTP Headers for IMDb requests
headers: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.imdb.com/",
    "Connection": "keep-alive",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

# Worker configuration
workers_env: str | None = os.getenv("WORKERS")
try:
    default_worker_count: int = int(workers_env) if workers_env is not None else 4
except ValueError:
    default_worker_count: int = 4
