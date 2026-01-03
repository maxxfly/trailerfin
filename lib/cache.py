"""Cache management module for expiration times and ignored titles."""

import json
import logging
from pathlib import Path
from typing import Any


def save_expiration_times(expiration_times: dict[str, int]) -> None:
    """Save expiration times to cache file."""
    cache_file = Path("trailer_expirations.json")
    try:
        with open(cache_file, "w") as f:
            json.dump(expiration_times, f)
    except Exception as e:
        logging.error(f"Error saving expiration times: {e}")


def load_expiration_times() -> dict[str, int]:
    """Load expiration times from cache file."""
    cache_file = Path("trailer_expirations.json")
    try:
        if cache_file.exists():
            with open(cache_file, "r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading expiration times: {e}")
    return {}


def load_ignored_titles() -> dict[str, Any]:
    """Load the list of ignored titles from a JSON file."""
    ignore_file = Path("ignored_titles.json")
    try:
        if ignore_file.exists():
            with open(ignore_file, "r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading ignored titles: {e}")
    return {}


def save_ignored_titles(ignored_titles: dict[str, Any]) -> None:
    """Save the list of ignored titles to a JSON file."""
    ignore_file = Path("ignored_titles.json")
    try:
        with open(ignore_file, "w") as f:
            json.dump(ignored_titles, f)
    except Exception as e:
        logging.error(f"Error saving ignored titles: {e}")
