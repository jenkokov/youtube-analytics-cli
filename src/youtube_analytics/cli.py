import click
import os
from auth import YouTubeAuth
from data_storage import DataStorage
from youtube_client import YouTubeClient
from show_mapper import ShowMapper

@click.group()
@click.option('--config-dir', default='config', help='Configuration directory')
@click.option('--data-dir', default='data', help='Data storage directory')
@click.pass_context
def cli(ctx, config_dir, data_dir):
    """YouTube Analytics CLI - Collect and analyze YouTube channel data"""
    ctx.ensure_object(dict)
    ctx.obj['config_dir'] = config_dir
    ctx.obj['data_dir'] = data_dir
    
    # Ensure directories exist
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

@cli.command()
@click.option('--channel-id', help='YouTube Channel ID (optional if set in .env)')
@click.option('--output', type=click.Choice(['console', 'csv', 'sqlite']), default='console', help='Output format')
@click.pass_context
def channel_stats(ctx, channel_id, output):
    """Get basic channel statistics"""
    try:
        # Initialize services
        auth = YouTubeAuth()
        youtube_service = auth.get_youtube_service()
        analytics_service = auth.get_analytics_service()

        client = YouTubeClient(youtube_service, analytics_service)
        storage = DataStorage(ctx.obj['data_dir'])

        # Get channel stats
        stats = client.get_channel_stats(channel_id)
        
        if output == 'console':
            _display_channel_stats(stats)
        elif output == 'csv':
            storage.save_channel_stats_csv(stats)
            click.echo("Channel stats saved to data/channel_stats.csv")
        elif output == 'sqlite':
            storage.save_channel_stats_db(stats)
            click.echo("Channel stats saved to database")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if 'invalid_grant' in str(e) or 'Bad Request' in str(e):
            click.echo("This looks like an expired token. Run: python -m src.youtube_analytics.cli reauth")
        exit(1)

def _display_channel_stats(stats):
    """Display channel stats in console"""
    click.echo("\n=== Channel Statistics ===")
    click.echo(f"Channel: {stats['title']}")
    click.echo(f"Subscribers: {stats['subscriber_count']:,}")
    click.echo(f"Total Views: {stats['view_count']:,}")
    click.echo(f"Video Count: {stats['video_count']:,}")
    click.echo(f"Created: {stats['published_at']}")
    if stats.get('description'):
        click.echo(f"Description: {stats['description'][:100]}...")

