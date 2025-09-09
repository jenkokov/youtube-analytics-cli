upd# YouTube Analytics CLI & Dashboard

A comprehensive tool for collecting YouTube Studio analytics data locally, with an interactive web dashboard for visualization and analysis.

## Prerequisites

- Python 3.8 or higher
- Google Cloud Console account

## Setup

### 1. Clone and navigate to the project
```bash
cd youtube-analytics-cli
```

### 2. Create and activate virtual environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up Google Cloud Console
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3** and **YouTube Analytics API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Choose **Desktop Application** as the application type
6. Download the credentials JSON file (optional - you can use environment variables instead)

### 5. Configure environment
```bash
# Copy the environment template
cp .env.example .env

# Edit .env file with your credentials
# You need to add your CLIENT_ID and CLIENT_SECRET from Google Cloud Console
```

Your `.env` file should look like:
```env
YOUTUBE_CLIENT_ID=your_client_id_here.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your_client_secret_here
DEFAULT_CHANNEL_ID=your_channel_id_here
```

### 6. Run initial setup
```bash
python -m src.youtube_analytics.cli setup
```

This will test authentication and guide you through the OAuth flow.

## Usage

### Get Channel Statistics
```bash
# Display stats in console
python -m src.youtube_analytics.cli channel-stats

# Save to CSV
python -m src.youtube_analytics.cli channel-stats --output csv

# Save to SQLite database
python -m src.youtube_analytics.cli channel-stats --output sqlite

# Specify a different channel ID
python -m src.youtube_analytics.cli channel-stats --channel-id UCxxxxxxxxxxxxxxxxx
```

### Get Video Statistics
```bash
# Get stats for all videos in your channel (default 25 videos)
python -m src.youtube_analytics.cli video-stats

# Get stats for a specific video
python -m src.youtube_analytics.cli video-stats --video-id dQw4w9WgXcQ

# Get more videos with verbose output
python -m src.youtube_analytics.cli video-stats --max-videos 50 -v

# Different output formats
python -m src.youtube_analytics.cli video-stats --output console
python -m src.youtube_analytics.cli video-stats --output csv
python -m src.youtube_analytics.cli video-stats --output sqlite

# Skip traffic source analytics (faster)
python -m src.youtube_analytics.cli video-stats --no-analytics
```

### Show and Episode Mapping
Map show names and episode numbers from video titles using regex patterns:

```bash
# View current patterns
python -m src.youtube_analytics.cli list-patterns

# Test a title against patterns
python -m src.youtube_analytics.cli test-pattern "DOU News #123"

# Preview what would be mapped (dry run)
python -m src.youtube_analytics.cli update-shows --dry-run

# Apply the mapping
python -m src.youtube_analytics.cli update-shows
```

Edit `config/show_patterns.yaml` to customize regex patterns for your shows.

## Interactive Dashboard 🎯

Launch a web-based dashboard for interactive data visualization and analysis:

```bash
# Recommended method (includes validation)
python run_dashboard.py

# Alternative direct launch
streamlit run streamlit_app.py
```

### Dashboard Features
- **📊 Interactive Charts**: Plotly-powered visualizations with zoom and hover
- **🎛️ Advanced Filters**: Show selector, episode range, and traffic source filters
- **📈 Trend Analysis**: 7-day rolling average overlay for performance tracking
- **📋 Summary Metrics**: KPI cards showing totals, averages, and growth rates
- **📥 Data Export**: CSV downloads for both video and traffic analytics
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices

### Dashboard Requirements
- Streamlit 1.32.0+ and Plotly 5.19.0+ (included in requirements.txt)
- YouTube data collected via CLI commands
- Show/episode mapping completed (for best experience)

### Command Options

#### `channel-stats` command:
- `--channel-id`: Specify a YouTube channel ID (optional if set in `.env`)
- `--output`: Choose output format: `console`, `csv`, or `sqlite`

#### `video-stats` command:
- `--video-id`: Get stats for a specific video ID
- `--channel-id`: Specify a YouTube channel ID (optional if set in `.env`)
- `--max-videos`: Maximum number of videos to process (default: 25)
- `--output`: Choose output format: `console`, `csv`, or `sqlite` (default: `sqlite`)
- `--include-analytics/--no-analytics`: Include traffic source data (default: enabled)
- `-v, --verbose`: Show detailed progress for each video

