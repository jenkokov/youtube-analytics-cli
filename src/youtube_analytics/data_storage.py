import sqlite3
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

class DataStorage:
    def __init__(self, data_dir='data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / 'youtube_analytics.sqlite'
        self.exports_dir = self.data_dir / 'exports'
        self.exports_dir.mkdir(exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            
            # Channel stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channel_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    subscriber_count INTEGER,
                    view_count INTEGER,
                    video_count INTEGER,
                    published_at TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Video stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL UNIQUE,
                    channel_id TEXT,
                    title TEXT,
                    description TEXT,
                    upload_time TEXT,
                    duration INTEGER,
                    watch_url TEXT,
                    view_count INTEGER,
                    like_count INTEGER,
                    dislike_count INTEGER,
                    comment_count INTEGER,
                    visibility TEXT DEFAULT NULL,
                    is_short BOOLEAN DEFAULT FALSE,
                    show TEXT DEFAULT NULL,
                    episode_num INTEGER DEFAULT NULL,
                    thumbnail_url TEXT DEFAULT NULL,
                    exclude_from_stats INTEGER DEFAULT 0,
                    tags TEXT DEFAULT NULL,
                    subscriber_count INTEGER DEFAULT NULL,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Add new columns to existing table if they don't exist
            cursor.execute("PRAGMA table_info(video_stats)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'tags' not in columns:
                cursor.execute('ALTER TABLE video_stats ADD COLUMN tags TEXT DEFAULT NULL')

            if 'subscriber_count' not in columns:
                cursor.execute('ALTER TABLE video_stats ADD COLUMN subscriber_count INTEGER DEFAULT NULL')
            
            # Traffic source analytics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS traffic_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    traffic_source TEXT,
                    views INTEGER,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES video_stats (video_id)
                )
            ''')
            
            # Analytics data table (for future use)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT,
                    metric TEXT,
                    date TEXT,
                    value INTEGER,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    
    def save_channel_stats_csv(self, stats):
        """Save channel stats to CSV file"""
        df = pd.DataFrame([stats])
        df['collected_at'] = datetime.now()
        
        csv_path = self.exports_dir / 'channel_stats.csv'
        
        # Append to existing file or create new one
        if csv_path.exists():
            df.to_csv(csv_path, mode='a', header=False, index=False)
        else:
            df.to_csv(csv_path, index=False)
        
        return csv_path
    
    def save_channel_stats_db(self, stats):
        """Save channel stats to SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO channel_stats 
                (channel_id, title, description, subscriber_count, view_count, video_count, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                stats['channel_id'],
                stats['title'],
                stats.get('description', ''),
                stats['subscriber_count'],
                stats['view_count'],
                stats['video_count'],
                stats['published_at']
            ))
            conn.commit()
    
    def get_channel_stats_history(self, channel_id=None):
        """Get historical channel stats from database"""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM channel_stats"
            params = ()
            
            if channel_id:
                query += " WHERE channel_id = ?"
                params = (channel_id,)
            
            query += " ORDER BY collected_at DESC"
            
            df = pd.read_sql_query(query, conn, params=params)
            return df
    
    def export_to_csv(self, table_name, filename=None):
        """Export any table to CSV"""
        if not filename:
            filename = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        csv_path = self.exports_dir / filename
        
        with sqlite3.connect(self.db_path) as conn:
            if table_name == 'video_stats':
                df = pd.read_sql_query(f"SELECT * FROM {table_name} WHERE exclude_from_stats = 0", conn)
            else:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            df.to_csv(csv_path, index=False)
        
        return csv_path
    
    def get_database_info(self):
        """Get information about the database tables and record counts"""
        info = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                info[table_name] = count
        
        return info
    
    def save_video_stats_db(self, video_stats, traffic_sources=None):
        """Save or update video stats to SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if video exists
            cursor.execute("SELECT id FROM video_stats WHERE video_id = ?", (video_stats['video_id'],))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing video
                cursor.execute('''
                    UPDATE video_stats
                    SET channel_id = ?, title = ?, description = ?, upload_time = ?,
                        duration = ?, watch_url = ?, view_count = ?, like_count = ?,
                        dislike_count = ?, comment_count = ?, visibility = ?, is_short = ?, thumbnail_url = ?,
                        tags = ?, subscriber_count = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                ''', (
                    video_stats['channel_id'],
                    video_stats['title'],
                    video_stats.get('description', ''),
                    video_stats['upload_time'],
                    video_stats['duration_seconds'],
                    video_stats['watch_url'],
                    video_stats['view_count'],
                    video_stats['like_count'],
                    video_stats.get('dislike_count', 0),
                    video_stats['comment_count'],
                    video_stats.get('visibility'),
                    video_stats.get('is_short', False),
                    video_stats.get('thumbnail_url'),
                    video_stats.get('tags'),
                    video_stats.get('subscriber_count'),
                    video_stats['video_id']
                ))
            else:
                # Insert new video
                cursor.execute('''
                    INSERT INTO video_stats
                    (video_id, channel_id, title, description, upload_time, duration,
                     watch_url, view_count, like_count, dislike_count, comment_count, visibility, is_short, thumbnail_url, tags, subscriber_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video_stats['video_id'],
                    video_stats['channel_id'],
                    video_stats['title'],
                    video_stats.get('description', ''),
                    video_stats['upload_time'],
                    video_stats['duration_seconds'],
                    video_stats['watch_url'],
                    video_stats['view_count'],
                    video_stats['like_count'],
                    video_stats.get('dislike_count', 0),
                    video_stats['comment_count'],
                    video_stats.get('visibility'),
                    video_stats.get('is_short', False),
                    video_stats.get('thumbnail_url'),
                    video_stats.get('tags'),
                    video_stats.get('subscriber_count')
                ))
            
            # Save traffic sources if provided
            if traffic_sources:
                # Delete existing traffic sources for this video
                cursor.execute("DELETE FROM traffic_sources WHERE video_id = ?", (video_stats['video_id'],))
                
                # Insert new traffic sources
                for source, views in traffic_sources.items():
                    cursor.execute('''
                        INSERT INTO traffic_sources (video_id, traffic_source, views)
                        VALUES (?, ?, ?)
                    ''', (video_stats['video_id'], source, views))
            
            conn.commit()
    
    def save_video_stats_csv(self, video_stats, traffic_sources=None):
        """Save video stats to CSV file"""
        # Skip if video is excluded from stats
        if video_stats.get('exclude_from_stats', 0) == 1:
            return None
            
        df = pd.DataFrame([video_stats])
        df['collected_at'] = datetime.now()
        
        csv_path = self.exports_dir / 'video_stats.csv'
        
        # Append to existing file or create new one
        if csv_path.exists():
            df.to_csv(csv_path, mode='a', header=False, index=False)
        else:
            df.to_csv(csv_path, index=False)
        
        # Save traffic sources to separate CSV if provided
        if traffic_sources:
            traffic_df = pd.DataFrame([
                {
                    'video_id': video_stats['video_id'],
                    'traffic_source': source,
                    'views': views,
                    'collected_at': datetime.now()
                }
                for source, views in traffic_sources.items()
            ])
            
            traffic_csv_path = self.exports_dir / 'traffic_sources.csv'
            if traffic_csv_path.exists():
                traffic_df.to_csv(traffic_csv_path, mode='a', header=False, index=False)
            else:
                traffic_df.to_csv(traffic_csv_path, index=False)
        
        return csv_path
    
    def get_video_stats_history(self, video_id=None, channel_id=None):
        """Get historical video stats from the database"""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM video_stats"
            params = ()
            conditions = []
            
            if video_id:
                conditions.append("video_id = ?")
                params = params + (video_id,)
            
            if channel_id:
                conditions.append("channel_id = ?")
                params = params + (channel_id,)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY last_updated DESC"
            
            df = pd.read_sql_query(query, conn, params=params)
            return df

    def get_traffic_sources(self, video_id):
        """Get traffic sources for a specific video"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM traffic_sources WHERE video_id = ? ORDER BY views DESC",
                conn,
                params=(video_id,)
            )
            return df