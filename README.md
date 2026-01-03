<div align="center">
  <a href="https://github.com/Pukabyte/trailerfin">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/logo.png" width="400">
      <img alt="trailerfin" src="assets/logo.png" width="400">
    </picture>
  </a>
</div>

<div align="center">
  <a href="https://github.com/Pukabyte/trailerfin/stargazers"><img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/Pukabyte/trailerfin?label=Trailerfin"></a>
  <a href="https://github.com/Pukabyte/trailerfin/issues"><img alt="Issues" src="https://img.shields.io/github/issues/Pukabyte/trailerfin" /></a>
  <a href="https://github.com/Pukabyte/trailerfin/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/Pukabyte/trailerfin"></a>
  <a href="https://github.com/Pukabyte/trailerfin/graphs/contributors"><img alt="Contributors" src="https://img.shields.io/github/contributors/Pukabyte/trailerfin" /></a>
  <a href="https://discord.gg/vMSnNcd7m5"><img alt="Discord" src="https://img.shields.io/badge/Join%20discord-8A2BE2" /></a>
</div>

<div align="center">
  <p>Automatically manage IMDb trailers for your media library.</p>
</div>

# Trailerfin

Trailerfin is a powerful tool for automatically retrieving and refreshing IMDb trailer links for your media library as backdrop videos. By default, it creates `.strm` files that Jellyfin/Plex can use to stream trailers, or it can download trailers locally as `trailer.mp4` files. It intelligently tracks link expiration times and only updates when necessary.

Built with modern async architecture using `aiohttp` and `asyncio`, Trailerfin offers multi-language support, multi-directory scanning, NFO file parsing, and flexible concurrency control for efficient processing of large media libraries.

## Features
- 🎬 Automatically find and download trailers from IMDb for your movie collection
- 🔄 Scheduled refresh of trailer links before they expire
- 🎯 Smart expiration tracking with configurable refresh windows
- 🚫 Ignore list for movies without trailers
- 📊 Detailed logging with expiration time tracking
- 🐳 Docker support for easy deployment
- 🔔 Continuous monitoring mode for new media detection
- 🕒 Automatic expiration checking
- 🎥 Prioritizes trailers over clips
- 📝 JSON-based ignore list for easy management
- 🌍 Multi-language trailer support (via TMDB API)
- 💾 Download mode: save trailers as `trailer.mp4` instead of `.strm` files
- 📁 Multi-directory scanning: monitor multiple media libraries simultaneously
- 📋 NFO file parsing: extract IMDb IDs from Kodi/Plex `.nfo` files
- ⚡ Async architecture with aiohttp for improved performance
- 🎚️ Configurable worker concurrency for parallel processing
- 📏 Test mode with `--limit` to process a specific number of folders
- 📊 Real-time progress bar with Click

