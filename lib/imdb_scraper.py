"""IMDb scraping module for extracting trailer URLs."""

import json
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from lib.config import headers, tmdb_api_key, video_start_time


def tmdb_to_imdb(tmdb_id: str) -> str | None:
    """Convert TMDB ID to IMDB ID using TMDB API. Try both as movie and TV show."""
    if not tmdb_api_key:
        logging.error(
            "TMDB_API_KEY not set. Please set it in the .env file or as an environment variable."
        )
        return None
    # Try as movie
    url_movie = f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
    try:
        response = requests.get(url_movie, timeout=10)
        if response.status_code == 200:
            data = response.json()
            imdb_id = data.get("imdb_id")
            if imdb_id and imdb_id.startswith("tt"):
                return imdb_id
        # Try as TV Shows if it fails
        url_tv = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
        response = requests.get(url_tv, timeout=10)
        if response.status_code == 200:
            data = response.json()
            imdb_id = data.get("imdb_id")
            if imdb_id and imdb_id.startswith("tt"):
                return imdb_id
        else:
            logging.error(
                f"TMDB API error {response.status_code} for TMDB ID {tmdb_id}"
            )
    except Exception as e:
        logging.error(f"Error converting TMDB->IMDB: {e}")
    return None


def get_trailer_video_page_url(imdb_id: str) -> str | None:
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
        # First try descending order (newest first) for trailers
        url = f"https://www.imdb.com/title/{imdb_id}/videogallery/?sort=date,desc"
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            video_page_url = find_trailer_in_page(soup)
            if video_page_url:
                return video_page_url

        # If no trailer found in descending order, try ascending order
        url = f"https://www.imdb.com/title/{imdb_id}/videogallery/?sort=date,asc"
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            video_page_url = find_trailer_in_page(soup)
            if video_page_url:
                return video_page_url

            # If still no trailer found, look for first video longer than 30 seconds
            video_links = soup.find_all("a", href=lambda x: x and "/video/vi" in x)
            logging.debug(f"Found {len(video_links)} video links")

            for link in video_links:
                # Get the duration from the parent div
                parent_div = link.find_parent("div", class_="video-item")
                if parent_div:
                    duration_text = parent_div.find("span", class_="video-duration")
                    if duration_text:
                        duration = duration_text.get_text(strip=True)
                        logging.debug(f"Found duration: {duration}")
                        # Parse duration (format: "X min Y sec")
                        minutes = 0
                        seconds = 0
                        if "min" in duration:
                            minutes = int(duration.split("min")[0].strip())
                        if "sec" in duration:
                            seconds = int(duration.split("sec")[0].strip().split()[-1])
                        total_seconds = minutes * 60 + seconds
                        if total_seconds > 30:
                            video_page_url = f"https://www.imdb.com{link['href']}"
                            return video_page_url

        logging.warning(f"No suitable video found for {imdb_id}")
        return None
    except Exception as e:
        logging.error(f"Error fetching videos for {imdb_id}: {e}")
        return None


def get_direct_video_url_from_page(video_page_url: str) -> str | None:
    """Extract direct video URL from IMDb video page."""
    try:
        response = requests.get(video_page_url, headers=headers, timeout=20)
        if response.status_code != 200:
            logging.error(
                f"Failed to fetch video page: {video_page_url} (status {response.status_code})"
            )
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
        if not script_tag:
            logging.error(
                f"No __NEXT_DATA__ script tag found on page: {video_page_url}"
            )
            return None
        data = json.loads(script_tag.string)
        playback_urls = data["props"]["pageProps"]["videoPlaybackData"]["video"][
            "playbackURLs"
        ]
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
        logging.warning(f"No playback URLs found in JSON on page: {video_page_url}")
        return None
    except Exception as e:
        logging.error(f"Error parsing playback URLs from JSON: {e}")
        return None
