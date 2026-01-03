#!/usr/bin/env python3
"""Quick test script to verify the download functionality."""

import logging
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from lib.file_manager import download_trailer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_download():
    """Test the download_trailer function with a small test file."""
    # This is just a test URL - in real usage, this would be from IMDb
    test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    test_folder = "/tmp/test_trailer_download"

    # Create test folder
    os.makedirs(test_folder, exist_ok=True)

    # Test download
    logging.info(f"Testing download to: {test_folder}")
    success = download_trailer(test_folder, test_url)

    if success:
        trailer_path = os.path.join(test_folder, "trailer.mp4")
        if os.path.exists(trailer_path):
            size = os.path.getsize(trailer_path)
            logging.info(f"✓ Download successful! File size: {size} bytes")
            # Clean up
            os.remove(trailer_path)
            os.rmdir(test_folder)
            return True
        else:
            logging.error("✗ File not found after download")
            return False
    else:
        logging.error("✗ Download failed")
        return False


if __name__ == "__main__":
    success = test_download()
    sys.exit(0 if success else 1)
