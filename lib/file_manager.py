"""File management module for .strm files and URLs."""

import asyncio
import logging
import os
import time
import urllib.parse

import aiohttp

from lib.config import headers, video_filename

try:
    import yt_dlp

    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logging.warning("yt-dlp not installed. YouTube downloads will not be available.")


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


async def download_trailer(
    folder_path: str, video_url: str, show_progress: bool = False
) -> bool:
    """Download trailer video and save as trailer.mp4 in the folder.

    Supports both direct video URLs (IMDb) and YouTube URLs (TMDB).
    """
    trailer_path = os.path.join(folder_path, "trailer.mp4")

    try:
        # Check if it's a YouTube URL
        is_youtube = "youtube.com" in video_url or "youtu.be" in video_url

        if is_youtube:
            # Use yt-dlp for YouTube downloads
            if not YT_DLP_AVAILABLE:
                logging.error("Cannot download YouTube trailers: yt-dlp not installed")
                return False

            if not show_progress:
                logging.info(f"Downloading YouTube trailer to {trailer_path}")

            # yt-dlp options - remove .mp4 from outtmpl since yt-dlp adds extension
            base_path = trailer_path.rsplit(".", 1)[0]  # Remove .mp4 extension
            ydl_opts = {
                "format": "best[ext=mp4]/best",  # Prefer MP4, fallback to best quality
                "outtmpl": f"{base_path}.%(ext)s",  # Let yt-dlp add the extension
                "quiet": show_progress,  # Suppress output when progress bar is shown
                "no_warnings": show_progress,
                "noplaylist": True,
                "merge_output_format": "mp4",
                "postprocessors": [
                    {  # Ensure MP4 format
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    }
                ],
            }

            # Run yt-dlp in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([video_url])
                )
            except Exception as e:
                logging.error(f"yt-dlp execution failed: {e}")
                return False

            # Check if download was successful (file exists and has content)
            if os.path.exists(trailer_path) and os.path.getsize(trailer_path) > 0:
                # Verify it's actually a video file, not HTML
                with open(trailer_path, "rb") as f:
                    header = f.read(100)
                    if b"<html" in header.lower() or b"<!doctype" in header.lower():
                        logging.error(
                            f"Downloaded file is HTML, not a video. Removing {trailer_path}"
                        )
                        os.remove(trailer_path)
                        return False

                if not show_progress:
                    size_mb = os.path.getsize(trailer_path) / (1024 * 1024)
                    logging.info(f"Downloaded {size_mb:.2f} MB to {trailer_path}")
                return True
            else:
                logging.error(f"YouTube download failed: file not created or empty")
                return False
        else:
            # Use aiohttp for direct video URLs (IMDb)
            if not show_progress:
                logging.info(f"Downloading trailer to {trailer_path}")
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    video_url, timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()

                    # Get total size for progress logging
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    with open(trailer_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

            if not show_progress:
                if total_size > 0:
                    size_mb = total_size / (1024 * 1024)
                    logging.info(f"Downloaded {size_mb:.2f} MB to {trailer_path}")
                else:
                    logging.info(f"Downloaded trailer to {trailer_path}")

            return True
    except Exception as e:
        logging.error(f"Error downloading trailer to {trailer_path}: {e}")
        # Clean up partial download
        if os.path.exists(trailer_path):
            os.remove(trailer_path)
        return False
