# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a YouTube Analytics CLI tool that collects YouTube Studio analytics data locally for analysis. It's designed to gather channel and video statistics, store them in SQLite databases or CSV files, and prepare data for Jupyter notebook analysis.

## Development Commands

### Environment Setup
```bash
# Install dependencies and create virtual environment (using uv)
uv sync

# Initial setup and authentication test
uv run python -m src.youtube_analytics.cli setup
# Or use the console script entry point
uv run youtube-analytics setup
```

**Legacy setup (if not using uv)**:
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Initial setup and authentication test
python -m src.youtube_analytics.cli setup
```

### Running the CLI
```bash
# Basic channel statistics
uv run youtube-analytics channel-stats

# Video statistics with pagination support
uv run youtube-analytics video-stats --max-videos 500 -v

# Specific video analysis
uv run youtube-analytics video-stats --video-id dQw4w9WgXcQ

# Different output formats
uv run youtube-analytics video-stats --output sqlite
uv run youtube-analytics video-stats --output csv
uv run youtube-analytics video-stats --output console

# Show and episode mapping
uv run youtube-analytics update-shows --dry-run  # Preview changes
uv run youtube-analytics update-shows           # Apply changes
uv run youtube-analytics list-patterns          # View regex patterns
uv run youtube-analytics test-pattern "DOU News #123"  # Test title

# Caption downloads (default: plain text transcripts)
uv run youtube-analytics download-captions --video-ids 'abc123,def456' -v
uv run youtube-analytics download-captions --video-ids 'abc123' --format vtt  # VTT with timestamps
uv run youtube-analytics download-captions --video-ids 'abc123' --output-dir exports/captions

