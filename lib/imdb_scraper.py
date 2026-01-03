"""IMDb scraping module for extracting trailer URLs."""

import asyncio
import json
import logging
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from lib.config import headers, tmdb_api_key, video_start_time

# Global flag to track if TMDB API is available
_tmdb_api_available = None


async def validate_tmdb_api_key() -> bool:
    """Validate TMDB API key at startup. Returns True if valid, False otherwise."""
    global _tmdb_api_available

    if not tmdb_api_key:
        logging.warning(
            "TMDB_API_KEY not set. Multi-language trailer support disabled. "
            "Get a free API key at https://www.themoviedb.org/settings/api"
        )
        _tmdb_api_available = False
        return False

    try:
        async with aiohttp.ClientSession() as session:
            # Test the API key with a simple configuration request
            url = f"https://api.themoviedb.org/3/configuration?api_key={tmdb_api_key}"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logging.info(
                        "TMDB API key validated successfully. Multi-language support enabled."
                    )
                    _tmdb_api_available = True
                    return True
                elif response.status == 401:
                    logging.error(
                        "TMDB API key is invalid (401 Unauthorized). "
                        "Please check your TMDB_API_KEY in the .env file. "
                        "Falling back to IMDb scraping (English only)."
                    )
                    _tmdb_api_available = False
                    return False
                else:
                    logging.warning(
                        f"TMDB API returned status {response.status}. "
                        f"Falling back to IMDb scraping."
                    )
                    _tmdb_api_available = False
                    return False
    except Exception as e:
        logging.warning(
            f"Failed to validate TMDB API key: {e}. Falling back to IMDb scraping."
        )
        _tmdb_api_available = False
        return False


async def imdb_to_tmdb(imdb_id: str) -> tuple[str, str] | None:
    """Convert IMDb ID to TMDB ID using TMDB API. Returns (tmdb_id, media_type)."""
    global _tmdb_api_available

    # If we already know TMDB API is not available, skip it
    if _tmdb_api_available is False:
        return None

    if not tmdb_api_key:
        if _tmdb_api_available is None:
            logging.warning(
                "TMDB_API_KEY not set. Falling back to IMDb scraping (English only)."
            )
            _tmdb_api_available = False
        return None

    try:
        async with aiohttp.ClientSession() as session:
            # Try movie search first
            url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={tmdb_api_key}&external_source=imdb_id"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    # Check for movie results
                    if data.get("movie_results"):
                        tmdb_id = str(data["movie_results"][0]["id"])
                        logging.debug(
                            f"Found TMDB movie ID {tmdb_id} for IMDb {imdb_id}"
                        )
                        return (tmdb_id, "movie")

                    # Check for TV show results
                    if data.get("tv_results"):
                        tmdb_id = str(data["tv_results"][0]["id"])
                        logging.debug(f"Found TMDB TV ID {tmdb_id} for IMDb {imdb_id}")
                        return (tmdb_id, "tv")

                    logging.warning(f"No TMDB results found for IMDb ID {imdb_id}")
                else:
                    logging.debug(
                        f"TMDB API error {response.status} for IMDb ID {imdb_id}"
                    )
    except Exception as e:
        logging.error(f"Error converting IMDb->TMDB: {e}")

    return None