#### `update-shows` command:
- `--dry-run`: Preview changes without updating database
- `--verbose/--quiet`: Control output verbosity (default: verbose)
- `--config-file`: Use custom pattern configuration file

#### `list-patterns` command:
- `--config-file`: Use custom pattern configuration file

#### `test-pattern` command:
- `title`: Video title to test against patterns
- `--config-file`: Use custom pattern configuration file

#### Global options:
- `--config-dir`: Custom configuration directory (default: `config`)
- `--data-dir`: Custom data storage directory (default: `data`)

## Data Storage

Data is stored locally in:
- **SQLite Database**: `data/youtube_analytics.sqlite`
- **CSV Exports**: 
  - `data/exports/channel_stats.csv`
  - `data/exports/video_stats.csv`
  - `data/exports/traffic_sources.csv`
- **Configuration**: 
  - `config/token.pickle` (auth tokens)
  - `config/credentials.json` (auto-generated)
  - `config/show_patterns.yaml` (regex patterns for show mapping)

### Video Data Fields
Each video record includes:
- Video title, ID, and YouTube URL
- Upload time and duration (in seconds)
- View count, like count, dislike count, comment count
- Visibility status (public, private, unlisted)
- Show name and episode number (from regex mapping)
- Thumbnail URL (highest quality available)
- Short video detection (YouTube Shorts)
- Traffic source analytics (where views come from)
- Exclusion flag for filtering from reports

## Project Structure
```
youtube-analytics-cli/
├── src/youtube_analytics/
│   ├── __init__.py
│   ├── auth.py          # OAuth2 authentication
│   ├── cli.py           # Command-line interface  
│   ├── data_storage.py  # CSV/SQLite storage
│   ├── youtube_client.py # YouTube API client
│   └── show_mapper.py   # Show/episode regex mapping
├── config/              # Authentication and patterns (auto-created)
│   ├── show_patterns.yaml # Regex patterns for show mapping
│   ├── token.pickle     # OAuth tokens (auto-generated)
│   └── credentials.json # API credentials (auto-generated)
├── data/               # Local data storage (auto-created)
│   ├── youtube_analytics.sqlite # Main database
│   └── exports/        # CSV export files
├── streamlit_app.py    # Interactive web dashboard
├── run_dashboard.py    # Dashboard launcher script
├── venv/               # Virtual environment
├── requirements.txt    # Python dependencies
├── .env                # Your credentials (create from .env.example)
├── .env.example        # Template for environment variables
├── .gitignore
└── README.md
```

## Features

### Data Collection
✅ **Channel Statistics**: Subscriber count, total views, video count  
✅ **Video Statistics**: Individual video metrics with traffic sources  
✅ **Duration Tracking**: Video duration stored in seconds for analysis  
✅ **Thumbnail Collection**: Highest quality thumbnail URLs (maxres preferred)  
✅ **Visibility Tracking**: Public, private, unlisted status detection  
✅ **YouTube Shorts**: Automatic detection of short-form content  
✅ **Traffic Sources**: Where your views come from (search, suggested, etc.)  
✅ **Dislike Counts**: Available for authenticated video owners

## Quick Start Guide

1. **Setup**: Follow installation and authentication steps above
2. **Collect Data**: `python -m src.youtube_analytics.cli video-stats`
3. **Map Shows**: Edit `config/show_patterns.yaml` then run `update-shows`
4. **Launch Dashboard**: `python run_dashboard.py`
5. **Analyze**: Use interactive filters and export data as needed

## Troubleshooting

### Authentication Issues
- Make sure your `.env` file has the correct credentials
- Check that YouTube Data API v3 and YouTube Analytics API are enabled in Google Cloud Console
- Verify your OAuth2 client is configured for "Desktop Application"
- Add yourself as a test user if your app is in "Testing" mode

### Permission Errors
- Ensure you have read/write permissions in the project directory
- The tool will create `config/` and `data/` directories automatically

### Dashboard Issues
- **"No data available"**: Run `video-stats` command first to collect data
- **Empty dashboard**: Ensure videos have show/episode mapping completed
- **Port conflicts**: Dashboard runs on localhost:8501 by default
- **Streamlit not found**: Install dependencies with `pip install -r requirements.txt`

### Performance Notes
- Use `--no-analytics` flag to skip traffic source data for faster processing
- Use `-v` flag to monitor progress when processing many videos
- Database automatically handles updates - existing videos are refreshed with new stats
- Dashboard filters data in real-time - larger datasets may take longer to load