# Interactive dashboard
uv run python run_dashboard.py                  # Launch Streamlit dashboard
uv run streamlit run streamlit_app.py           # Alternative launch method
```

**Alternative: using module syntax**
```bash
uv run python -m src.youtube_analytics.cli <command>
```

### Authentication Setup
```bash
# Copy environment template and configure
cp .env.example .env
# Edit .env with YouTube API credentials
```

## Architecture Overview

### Core Components

**`cli.py`** - Click-based command-line interface with main commands:
- `channel-stats`: Collects basic channel metrics (subscribers, views, video count)
- `video-stats`: Collects detailed video statistics with pagination support for large datasets
- `update-shows`: Maps show names and episode numbers using regex patterns from config
- `list-patterns`: Shows all configured regex patterns for show/episode mapping
- `test-pattern`: Tests a video title against all configured patterns
- `download-captions`: Downloads captions for specified videos in various formats

**`auth.py`** - OAuth2 authentication handler:
- Manages Google Cloud Console credentials via environment variables or JSON files
- Handles token caching with separate files for different scope modes
- Supports both YouTube Data API v3 and YouTube Analytics API scopes (readonly mode)
- Supports YouTube Captions API with youtube.force-ssl scope (captions mode)

**`youtube_client.py`** - YouTube API client wrapper:
- Implements pagination for large video collections (auto-handles 50-video API limits)
- Converts ISO 8601 durations to seconds for database storage
- Fetches video categories and detects draft status
- Collects traffic source analytics (where views originate)

**`data_storage.py`** - Data persistence layer:
- SQLite database with automatic schema migrations
- Upsert logic for video updates (existing videos get refreshed stats)
- Dual storage: SQLite for analysis, CSV for spreadsheet export
- Database structure: `channel_stats`, `video_stats`, `traffic_sources` tables

**`show_mapper.py`** - Show/episode mapping system:
- Loads regex patterns from YAML configuration files
- Extracts show names and episode numbers from video titles
- Updates database with mapped show/episode information
- Provides dry-run mode and detailed processing statistics

**`caption_downloader.py`** - Caption download system:
- Downloads auto-generated or manual captions from YouTube videos
- Supports multiple formats: TXT (plain text - default), VTT, SRT, SBV
- Extracts clean transcripts without timing information for text analysis
- Sanitizes video titles for filesystem compatibility
- Batch processing with detailed progress tracking and error handling
- Owner-only restriction (YouTube API limitation)

**`streamlit_app.py`** - Interactive web dashboard:
- Streamlit-based web application for data visualization
- Interactive controls for show selection and episode range filtering  
- Stacked bar charts with traffic source breakdown
- 7-day rolling average overlay for trend analysis
- Summary metrics and CSV export functionality

### Data Flow Architecture

1. **Authentication**: OAuth2 flow creates cached tokens in `config/`
2. **API Collection**: YouTube client fetches data with automatic pagination
3. **Data Processing**: Duration conversion, visibility status detection, show/episode mapping
4. **Storage**: Upsert to SQLite database at `data/youtube_analytics.sqlite`
5. **Export**: Optional CSV exports to `data/exports/` directory

### Database Schema Design

**video_stats table**:
- Stores duration as INTEGER (seconds) for mathematical analysis
- Includes nullable category (TEXT) and draft status (BOOLEAN)
- Uses `last_updated` timestamp for tracking data freshness
- UNIQUE constraint on video_id enables upsert operations

**traffic_sources table**:
- Foreign key relationship to video_stats
- Captures analytics data on view origins (search, suggested, etc.)
- Refreshed on each video update

### Key Technical Decisions

**Pagination Implementation**: Handles YouTube's 50-video API limit transparently, allowing requests for hundreds/thousands of videos with progress tracking.

**Duration Storage**: ISO 8601 format (PT4M13S) converted to seconds for database storage, human-readable format for display.

**Authentication Strategy**: Environment variables preferred over JSON files for easier deployment, with automatic credential file generation.

**Data Migration**: Automatic schema updates preserve existing data when adding new fields.

**Error Handling**: Individual video failures don't stop batch processing, with verbose mode showing detailed progress.

## Configuration

**Environment Variables** (`.env`):
- `YOUTUBE_CLIENT_ID`: OAuth2 client ID from Google Cloud Console
- `YOUTUBE_CLIENT_SECRET`: OAuth2 client secret
- `DEFAULT_CHANNEL_ID`: Optional default channel for operations

**Required APIs**: Enable both YouTube Data API v3 and YouTube Analytics API in Google Cloud Console.

**OAuth Setup**: Desktop application type, add authenticated user as test user if app is in "Testing" mode.

## Show/Episode Mapping

The system supports automatic mapping of show names and episode numbers using regex patterns configured in YAML files.

### Configuration
**Show Patterns** (`config/show_patterns.yaml`):
```yaml
show_patterns:
  - name: "DOU News"
    title_regex: "(?i)dou\\s+news"
    episode_regex: "(?i)dou\\s+news.*#?(\\d+)"
    episode_group: 1
    enabled: true
```

### Pattern Options
- `name`: Show name to assign when pattern matches
- `title_regex`: Pattern to match video titles
- `episode_regex`: Pattern to extract episode numbers (optional)
- `show_group`: Regex group containing show name (if extracting from title)
- `episode_group`: Regex group containing episode number
- `enabled`: Whether pattern is active

### Processing Options
- `update_only_empty`: Only update videos with NULL show/episode fields
- `max_videos`: Limit processing to N videos (0 = no limit)
- `dry_run`: Preview mode without database changes
- `verbose`: Show detailed progress output

## Caption Downloads

The system supports downloading captions (subtitles) from YouTube videos using the YouTube Data API v3 Captions endpoint.

### Features
- **Batch Downloads**: Download captions for multiple videos at once using comma-separated IDs
- **Multiple Formats**: Support for plain text (TXT), VTT (WebVTT), SRT (SubRip), and SBV formats
- **Plain Text Default**: By default, downloads clean transcripts without timing information (ideal for analysis)
- **Language Selection**: Target specific languages (default: Ukrainian 'uk')
- **Auto-Generated Captions**: Downloads ASR (automatic speech recognition) captions
- **Smart Filename Handling**: Sanitizes video titles and includes video ID for uniqueness
- **Progress Tracking**: Verbose mode shows detailed progress for each video

### Usage
```bash
# Download Ukrainian transcripts for multiple videos (plain text - default)
uv run youtube-analytics download-captions --video-ids 'abc123,def456,ghi789' -v

