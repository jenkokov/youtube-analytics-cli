#!/usr/bin/env python3
"""
YouTube Analytics Dashboard Launcher

This script launches the Streamlit dashboard for YouTube analytics visualization.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Launch the Streamlit dashboard"""
    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Check if data directory exists
    data_dir = script_dir / "data"
    if not data_dir.exists():
        print("⚠️  Data directory not found!")
        print("Please run the CLI tool first to collect YouTube data:")
        print("python -m src.youtube_analytics.cli video-stats")
        return
    
    # Check if database exists
    db_path = data_dir / "youtube_analytics.sqlite"
    if not db_path.exists():
        print("⚠️  Database not found!")
        print("Please run the CLI tool first to collect YouTube data:")
        print("python -m src.youtube_analytics.cli video-stats")
        return
    
    print("🚀 Starting YouTube Analytics Dashboard...")
    print("📊 Dashboard will open in your default browser")
    print("🔗 Access URL: http://localhost:8501")
    print("\n💡 Press Ctrl+C to stop the dashboard\n")
    
    try:
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
            "--server.headless", "false",
            "--server.port", "8501",
            "--server.address", "localhost"
        ])
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped.")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")

if __name__ == "__main__":
    main()