@cli.command()
@click.option('--video-id', help='Specific video ID to get stats for')
@click.option('--channel-id', help='YouTube Channel ID (optional if set in .env)')
@click.option('--max-videos', default=25, help='Maximum number of videos to process')
@click.option('--output', type=click.Choice(['console', 'csv', 'sqlite']), default='sqlite', help='Output format')
@click.option('--include-analytics/--no-analytics', default=True, help='Include traffic source analytics')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output - show progress for each video')
@click.pass_context
def video_stats(ctx, video_id, channel_id, max_videos, output, include_analytics, verbose):
    """Get detailed video statistics"""
    try:
        # Initialize services
        auth = YouTubeAuth()
        youtube_service = auth.get_youtube_service()
        analytics_service = auth.get_analytics_service() if include_analytics else None
        
        client = YouTubeClient(youtube_service, analytics_service)
        storage = DataStorage(ctx.obj['data_dir'])
        
        if video_id:
            # Get stats for a specific video
            if verbose:
                click.echo(f"Getting stats for video: {video_id}")
            
            video_stats = client.get_video_stats(video_id)
            traffic_sources = {}
            
            if include_analytics and analytics_service:
                if verbose:
                    click.echo("  Getting traffic source analytics...")
                analytics_data = client.get_video_analytics(video_id, channel_id)
                traffic_sources = analytics_data.get('traffic_sources', {})
                subscribers_gained = analytics_data.get('subscribers_gained')

                # Add subscriber data to video stats
                if subscribers_gained is not None:
                    video_stats['subscriber_count'] = subscribers_gained
            
            # Save immediately for a single video
            video_data = {'stats': video_stats, 'traffic_sources': traffic_sources}
            if output == 'console':
                _display_video_stats(video_stats, traffic_sources)
            elif output == 'csv':
                storage.save_video_stats_csv(video_stats, traffic_sources)
            elif output == 'sqlite':
                storage.save_video_stats_db(video_stats, traffic_sources)
            
            saved_count = 1
            
            # Apply show mapping for single video (only for sqlite output)
            if output == 'sqlite':
                try:
                    if verbose:
                        click.echo("Applying show mapping...")
                    mapper = ShowMapper(db_path=ctx.obj['data_dir'] + '/youtube_analytics.sqlite')
                    mapping_stats = mapper.process_videos(dry_run=False, verbose=False)
                    if mapping_stats['shows_mapped'] > 0:
                        click.echo(f"Applied show mapping to video")
                except (FileNotFoundError, ValueError):
                    if verbose:
                        click.echo("Show patterns not configured - skipping mapping")
                except Exception as e:
                    if verbose:
                        click.echo(f"Show mapping failed: {e}")
        else:
            # Get stats for all videos in a channel
            if max_videos > 50 and not verbose:
                click.echo(f"Collecting stats for up to {max_videos} videos...")
                click.echo("Note: This will require multiple API requests. Use -v for detailed progress.")
            elif verbose:
                click.echo(f"Collecting stats for up to {max_videos} videos with verbose output...")
            else:
                click.echo(f"Collecting stats for up to {max_videos} videos...")
            
            # Define save callback based on output format
            def save_callback(video_data):
                video_stats = video_data['stats']
                traffic_sources = video_data['traffic_sources']
                
                if output == 'console':
                    _display_video_stats(video_stats, traffic_sources)
                elif output == 'csv':
                    storage.save_video_stats_csv(video_stats, traffic_sources)
                elif output == 'sqlite':
                    storage.save_video_stats_db(video_stats, traffic_sources)
            
            # Use callback for immediate saving during processing
            saved_count = client.get_channel_video_stats(
                channel_id=channel_id, 
                max_results=max_videos,
                include_analytics=include_analytics,
                verbose=verbose,
                save_callback=save_callback
            )
        
        # Apply show mapping after data collection is complete (only for sqlite output)
        if output == 'sqlite' and saved_count > 0:
            try:
                if verbose:
                    click.echo("\nApplying show mapping to new videos...")
                mapper = ShowMapper(db_path=ctx.obj['data_dir'] + '/youtube_analytics.sqlite')
                mapping_stats = mapper.process_videos(dry_run=False, verbose=False)
                if mapping_stats['shows_mapped'] > 0:
                    click.echo(f"Applied show mapping to {mapping_stats['shows_mapped']} videos")
                elif verbose:
                    click.echo("No new videos required show mapping")
            except (FileNotFoundError, ValueError):
                if verbose:
                    click.echo("Show patterns not configured - skipping mapping")
            except Exception as e:
                if verbose:
                    click.echo(f"Show mapping failed: {e}")
        
        if output == 'csv':
            click.echo(f"Saved {saved_count} video stats to data/exports/video_stats.csv")
        elif output == 'sqlite':
            click.echo(f"Saved {saved_count} video stats to data/youtube_analytics.sqlite")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if 'invalid_grant' in str(e) or 'Bad Request' in str(e):
            click.echo("This looks like an expired token. Run: python -m src.youtube_analytics.cli reauth")
        exit(1)

def _format_duration(seconds):
    """Format duration in seconds to readable format"""
    if seconds == 0:
        return "0s"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    
    return "".join(parts)

def _display_video_stats(video_stats, traffic_sources=None):
    """Display video stats in console"""
    click.echo(f"\n=== {video_stats['title']} ===")
    click.echo(f"Video ID: {video_stats['video_id']}")
    click.echo(f"Channel ID: {video_stats['channel_id']}")
    click.echo(f"Upload Time: {video_stats['upload_time']}")
    click.echo(f"Duration: {_format_duration(video_stats['duration_seconds'])}")
    click.echo(f"Watch URL: {video_stats['watch_url']}")
    click.echo(f"Views: {video_stats['view_count']:,}")
    click.echo(f"Likes: {video_stats['like_count']:,}")
    click.echo(f"Comments: {video_stats['comment_count']:,}")
    
    # Show thumbnail URL if available
    if video_stats.get('thumbnail_url'):
        click.echo(f"Thumbnail: {video_stats['thumbnail_url']}")
    
    # Show video type and status
    video_type = "YouTube Short" if video_stats.get('is_short') else "Regular Video"
    visibility = video_stats.get('visibility')
    if visibility:
        click.echo(f"Type: {video_type} ({visibility.title()})")
    else:
        click.echo(f"Type: {video_type}")

    # Show tags if available
    if video_stats.get('tags'):
        click.echo(f"Tags: {video_stats['tags']}")

    # Show subscriber acquisition data
    if video_stats.get('subscriber_count') is not None:
        click.echo(f"New Subscribers: {video_stats['subscriber_count']:,}")

    if traffic_sources:
        click.echo("\nTraffic Sources:")
        for source, views in sorted(traffic_sources.items(), key=lambda x: x[1], reverse=True):
            click.echo(f"  {source}: {views:,} views")

