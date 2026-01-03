"""NFO file parsing module for extracting IMDb IDs from .nfo files."""

import logging
import os
import re
import xml.etree.ElementTree as ET


def parse_nfo_file(nfo_path: str) -> str | None:
    """Parse a .nfo file to extract IMDb ID.

    Supports both XML format and plain text with IMDb URLs.
    """
    try:
        with open(nfo_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try XML parsing first (Kodi/Plex format)
        try:
            root = ET.fromstring(content)

            # Look for <uniqueid type="imdb">
            for uniqueid in root.findall(".//uniqueid"):
                if uniqueid.get("type") == "imdb":
                    imdb_id = uniqueid.text
                    if imdb_id and imdb_id.startswith("tt"):
                        logging.debug(f"Found IMDb ID in XML uniqueid: {imdb_id}")
                        return imdb_id

            # Look for <imdb> or <imdbid> tags
            for tag in ["imdb", "imdbid", "id"]:
                element = root.find(f".//{tag}")
                if element is not None and element.text:
                    imdb_id = element.text.strip()
                    if imdb_id.startswith("tt"):
                        logging.debug(f"Found IMDb ID in XML {tag}: {imdb_id}")
                        return imdb_id
        except ET.ParseError:
            # Not valid XML, try text parsing
            pass

        # Try to find IMDb URL or ID in plain text
        # Pattern for IMDb URLs: https://www.imdb.com/title/tt1234567/
        url_match = re.search(r"imdb\.com/title/(tt\d+)", content, re.IGNORECASE)
        if url_match:
            imdb_id = url_match.group(1)
            logging.debug(f"Found IMDb ID in URL: {imdb_id}")
            return imdb_id

        # Pattern for plain IMDb ID: tt1234567
        id_match = re.search(r"\b(tt\d{7,})\b", content)
        if id_match:
            imdb_id = id_match.group(1)
            logging.debug(f"Found IMDb ID in text: {imdb_id}")
            return imdb_id

        logging.warning(f"No IMDb ID found in {nfo_path}")
        return None

    except Exception as e:
        logging.error(f"Error parsing NFO file {nfo_path}: {e}")
        return None


def find_nfo_file(directory: str) -> str | None:
    """Find a .nfo file in the given directory.

    Looks for common NFO file names used by media servers.
    """
    # Common NFO file patterns
    patterns = ["movie.nfo", "tvshow.nfo", "*.nfo"]

    try:
        for pattern in patterns:
            if pattern == "*.nfo":
                # Find any .nfo file
                for file in os.listdir(directory):
                    if file.lower().endswith(".nfo"):
                        nfo_path = os.path.join(directory, file)
                        logging.debug(f"Found NFO file: {nfo_path}")
                        return nfo_path
            else:
                nfo_path = os.path.join(directory, pattern)
                if os.path.exists(nfo_path):
                    logging.debug(f"Found NFO file: {nfo_path}")
                    return nfo_path

        logging.debug(f"No NFO file found in {directory}")
        return None

    except Exception as e:
        logging.error(f"Error finding NFO file in {directory}: {e}")
        return None


def get_imdb_from_nfo(directory: str) -> str | None:
    """Get IMDb ID from NFO file in directory."""
    nfo_file = find_nfo_file(directory)
    if nfo_file:
        return parse_nfo_file(nfo_file)
    return None