## Requirements
- Python 3.11+
- Docker (recommended)
- IMDb IDs in your media folder structure (e.g., `Movie Name (2023) [imdb-tt1234567]`) or `.nfo` files with IMDb IDs
- TMDB API key (for multi-language trailer support) - Get one at [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- `yt-dlp` (automatically installed via requirements.txt) - For downloading YouTube trailers in multiple languages
- **For `.strm` mode only** (default): Theme videos must be enabled in Jellyfin/Plex (Settings > Display > Libraries per device)
- **For `--download` mode**: No special configuration needed - trailers are saved as `trailer.mp4` files
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/trailerfin.png">
      <img alt="trailerfin" src="assets/trailerfin.png">
    </picture>

## Setup

### 1. Clone the repository
```sh
git clone https://github.com/Pukabyte/trailerfin.git
cd trailerfin
```

### 2. Configure Environment Variables
Copy the example environment file and configure it:

```sh
cp .env.example .env
```

Edit the `.env` file with your settings:

```env
SCAN_PATH=/path/to/your/media
VIDEO_FILENAME=trailer.strm
WORKERS=4
VIDEO_START_TIME=10
SCHEDULE_DAYS=7
TMDB_API_KEY=your_tmdb_api_key_here
TRAILER_LANGUAGE=en
```

**Environment Variables:**

- `SCAN_PATH`: Directory to scan for IMDb IDs (can be overridden with `--dir` CLI option)
- `VIDEO_FILENAME`: Name of the .strm file to create (default: `trailer.strm`)
- `WORKERS`: Number of concurrent workers for parallel processing (default: 4)
- `VIDEO_START_TIME`: Start time in seconds for the video (default: 10, skips intros/ads)
- `SCHEDULE_DAYS`: Interval in days for scheduled scans (default: 7)
- `TMDB_API_KEY`: Your TMDB API key - **Required for multi-language support**. Get a free key at [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- `TRAILER_LANGUAGE`: Default language for trailers as ISO 639-1 code (default: `en`)

> **Note:** Without a TMDB API key, Trailerfin will fall back to IMDb scraping which only supports English trailers.

### 3. Build and Run with Docker

#### Build the Docker image
```sh
docker build -t trailerfin .
```

#### Run the container
```sh
docker run --env-file .env -v /path/to/your/media:/mnt/plex trailerfin
```

### 4. Using Docker Compose

A sample `docker-compose.yml` is provided:

```yaml
services:
  trailerfin:
    build: .
    container_name: trailerfin
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
    volumes:
      - /mnt:/mnt # Make sure this directory is where your content can be found in
      - /opt/trailerfin:/app
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
```

Start with:
```sh
docker-compose up -d
```

## Usage

### Basic Manual Run
Scan a single directory:
```sh
python trailerfin.py --dir /path/to/your/media
```

### Multi-Directory Scanning
Scan multiple directories simultaneously:
```sh
python trailerfin.py --dir /path/to/movies --dir /path/to/tv --dir /path/to/documentaries
```

### Download Mode
Download trailers as `trailer.mp4` files instead of creating `.strm` files:
```sh
python trailerfin.py --dir /path/to/your/media --download
```

### Multi-Language Support
Fetch trailers in a specific language (ISO 639-1 code):
```sh
python trailerfin.py --dir /path/to/your/media --language fr
```

### NFO File Parsing
Extract IMDb IDs from `.nfo` files (Kodi/Plex format) instead of folder names:
```sh
python trailerfin.py --dir /path/to/your/media --use-nfo
```

### Worker Concurrency
Control the number of concurrent workers for parallel processing:
```sh
python trailerfin.py --dir /path/to/your/media --workers 8
```

### Test Mode with Limit
Process only a specific number of folders (useful for testing):
```sh
python trailerfin.py --dir /path/to/your/media --limit 10
```

### Force Refresh
Force download/refresh trailers even if they already exist:
```sh
python trailerfin.py --dir /path/to/your/media --force
```
Useful when:
- You want to update all trailers to a different language
- You want to replace existing trailers with newer versions
- You've deleted the ignore list and want to retry all folders

### Continuous Monitoring Mode (Recommended)
```sh
python trailerfin.py --dir /path/to/your/media --monitor
```
This mode will:
- Continuously monitor for new media
- Check for expiring links
- Automatically refresh links before they expire
- Skip movies without trailers
- Run in the background

### Scheduled Refresh Mode
Run on a scheduled interval:
```sh
python trailerfin.py --dir /path/to/your/media --schedule
```

### Combined Options Example
Multi-directory, multi-language, download mode with NFO parsing:
```sh
python trailerfin.py \
  --dir /path/to/movies \
  --dir /path/to/tv \
  --language fr \
  --download \
  --use-nfo \
  --workers 8
```

## CLI Options Reference

All available command-line options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dir` | Multiple | From `.env` | Directory paths to scan (can be specified multiple times) |
| `--workers` | Integer | 4 | Number of concurrent workers for parallel processing |
| `--schedule` | Flag | False | Run scheduled refresh at configured intervals |
| `--monitor` | Flag | False | Continuous monitoring mode for new media and expiring links |
| `--use-nfo` | Flag | False | Extract IMDb IDs from `.nfo` files instead of folder names |
| `--limit` | Integer | None | Process only N folders (useful for testing) |
| `--download` | Flag | False | Download trailers as `trailer.mp4` instead of creating `.strm` files |
| `--language` | String | `en` | Language code (ISO 639-1) for TMDB trailers (e.g., `fr`, `es`, `de`) |
| `--force` | Flag | False | Force download/refresh even if trailer already exists |

Example with all options:
```sh
python trailerfin.py \
  --dir /movies \
  --dir /tv \
  --workers 8 \
  --language fr \
  --download \
  --use-nfo \
  --limit 50 \
  --force \
  --monitor
```

## Features in Detail

### Download Mode
By default, Trailerfin creates `.strm` files that contain URLs to IMDb trailers. With the `--download` flag, it will instead download the trailer video and save it as `trailer.mp4` in each movie folder. This is useful for offline access or when you prefer to store trailers locally.

**Technical details:**
- IMDb trailers (English): Downloaded directly via HTTP
- YouTube trailers (TMDB multi-language): Downloaded using `yt-dlp`
- Full multi-language support in download mode

**Automatic fallback:**
- If a YouTube trailer is unavailable (region-blocked, deleted, etc.), Trailerfin automatically falls back to IMDb (English)
- This ensures you always get a trailer when available, even if the preferred language version is unavailable

### Multi-Language Trailers
Using the `--language` option with a valid ISO 639-1 language code (e.g., `fr`, `es`, `de`), Trailerfin will fetch trailers in the specified language via the TMDB API. This feature requires a valid `TMDB_API_KEY` in your `.env` file.

**Important notes:**
- The TMDB API key is validated at startup to ensure multi-language support works correctly
- Without a valid TMDB API key, Trailerfin automatically falls back to IMDb scraping (English only)
- For TV shows, Trailerfin intelligently filters out season-specific trailers to retrieve the original series trailer
- Multi-language support works in both `.strm` and `--download` modes (uses `yt-dlp` for YouTube downloads)

Supported language codes include:
- `en` - English (default)
- `fr` - French
- `es` - Spanish
- `de` - German
- `it` - Italian
- `ja` - Japanese
- And many more...

### NFO File Parsing
With the `--use-nfo` flag, Trailerfin will look for `.nfo` files in each folder and extract the IMDb ID from them. This is particularly useful if you use Kodi or Plex, which store metadata in `.nfo` files. Trailerfin supports both XML-based and plain-text NFO formats.

**TV Show handling:**
- For TV shows, Trailerfin automatically detects season folders (Season 01, Saison 02, etc.)
- It searches for the `tvshow.nfo` file in the parent directory (series root)
- This ensures the trailer is placed at the series level, not in individual season folders

### Multi-Directory Scanning
You can specify multiple `--dir` options to scan multiple directories simultaneously. This is ideal if you have separate libraries for movies, TV shows, documentaries, etc. Each directory will be processed in parallel, respecting the worker concurrency limit.

### Worker Concurrency
The `--workers` option controls how many folders are processed concurrently using Python's asyncio. The default is 4 workers, but you can increase this for faster processing on powerful systems or decrease it to reduce system load.

### Async Architecture
Trailerfin uses `aiohttp` for async HTTP requests and `asyncio` for concurrent processing. This provides significant performance improvements over synchronous implementations, especially when processing large media libraries.

### Ignore List
- Automatically maintains a list of movies without trailers
- Prevents repeated attempts to fetch non-existent trailers
- Stored in `ignored_titles.json`
- Can be manually edited to retry specific movies

### Video Prioritization
- Prioritizes trailers over clips
- Falls back to clips if no trailer is available
- Ensures best quality video content

### Expiration Management
- Tracks expiration times for all links
- Shows remaining time in minutes and seconds
- Automatically refreshes links before they expire
- Maintains state between runs

## Logging
Logs are output to stdout and can be viewed with Docker logs or Compose logs. The logging includes:
- Link expiration times in readable format
- New media detection
- Ignored titles
- Processing progress with real-time progress bar
- Async task execution details
- Multi-directory scanning progress
- Language-specific trailer retrieval status
- Error handling and troubleshooting information

## Architecture

Trailerfin uses a modern async architecture for optimal performance:
- **aiohttp**: Async HTTP client for non-blocking API requests
- **asyncio**: Concurrent task execution with Semaphore-based worker pool
- **Click**: Modern CLI framework with rich option handling
- **Real-time progress**: Progress bar updates as tasks complete
- **Modular design**: Organized into logical modules (scanner, file_manager, imdb_scraper, nfo_parser, cache, config)

## License
MIT License 