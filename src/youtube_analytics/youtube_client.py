import os
import re
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

class YouTubeClient:
    def __init__(self, youtube_service, analytics_service=None):
        self.youtube = youtube_service
        self.analytics = analytics_service
    
    def get_channel_stats(self, channel_id=None):
        """Get basic channel statistics"""
        if not channel_id:
            channel_id = os.getenv('DEFAULT_CHANNEL_ID')
            if not channel_id:
                # Get the authenticated user's channel
                channel_id = self._get_my_channel_id()
        
        try:
            # Get channel details
            request = self.youtube.channels().list(
                part='snippet,statistics,contentDetails',
                id=channel_id
            )
            response = request.execute()
            
            if not response.get('items'):
                raise ValueError(f"Channel with ID {channel_id} not found")
            
            channel = response['items'][0]
            snippet = channel['snippet']
            statistics = channel['statistics']
            
            stats = {
                'channel_id': channel_id,
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'published_at': snippet['publishedAt'],
                'subscriber_count': int(statistics.get('subscriberCount', 0)),
                'view_count': int(statistics.get('viewCount', 0)),
                'video_count': int(statistics.get('videoCount', 0)),
            }
            
            return stats
            
        except HttpError as e:
            raise Exception(f"YouTube API error: {e}")
    
    def _get_my_channel_id(self):
        """Get the channel ID for the authenticated user"""
        try:
            request = self.youtube.channels().list(
                part='id',
                mine=True
            )
            response = request.execute()
            
            if not response.get('items'):
                raise ValueError("No channel found for authenticated user")
            
            return response['items'][0]['id']
            
        except HttpError as e:
            raise Exception(f"Failed to get channel ID: {e}")
    
    def _parse_duration(self, duration_iso):
        """Convert ISO 8601 duration to seconds"""
        # ISO 8601 duration format: PT4M13S, PT1H30M5S, PT45S, etc.
        pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
        match = pattern.match(duration_iso)
        
        if not match:
            return 0
        
        hours, minutes, seconds = match.groups()
        total_seconds = 0
        
        if hours:
            total_seconds += int(hours) * 3600
        if minutes:
            total_seconds += int(minutes) * 60
        if seconds:
            total_seconds += int(seconds)
            
        return total_seconds
    
    @staticmethod
    def _detect_youtube_short(duration_seconds, content_details, snippet, status, recording_details):
        """Enhanced YouTube Shorts detection using multiple indicators"""
        
        # Primary method: Duration-based (60 seconds or less)
        is_duration_short = duration_seconds <= 60 and duration_seconds > 0
        
        # Check for additional indicators that might suggest Shorts
        additional_indicators = []
        
        # 1. Check aspect ratio if available (Shorts are typically vertical 9:16)
        # Note: This info might not be available in basic API response
        
        # 2. Check for mobile recording indicators
        if recording_details:
            # Look for mobile recording patterns (not reliable but can be a hint)
            recording_date = recording_details.get('recordingDate')
            if recording_date:
                additional_indicators.append('mobile_recorded')
        
        # 3. Check video description for Shorts hashtags
        description = snippet.get('description', '').lower()
        shorts_keywords = ['#shorts', '#short', '#youtubeshorts', '#ytshorts']
        has_shorts_hashtag = any(keyword in description for keyword in shorts_keywords)
        if has_shorts_hashtag:
            additional_indicators.append('shorts_hashtag')
        
        # 4. Check title for Shorts indicators
        title = snippet.get('title', '').lower()
        if '#shorts' in title or '#short' in title:
            additional_indicators.append('shorts_title')
        
        # 5. Check tags if available
        tags = snippet.get('tags', [])
        if tags:
            shorts_tags = [tag.lower() for tag in tags if 'short' in tag.lower()]
            if shorts_tags:
                additional_indicators.append('shorts_tags')
        
        # Enhanced logic: 
        # - If duration <= 60s AND has additional indicators → definitely Short
        # - If duration <= 60s but no indicators → likely Short (use duration)
        # - If duration > 60s but has strong indicators → possibly mislabeled, still use duration
        
        confidence_score = len(additional_indicators)
        
        # Log detection details if verbose (you could expand this)
        detection_method = 'duration_only'
        if is_duration_short and confidence_score > 0:
            detection_method = f'duration_plus_{confidence_score}_indicators'
        elif is_duration_short:
            detection_method = 'duration_only'
        elif confidence_score >= 2:  # Strong indicators even if longer
            detection_method = 'indicators_override'
            # In rare cases, might be a Short that's slightly over 60s due to processing
            return duration_seconds <= 65  # Allow small buffer
        
        return is_duration_short
    
    def _get_best_thumbnail(self, thumbnails):
        """Get the best available thumbnail URL from thumbnails object"""
        if not thumbnails:
            return None
        
        # Priority order: maxres > high > medium > default
        preferred_sizes = ['maxres', 'high', 'medium', 'default']
        
        for size in preferred_sizes:
            if size in thumbnails:
                return thumbnails[size].get('url')
        
        # Fallback: return any available thumbnail
        for size, thumbnail in thumbnails.items():
            if 'url' in thumbnail:
                return thumbnail['url']
        
        return None
    
    def get_channel_videos(self, channel_id=None, max_results=50, verbose=False):
        """Get list of videos from a channel with pagination support"""
        if not channel_id:
            channel_id = self._get_my_channel_id()
        
        try:
            # First, get the uploads playlist ID
            request = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            )
            response = request.execute()
            
            if not response.get('items'):
                raise ValueError(f"Channel with ID {channel_id} not found")
            
            uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from the uploads playlist with pagination
            videos = []
            next_page_token = None
            page_count = 0
            
            while len(videos) < max_results:
                # Calculate how many videos to request in this batch
                per_page = min(50, max_results - len(videos))  # YouTube API max is 50
                
                if verbose and page_count > 0:
                    print(f"Fetching page {page_count + 1} of videos... ({len(videos)} collected so far)")
                
                request = self.youtube.playlistItems().list(
                    part='snippet',
                    playlistId=uploads_playlist_id,
                    maxResults=per_page,
                    pageToken=next_page_token if next_page_token else None
                )
                response = request.execute()
                
                # Process videos from this page
                page_videos = []
                for item in response.get('items', []):
                    video_info = {
                        'video_id': item['snippet']['resourceId']['videoId'],
                        'title': item['snippet']['title'],
                        'published_at': item['snippet']['publishedAt'],
                        'description': item['snippet'].get('description', ''),
                    }
                    page_videos.append(video_info)
                
                videos.extend(page_videos)
                page_count += 1
                
                # Check if there are more pages
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    # No more pages available
                    if verbose and len(videos) < max_results:
                        print(f"Reached end of channel videos. Found {len(videos)} total videos (requested {max_results})")
                    break
                
                # If we got fewer videos than requested in this page, we've reached the end
                if len(page_videos) < per_page:
                    break
            
            if verbose:
                print(f"Successfully fetched {len(videos)} videos across {page_count} page(s)")
            
            return videos
            
        except HttpError as e:
            raise Exception(f"Failed to get channel videos: {e}")
    
    def get_video_stats(self, video_id):
        """Get detailed statistics for a specific video"""
        try:
            request = self.youtube.videos().list(
                part='snippet,statistics,contentDetails,status,recordingDetails',
                id=video_id
            )
            response = request.execute()
            
            if not response.get('items'):
                raise ValueError(f"Video with ID {video_id} not found")
            
            video = response['items'][0]
            snippet = video['snippet']
            statistics = video['statistics']
            content_details = video['contentDetails']
            status = video.get('status', {})
            recording_details = video.get('recordingDetails', {})
            
            # Get video visibility/privacy status
            visibility = status.get('privacyStatus')
            
            # Get best available thumbnail
            thumbnail_url = self._get_best_thumbnail(snippet.get('thumbnails', {}))

            # Determine if video is a YouTube Short
            duration_seconds = self._parse_duration(content_details['duration'])

            # Multiple detection methods for YouTube Shorts
            is_short = self._detect_youtube_short(
                duration_seconds,
                content_details,
                snippet,
                status,
                recording_details
            )

            # Get tags if available and format as comma-separated string
            tags = snippet.get('tags', [])
            tags_string = ', '.join(tags) if tags else None

            stats = {
                'video_id': video_id,
                'channel_id': snippet['channelId'],
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'upload_time': snippet['publishedAt'],
                'duration_seconds': duration_seconds,
                'watch_url': f"https://www.youtube.com/watch?v={video_id}",
                'view_count': int(statistics.get('viewCount', 0)),
                'like_count': int(statistics.get('likeCount', 0)),
                'dislike_count': int(statistics.get('dislikeCount', 0)),  # Available for authenticated video owners
                'comment_count': int(statistics.get('commentCount', 0)),
                'visibility': visibility,
                'is_short': is_short,
                'thumbnail_url': thumbnail_url,
                'tags': tags_string,
                'subscriber_count': None,  # Will be populated by analytics API
            }
            
            return stats
            
        except HttpError as e:
            raise Exception(f"Failed to get video stats: {e}")
    
    def get_video_analytics(self, video_id, channel_id=None, start_date='2023-01-01', end_date='2025-12-31'):
        """Get analytics data including traffic sources and subscriber acquisition for a specific video"""
        if not self.analytics:
            return {}

        if not channel_id:
            channel_id = self._get_my_channel_id()

        analytics_data = {}

        try:
            # Get traffic sources
            traffic_request = self.analytics.reports().query(
                ids=f'channel=={channel_id}',
                startDate=start_date,
                endDate=end_date,
                metrics='views',
                dimensions='insightTrafficSourceType',
                filters=f'video=={video_id}',
                sort='-views'
            )
            traffic_response = traffic_request.execute()

            traffic_sources = {}
            if traffic_response.get('rows'):
                for row in traffic_response['rows']:
                    traffic_source = row[0]
                    views = int(row[1])
                    traffic_sources[traffic_source] = views

            analytics_data['traffic_sources'] = traffic_sources

            # Get subscriber acquisition data - subscribers gained from this specific video
            try:
                subscriber_request = self.analytics.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='subscribersGained',
                    filters=f'video=={video_id}'
                )
                subscriber_response = subscriber_request.execute()

                subscribers_gained = 0
                if subscriber_response.get('rows'):
                    # Sum all subscriber gains from this video
                    subscribers_gained = sum(int(row[0]) for row in subscriber_response['rows'])

                analytics_data['subscribers_gained'] = subscribers_gained

            except HttpError as e:
                # Subscriber analytics might not be available for all videos
                print(f"Warning: Could not get subscriber data for video {video_id}: {e}")
                analytics_data['subscribers_gained'] = None

            return analytics_data

        except HttpError as e:
            # If analytics fails, return empty dict but don't fail the whole operation
            print(f"Warning: Could not get analytics data for video {video_id}: {e}")
            return {}
    
    def get_channel_video_stats(self, channel_id=None, max_results=50, include_analytics=True, verbose=False, save_callback=None):
        """Get detailed stats for all videos in a channel"""
        if verbose:
            print(f"Fetching video list for channel...")
        
        videos = self.get_channel_videos(channel_id, max_results, verbose=verbose)
        detailed_videos = []
        
        if not channel_id:
            channel_id = self._get_my_channel_id()
        
        total_videos = len(videos)
        if verbose:
            print(f"\nProcessing {total_videos} videos for detailed statistics...")
        
        saved_count = 0
        for i, video in enumerate(videos, 1):
            try:
                if verbose:
                    print(f"[{i}/{total_videos}] Getting stats for: {video['title'][:50]}{'...' if len(video['title']) > 50 else ''}")
                
                # Get basic video stats
                video_stats = self.get_video_stats(video['video_id'])
                
                # Get analytics data if requested and available
                traffic_sources = {}
                if include_analytics and self.analytics:
                    if verbose:
                        print(f"  Getting analytics data...")
                    analytics_data = self.get_video_analytics(video['video_id'], channel_id)
                    traffic_sources = analytics_data.get('traffic_sources', {})
                    subscribers_gained = analytics_data.get('subscribers_gained')

                    # Add subscriber data to video stats
                    if subscribers_gained is not None:
                        video_stats['subscriber_count'] = subscribers_gained

                video_data = {
                    'stats': video_stats,
                    'traffic_sources': traffic_sources
                }
                
                # Save immediately if callback provided
                if save_callback:
                    try:
                        save_callback(video_data)
                        saved_count += 1
                        if verbose:
                            print(f"  ✓ Saved to database | Views: {video_stats['view_count']:,} | Likes: {video_stats['like_count']:,}")
                    except Exception as save_error:
                        if verbose:
                            print(f"  ✗ Save failed: {save_error}")
                        else:
                            print(f"Warning: Failed to save video {video['video_id']}: {save_error}")
                else:
                    # Fallback to old behavior if no callback
                    detailed_videos.append(video_data)
                    if verbose:
                        print(f"  ✓ Views: {video_stats['view_count']:,} | Likes: {video_stats['like_count']:,}")
                
            except Exception as e:
                if verbose:
                    print(f"  ✗ Warning: Could not get stats for video {video['video_id']}: {e}")
                else:
                    print(f"Warning: Could not get stats for video {video['video_id']}: {e}")
                continue
        
        # Return saved count and any remaining videos (for backward compatibility)
        if save_callback:
            return saved_count
        return detailed_videos
    
    def search_channels(self, query, max_results=25):
        """Search for channels by keyword"""
        try:
            request = self.youtube.search().list(
                part='snippet',
                type='channel',
                q=query,
                maxResults=max_results
            )
            response = request.execute()
            
            channels = []
            for item in response.get('items', []):
                channel_info = {
                    'channel_id': item['id']['channelId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'published_at': item['snippet']['publishedAt'],
                }
                channels.append(channel_info)
            
            return channels
            
        except HttpError as e:
            raise Exception(f"Failed to search channels: {e}")