async def tmdb_to_imdb(tmdb_id: str) -> str | None:
    """Convert TMDB ID to IMDB ID using TMDB API. Try both as movie and TV show."""
    global _tmdb_api_available

    if _tmdb_api_available is False:
        return None

    if not tmdb_api_key:
        if _tmdb_api_available is None:
            logging.warning("TMDB_API_KEY not set.")
            _tmdb_api_available = False
        return None
    # Try as movie
    url_movie = f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url_movie, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    imdb_id = data.get("imdb_id")
                    if imdb_id and imdb_id.startswith("tt"):
                        return imdb_id
            # Try as TV Shows if it fails
            url_tv = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
            async with session.get(
                url_tv, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    imdb_id = data.get("imdb_id")
                    if imdb_id and imdb_id.startswith("tt"):
                        return imdb_id
                else:
                    logging.error(
                        f"TMDB API error {response.status} for TMDB ID {tmdb_id}"
                    )
    except Exception as e:
        logging.error(f"Error converting TMDB->IMDB: {e}")
    return None


async def get_tmdb_trailer_url(
    tmdb_id: str, media_type: str = "movie", language: str = "en"
) -> str | None:
    """Get trailer URL directly from TMDB API with language preference."""
    global _tmdb_api_available

    if _tmdb_api_available is False:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            # Get videos from TMDB
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/videos?api_key={tmdb_api_key}&language={language}"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    videos = data.get("results", [])

                    if not videos and language != "en":
                        # Fallback to English if no videos in requested language
                        logging.info(
                            f"No trailers found in '{language}', trying English"
                        )
                        url_en = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/videos?api_key={tmdb_api_key}&language=en"
                        async with session.get(
                            url_en, timeout=aiohttp.ClientTimeout(total=10)
                        ) as response_en:
                            if response_en.status == 200:
                                data_en = await response_en.json()
                                videos = data_en.get("results", [])

                    # Filter for trailers only (type="Trailer")
                    trailers = [
                        v
                        for v in videos
                        if v.get("type") == "Trailer" and v.get("site") == "YouTube"
                    ]

                    if trailers:
                        # Prefer official trailers
                        official = [t for t in trailers if t.get("official", False)]
                        trailer = official[0] if official else trailers[0]

                        youtube_key = trailer.get("key")
                        if youtube_key:
                            # Return YouTube URL
                            youtube_url = (
                                f"https://www.youtube.com/watch?v={youtube_key}"
                            )
                            logging.info(
                                f"Found TMDB trailer: {trailer.get('name', 'Trailer')} ({language})"
                            )
                            return youtube_url

                    # If no trailers, try clips
                    clips = [
                        v
                        for v in videos
                        if v.get("type") == "Clip" and v.get("site") == "YouTube"
                    ]
                    if clips:
                        youtube_key = clips[0].get("key")
                        if youtube_key:
                            youtube_url = (
                                f"https://www.youtube.com/watch?v={youtube_key}"
                            )
                            logging.info(
                                f"Found TMDB clip: {clips[0].get('name', 'Clip')} ({language})"
                            )
                            return youtube_url
                else:
                    logging.error(
                        f"TMDB API error {response.status} for {media_type} ID {tmdb_id}"
                    )
    except Exception as e:
        logging.error(f"Error fetching TMDB trailer: {e}")

    return None


async def get_trailer_video_page_url(imdb_id: str) -> str | None:
    """Get the video page URL for a trailer from IMDb."""

    def find_trailer_in_page(soup: BeautifulSoup) -> str | None:
        trailer_spans = soup.find_all(
            "span",
            class_="ipc-lockup-overlay__text ipc-lockup-overlay__text--clamp-none",
        )
        logging.debug(f"Found {len(trailer_spans)} spans with video class")

        # First pass: look for trailers
        for span in trailer_spans:
            span_text = span.get_text(strip=True)
            logging.debug(f"Checking span text: {span_text}")
            if "Trailer" in span_text:
                parent_link = span.find_parent(
                    "a", href=lambda x: x and "/video/vi" in x
                )
                if parent_link:
                    video_page_url = f"https://www.imdb.com{parent_link['href']}"
                    logging.debug(f"Found trailer link: {video_page_url}")
                    return video_page_url

        # Second pass: look for clips if no trailer found
        for span in trailer_spans:
            span_text = span.get_text(strip=True)
            logging.debug(f"Checking span text: {span_text}")
            if "Clip" in span_text:
                parent_link = span.find_parent(
                    "a", href=lambda x: x and "/video/vi" in x
                )
                if parent_link:
                    video_page_url = f"https://www.imdb.com{parent_link['href']}"
                    logging.debug(f"Found clip link: {video_page_url}")
                    return video_page_url

        return None

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # First try ascending order (oldest first) to get original series trailer
            # For TV shows, this avoids getting season-specific trailers
            url = f"https://www.imdb.com/title/{imdb_id}/videogallery/?sort=date,asc"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    soup = BeautifulSoup(text, "html.parser")
                    video_page_url = find_trailer_in_page(soup)
                    if video_page_url:
                        return video_page_url

            # If no trailer found in ascending order, try descending order
            url = f"https://www.imdb.com/title/{imdb_id}/videogallery/?sort=date,desc"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    soup = BeautifulSoup(text, "html.parser")
                    video_page_url = find_trailer_in_page(soup)
                    if video_page_url:
                        return video_page_url

                    # If still no trailer found, look for first video longer than 30 seconds
                    video_links = soup.find_all(
                        "a", href=lambda x: x and "/video/vi" in x
                    )
                    logging.debug(f"Found {len(video_links)} video links")

                    for link in video_links:
                        # Get the duration from the parent div
                        parent_div = link.find_parent("div", class_="video-item")
                        if parent_div:
                            duration_text = parent_div.find(
                                "span", class_="video-duration"
                            )
                            if duration_text:
                                duration = duration_text.get_text(strip=True)
                                logging.debug(f"Found duration: {duration}")
                                # Parse duration (format: "X min Y sec")
                                minutes = 0
                                seconds = 0
                                if "min" in duration:
                                    minutes = int(duration.split("min")[0].strip())
                                if "sec" in duration:
                                    seconds = int(
                                        duration.split("sec")[0].strip().split()[-1]
                                    )
                                total_seconds = minutes * 60 + seconds
                                if total_seconds > 30:
                                    video_page_url = (
                                        f"https://www.imdb.com{link['href']}"
                                    )
                                    return video_page_url

        logging.warning(f"No suitable video found for {imdb_id}")
        return None
    except Exception as e:
        logging.error(f"Error fetching videos for {imdb_id}: {e}")
        return None


async def get_direct_video_url_from_page(video_page_url: str) -> str | None:
    """Extract direct video URL from IMDb video page."""
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                video_page_url, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status != 200:
                    logging.error(
                        f"Failed to fetch video page: {video_page_url} (status {response.status})"
                    )
                    return None
                text = await response.text()
                soup = BeautifulSoup(text, "html.parser")
                script_tag = soup.find(
                    "script", id="__NEXT_DATA__", type="application/json"
                )
                if not script_tag:
                    logging.error(
                        f"No __NEXT_DATA__ script tag found on page: {video_page_url}"
                    )
                    return None
                data = json.loads(script_tag.string)
                playback_urls = data["props"]["pageProps"]["videoPlaybackData"][
                    "video"
                ]["playbackURLs"]
                mp4_urls = [
                    item for item in playback_urls if item.get("videoMimeType") == "MP4"
                ]
                if mp4_urls:

                    def quality_key(item: dict[str, Any]) -> int:
                        if "1080" in item.get("videoDefinition", ""):
                            return 3
                        if "720" in item.get("videoDefinition", ""):
                            return 2
                        if "480" in item.get("videoDefinition", ""):
                            return 1
                        return 0

                    best = sorted(mp4_urls, key=quality_key, reverse=True)[0]
                    return best["url"] + f"#t={video_start_time}"
                if playback_urls:
                    return playback_urls[0]["url"] + f"#t={video_start_time}"
                logging.warning(
                    f"No playback URLs found in JSON on page: {video_page_url}"
                )
                return None
    except Exception as e:
        logging.error(f"Error parsing playback URLs from JSON: {e}")
        return None
