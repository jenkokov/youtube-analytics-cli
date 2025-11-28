import os
import re
from pathlib import Path
from googleapiclient.errors import HttpError


class CaptionDownloader:
    def __init__(self, youtube_service, output_dir='data/captions'):
        """
        Initialize caption downloader

        Args:
            youtube_service: Authenticated YouTube API service (with youtube.force-ssl scope)
            output_dir: Directory to save caption files
        """
        self.youtube = youtube_service
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def list_caption_tracks(self, video_id):
        """
        List all caption tracks available for a video

        Args:
            video_id: YouTube video ID

        Returns:
            List of caption track metadata including language and track ID
        """
        try:
            request = self.youtube.captions().list(
                part='snippet',
                videoId=video_id
            )
            response = request.execute()
            return response.get('items', [])
        except HttpError as e:
            if e.resp.status == 403:
                raise PermissionError(f"Permission denied - you must be the owner of video {video_id}")
            elif e.resp.status == 404:
                raise ValueError(f"Video {video_id} not found")
            else:
                raise Exception(f"Failed to list caption tracks: {e}")

    def find_caption_track(self, video_id, language_code='uk'):
        """
        Find caption track ID for specific language

        Args:
            video_id: YouTube video ID
            language_code: Language code (e.g., 'uk' for Ukrainian)

        Returns:
            Caption track ID or None if not found
        """
        caption_tracks = self.list_caption_tracks(video_id)

        for item in caption_tracks:
            snippet = item.get('snippet', {})
            # Check if language matches and it's auto-generated (ASR)
            if (snippet.get('language') == language_code and
                snippet.get('trackKind') == 'asr'):
                return item['id']

        return None

    def download_caption(self, caption_id, format='vtt'):
        """
        Download caption content from YouTube

        Args:
            caption_id: Caption track ID
            format: Caption format (vtt, srt, sbv, txt)

        Returns:
            Caption content as string
        """
        try:
            # For text format, download as VTT and extract text
            download_format = 'vtt' if format == 'txt' else format

            request = self.youtube.captions().download(
                id=caption_id,
                tfmt=download_format
            )
            subtitle_content = request.execute()

            # The API returns bytes, decode to string
            if isinstance(subtitle_content, bytes):
                subtitle_content = subtitle_content.decode('utf-8')

            # Extract plain text if requested
            if format == 'txt':
                subtitle_content = self.extract_text_from_vtt(subtitle_content)

            return subtitle_content
        except HttpError as e:
            raise Exception(f"Failed to download caption: {e}")

    def extract_text_from_vtt(self, vtt_content):
        """
        Extract plain text from VTT caption content

        Args:
            vtt_content: VTT format caption string

        Returns:
            Plain text transcript
        """
        lines = vtt_content.split('\n')
        text_lines = []
        previous_line = None

        for line in lines:
            line = line.strip()

            # Skip empty lines, WEBVTT header, timestamps, and cue identifiers
            if not line or line.startswith('WEBVTT') or '-->' in line or line.isdigit() or line.startswith('NOTE'):
                continue

            # Skip lines with inline timestamps (e.g., <00:00:06.359>)
            if '<00:' in line:
                continue

            # Remove HTML-like tags (e.g., <c>, </c>, <i>, etc.)
            line = re.sub(r'<[^>]+>', '', line).strip()

            # Skip if empty after tag removal
            if not line:
                continue

            # Skip duplicate consecutive lines
            if line == previous_line:
                continue

            text_lines.append(line)
            previous_line = line

        # Join with newlines
        text = '\n'.join(text_lines)

        return text

    def sanitize_filename(self, title):
        """
        Sanitize video title for filesystem compatibility
        Remove/replace: / \ : * ? " < > |

        Args:
            title: Video title string

        Returns:
            Sanitized filename string
        """
        # Remove invalid characters
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', title)

        # Limit length to avoid filesystem issues
        sanitized = sanitized[:200]

        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip('. ')

        return sanitized

    def get_video_title(self, video_id):
        """
        Fetch video title using YouTube Data API

        Args:
            video_id: YouTube video ID

        Returns:
            Video title string
        """
        try:
            request = self.youtube.videos().list(
                part='snippet',
                id=video_id
            )
            response = request.execute()

            if not response.get('items'):
                raise ValueError(f"Video {video_id} not found")

            return response['items'][0]['snippet']['title']
        except HttpError as e:
            raise Exception(f"Failed to get video title: {e}")

    def caption_file_exists(self, video_id, format='txt'):
        """
        Check if a caption file already exists for this video ID

        Args:
            video_id: YouTube video ID
            format: File format extension

        Returns:
            True if file exists, False otherwise
        """
        # Look for any file that ends with _{video_id}.{format}
        pattern = f"*_{video_id}.{format}"
        matching_files = list(self.output_dir.glob(pattern))
        return len(matching_files) > 0

    def save_caption(self, content, video_id, video_title, format='vtt'):
        """
        Save caption content to file
        Filename format: {sanitized_title}_{video_id}.{format}

        Args:
            content: Caption content string
            video_id: YouTube video ID
            video_title: Video title
            format: File format extension

        Returns:
            Path to saved file or None if file already exists
        """
        sanitized_title = self.sanitize_filename(video_title)
        filename = f"{sanitized_title}_{video_id}.{format}"
        filepath = self.output_dir / filename

        # Check if file already exists
        if filepath.exists():
            return None

        # Write with UTF-8 encoding for Unicode support
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return filepath

    def download_captions_batch(self, video_ids, language_code='uk', format='vtt', verbose=False):
        """
        Download captions for multiple videos

        Args:
            video_ids: List of YouTube video IDs
            language_code: Language code (default: 'uk' for Ukrainian)
            format: Caption format (vtt, srt, sbv)
            verbose: Show detailed progress output

        Returns:
            Dictionary with statistics and lists of failed video IDs
        """
        stats = {
            'successful': 0,
            'failed': 0,
            'no_captions': 0,
            'skipped': 0,
            'permission_denied': 0,
            'failed_ids': [],
            'no_captions_ids': [],
            'permission_denied_ids': []
        }

        total_videos = len(video_ids)

        for i, video_id in enumerate(video_ids, 1):
            try:
                if verbose:
                    print(f"\n[{i}/{total_videos}] Video: {video_id}")

                # Check if file already exists BEFORE making any API calls (saves quota!)
                if self.caption_file_exists(video_id, format):
                    if verbose:
                        print(f"  ✓ Caption file already exists, skipping")
                    stats['skipped'] += 1
                    continue

                if verbose:
                    print(f"  Fetching video metadata...")

                # Get video title
                video_title = self.get_video_title(video_id)
                if verbose:
                    print(f"  ✓ Title: {video_title}")
                    print(f"  Finding {language_code.upper()} captions...")

                # Find caption track
                caption_id = self.find_caption_track(video_id, language_code)

                if not caption_id:
                    if verbose:
                        print(f"  ✗ No {language_code.upper()} captions available (skipped)")
                    stats['no_captions'] += 1
                    stats['no_captions_ids'].append(video_id)
                    continue

                if verbose:
                    print(f"  ✓ Found auto-generated {language_code.upper()} track")
                    format_desc = "plain text transcript" if format == 'txt' else f"{format.upper()} format"
                    print(f"  Downloading {format_desc}...")

                # Download caption content
                caption_content = self.download_caption(caption_id, format)

                # Save to file
                filepath = self.save_caption(caption_content, video_id, video_title, format)

                if filepath:
                    if verbose:
                        print(f"  ✓ Saved: {filepath}")
                    stats['successful'] += 1
                else:
                    # This shouldn't happen since we check at the beginning, but keep as safety
                    if verbose:
                        print(f"  File already exists, skipping")
                    stats['skipped'] += 1

            except PermissionError as e:
                if verbose:
                    print(f"  ✗ Permission denied - you must be the video owner")
                else:
                    print(f"Warning: {e}")
                stats['permission_denied'] += 1
                stats['permission_denied_ids'].append(video_id)

            except Exception as e:
                if verbose:
                    print(f"  ✗ Error: {e}")
                else:
                    print(f"Warning: Failed to download captions for {video_id}: {e}")
                stats['failed'] += 1
                stats['failed_ids'].append(video_id)

        return stats
