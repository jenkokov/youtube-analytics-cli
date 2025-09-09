import re
import yaml
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class ShowMapper:
    def __init__(self, config_path: str = None, db_path: str = None):
        """
        Initialize ShowMapper with config and database paths
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'show_patterns.yaml'
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / 'data' / 'youtube_analytics.sqlite'
            
        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
    
    def _extract_show_episode(self, title: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Extract show name and episode number from video title using regex patterns
        
        Returns:
            Tuple of (show_name, episode_number) or (None, None) if no match
        """
        patterns = self.config.get('show_patterns', [])
        
        for pattern in patterns:
            if not pattern.get('enabled', True):
                continue
                
            # Check if title matches the pattern
            title_regex = pattern.get('title_regex')
            if not title_regex:
                continue
                
            title_match = re.search(title_regex, title)
            if not title_match:
                continue
            
            # Extract show name
            show_name = pattern.get('name')
            if pattern.get('show_group'):
                # Extract show name from regex group
                show_group = pattern.get('show_group', 1)
                if len(title_match.groups()) >= show_group:
                    show_name = title_match.group(show_group).strip()
            
            # Extract episode number
            episode_num = None
            episode_regex = pattern.get('episode_regex')
            if episode_regex:
                episode_match = re.search(episode_regex, title)
                if episode_match:
                    episode_group = pattern.get('episode_group', 1)
                    if len(episode_match.groups()) >= episode_group:
                        try:
                            episode_num = int(episode_match.group(episode_group))
                        except (ValueError, IndexError):
                            pass
            
            if show_name:  # Return if we found at least a show name
                return show_name, episode_num
        
        return None, None
    
    def get_videos_to_update(self) -> List[Tuple[str, str]]:
        """
        Get list of videos that need show/episode mapping
        
        Returns:
            List of (video_id, title) tuples
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if self.config.get('options', {}).get('update_only_empty', True):
                # Only get videos where both show and episode_num are NULL
                query = """
                    SELECT video_id, title 
                    FROM video_stats 
                    WHERE (show IS NULL OR show = '') 
                    AND (episode_num IS NULL OR episode_num = 0)
                    AND exclude_from_stats = 0
                    ORDER BY upload_time DESC
                """
            else:
                # Get all videos (will overwrite existing mappings)
                query = """
                    SELECT video_id, title 
                    FROM video_stats 
                    WHERE exclude_from_stats = 0
                    ORDER BY upload_time DESC
                """
            
            max_videos = self.config.get('options', {}).get('max_videos', 0)
            if max_videos > 0:
                query += f" LIMIT {max_videos}"
            
            cursor.execute(query)
            return cursor.fetchall()
    
    def update_video_show_episode(self, video_id: str, show_name: str, episode_num: Optional[int], dry_run: bool = False):
        """
        Update show and episode information for a specific video
        """
        if dry_run:
            return
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE video_stats 
                SET show = ?, episode_num = ?, last_updated = CURRENT_TIMESTAMP
                WHERE video_id = ?
            """, (show_name, episode_num, video_id))
            conn.commit()
    
    def process_videos(self, dry_run: bool = None, verbose: bool = None) -> Dict[str, int]:
        """
        Process all videos and update show/episode information
        
        Returns:
            Dictionary with processing statistics
        """
        # Use config defaults if not specified
        if dry_run is None:
            dry_run = self.config.get('options', {}).get('dry_run', False)
        if verbose is None:
            verbose = self.config.get('options', {}).get('verbose', True)
        
        videos = self.get_videos_to_update()
        stats = {
            'total_processed': 0,
            'shows_mapped': 0,
            'episodes_mapped': 0,
            'no_match': 0
        }
        
        if verbose:
            print(f"Processing {len(videos)} videos...")
            if dry_run:
                print("DRY RUN MODE - No changes will be made")
            print()
        
        for i, (video_id, title) in enumerate(videos, 1):
            stats['total_processed'] += 1
            
            show_name, episode_num = self._extract_show_episode(title)
            
            if show_name:
                stats['shows_mapped'] += 1
                if episode_num is not None:
                    stats['episodes_mapped'] += 1
                
                if verbose:
                    ep_text = f" (Episode {episode_num})" if episode_num else ""
                    status = "[DRY RUN] " if dry_run else ""
                    print(f"[{i}/{len(videos)}] {status}Mapped: {show_name}{ep_text}")
                    print(f"  Title: {title[:80]}{'...' if len(title) > 80 else ''}")
                    print()
                
                self.update_video_show_episode(video_id, show_name, episode_num, dry_run)
            else:
                stats['no_match'] += 1
                if verbose:
                    print(f"[{i}/{len(videos)}] No match: {title[:80]}{'...' if len(title) > 80 else ''}")
                    print()
        
        return stats
    
    def list_patterns(self):
        """List all configured patterns"""
        patterns = self.config.get('show_patterns', [])
        print("Configured Show Patterns:")
        print("-" * 50)
        
        for i, pattern in enumerate(patterns, 1):
            status = "✓ Enabled" if pattern.get('enabled', True) else "✗ Disabled"
            print(f"{i}. {pattern.get('name', 'Unnamed')} ({status})")
            print(f"   Title Regex: {pattern.get('title_regex', 'N/A')}")
            print(f"   Episode Regex: {pattern.get('episode_regex', 'N/A')}")
            print()
    
    def test_pattern(self, title: str):
        """Test a title against all patterns"""
        show_name, episode_num = self._extract_show_episode(title)
        
        print(f"Testing title: {title}")
        print("-" * 50)
        
        if show_name:
            ep_text = f" (Episode {episode_num})" if episode_num else ""
            print(f"✓ Match found: {show_name}{ep_text}")
        else:
            print("✗ No match found")
        
        return show_name, episode_num