# Download with timestamps in VTT format
uv run youtube-analytics download-captions --video-ids 'abc123' --format vtt

# Download in SRT format
uv run youtube-analytics download-captions --video-ids 'abc123' --format srt

# Download captions in different language
uv run youtube-analytics download-captions --video-ids 'abc123' --language en

# Custom output directory
uv run youtube-analytics download-captions --video-ids 'abc123' --output-dir exports/captions
```

### Authentication
Caption downloads require **separate authentication** with the `youtube.force-ssl` scope, which grants broader permissions than the standard readonly scope. You will be prompted to authenticate when running the caption download command for the first time. This creates a separate token file (`config/token_captions.pickle`) that is used exclusively for caption operations.

### Important Limitations
- **Owner-Only Access**: You can only download captions from videos you own (YouTube API restriction)
- **Caption Availability**: Not all videos have auto-generated captions in all languages
- **API Quota**: Caption downloads count toward your YouTube API quota

### File Naming Convention
Downloaded caption files follow this pattern:
```
{sanitized_video_title}_{video_id}.{format}
```

For example:
- `My_Video_Title_abc123xyz.txt` (plain text transcript - default)
- `My_Video_Title_abc123xyz.vtt` (with timestamps)
- `DOU_News_Episode_42_def456uvw.srt` (SubRip format)

Special characters in video titles (`/ \ : * ? " < > |`) are replaced with underscores, and titles are truncated to 200 characters if necessary.

### Format Details

**TXT (Plain Text) - Default**:
- Clean transcript without timing information
- Ideal for text analysis, translation, or content review
- Smaller file size compared to formatted captions
- Extracts only the spoken text from the video

**VTT (WebVTT)**:
- Includes timestamps for each caption segment
- Web-standard format for video players
- Contains timing information: `00:00:01.000 --> 00:00:03.500`

**SRT (SubRip)** and **SBV (YouTube)**:
- Alternative formats with timing information
- Compatible with various video editing tools

### Error Handling
The tool handles various error scenarios gracefully:
- **No Captions Available**: Skips the video and continues with others
- **Permission Denied**: Shows clear message about owner-only restriction
- **Already Downloaded**: Skips existing files (no overwrite by default)
- **Network Errors**: Reports failures but continues batch processing

## Interactive Dashboard

The system includes a web-based dashboard built with Streamlit for interactive data visualization and analysis.

### Features
- **Show Selection**: Dropdown to choose which show to analyze
- **Episode Range Filter**: Slider to select specific episode ranges
- **Traffic Source Breakdown**: Stacked bar chart showing views by traffic source
- **Rolling Average**: 7-day rolling average trend line overlay
- **Summary Metrics**: Key performance indicators (KPIs) cards
- **Data Export**: CSV download for both video and traffic data
- **Responsive Design**: Works on desktop and mobile devices

### Launch Dashboard
```bash
# Recommended method (includes checks)
uv run python run_dashboard.py

# Direct method
uv run streamlit run streamlit_app.py
```

### Dashboard Components
1. **Sidebar Controls**: Show selector and episode range slider
2. **Metrics Cards**: Total episodes, views, averages, and growth
3. **Main Chart**: Interactive Plotly visualization with traffic source breakdown
4. **Data Table**: Expandable table showing detailed episode information
5. **Export Section**: CSV download buttons for data analysis

### Requirements
- Streamlit 1.32.0+
- Plotly 5.19.0+ 
- Valid database with show/episode data mapped
- Videos must not be excluded from stats (`exclude_from_stats = 0`)

## Data Storage Locations

- **Database**: `data/youtube_analytics.sqlite`
- **CSV Exports**: `data/exports/*.csv`
- **Captions**: `data/captions/*.txt` (plain text transcripts - default), or `*.vtt`, `*.srt`, `*.sbv` (with timestamps)
- **Auth Tokens**: `config/token.pickle` (analytics), `config/token_captions.pickle` (caption downloads)
- **Credentials**: `config/credentials.json` (auto-generated from env vars)
- **Show Patterns**: `config/show_patterns.yaml`