@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be updated without making changes')
@click.option('--verbose/--quiet', default=True, help='Show detailed progress')
@click.option('--config-file', default=None, help='Custom config file path')
@click.pass_context
def update_shows(ctx, dry_run, verbose, config_file):
    """Update show names and episode numbers using regex patterns"""
    try:
        # Initialize show mapper with optional custom config
        mapper = ShowMapper(config_path=config_file)
        
        # Process videos
        stats = mapper.process_videos(dry_run=dry_run, verbose=verbose)
        
        # Show summary
        click.echo("\n" + "="*50)
        click.echo("PROCESSING SUMMARY")
        click.echo("="*50)
        click.echo(f"Total videos processed: {stats['total_processed']}")
        click.echo(f"Shows mapped: {stats['shows_mapped']}")
        click.echo(f"Episodes mapped: {stats['episodes_mapped']}")
        click.echo(f"No match found: {stats['no_match']}")
        
        if dry_run:
            click.echo("\n[DRY RUN] No changes were made to the database.")
            click.echo("Remove --dry-run flag to apply changes.")
        else:
            click.echo(f"\n✓ Successfully updated {stats['shows_mapped']} videos!")
            
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()

@cli.command()
@click.option('--config-file', default=None, help='Custom config file path')
@click.pass_context
def list_patterns(ctx, config_file):
    """List all configured show patterns"""
    try:
        mapper = ShowMapper(config_path=config_file)
        mapper.list_patterns()
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()

@cli.command()
@click.argument('title')
@click.option('--config-file', default=None, help='Custom config file path')
@click.pass_context
def test_pattern(ctx, title, config_file):
    """Test a video title against all patterns"""
    try:
        mapper = ShowMapper(config_path=config_file)
        mapper.test_pattern(title)
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()

@cli.command()
@click.pass_context
def setup(ctx):
    """Set up authentication and configuration"""
    click.echo("Setting up YouTube Analytics CLI...")

    # Check if .env exists
    if not os.path.exists('.env'):
        click.echo("Creating .env file from template...")
        if os.path.exists('.env.example'):
            import shutil
            shutil.copy('.env.example', '.env')
            click.echo("Please edit .env file with your YouTube API credentials")
        else:
            click.echo("Please create a .env file with your YouTube API credentials")

    # Test authentication
    try:
        auth = YouTubeAuth()
        auth.authenticate()
        click.echo("✓ Authentication successful!")
    except Exception as e:
        click.echo(f"✗ Authentication failed: {e}")
        if 'invalid_grant' in str(e):
            click.echo("This looks like an expired token. Try: python -m src.youtube_analytics.cli reauth")
        else:
            click.echo("Please check your credentials and try again")

@cli.command()
@click.pass_context
def reauth(ctx):
    """Re-authenticate by forcing a new login (fixes expired tokens)"""
    click.echo("Re-authenticating with YouTube APIs...")

    try:
        # Remove existing token to force new authentication
        token_path = 'config/token.pickle'
        if os.path.exists(token_path):
            os.remove(token_path)
            click.echo("Removed expired token file")

        auth = YouTubeAuth()
        auth.authenticate(force_refresh=True)
        click.echo("✓ Re-authentication successful!")
        click.echo("You can now use the CLI commands normally.")

    except Exception as e:
        click.echo(f"✗ Re-authentication failed: {e}")
        click.echo("Please check your credentials in .env file and try again")

def main():
    """Entry point for the CLI"""
    cli()

if __name__ == '__main__':
    main()