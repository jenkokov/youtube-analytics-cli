import os
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# YouTube API scopes
SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

class YouTubeAuth:
    def __init__(self, credentials_file=None):
        self.credentials_file = credentials_file or 'config/credentials.json'
        self.token_file = 'config/token.pickle'
        self.credentials = None
        
    def authenticate(self, force_refresh=False):
        """Authenticate with YouTube API using OAuth2"""
        # Load existing credentials if not forcing refresh
        if os.path.exists(self.token_file) and not force_refresh:
            with open(self.token_file, 'rb') as token:
                self.credentials = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in
        if not self.credentials or not self.credentials.valid or force_refresh:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token and not force_refresh:
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    print("Starting new authentication flow...")
                    self.credentials = None

            if not self.credentials or force_refresh:
                if not os.path.exists(self.credentials_file):
                    self._create_credentials_file()

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                self.credentials = flow.run_local_server(port=0)

            # Save the credentials for the next run
            os.makedirs('config', exist_ok=True)
            with open(self.token_file, 'wb') as token:
                pickle.dump(self.credentials, token)

        return self.credentials
    
    def _create_credentials_file(self):
        """Create credentials file from environment variables"""
        client_id = os.getenv('YOUTUBE_CLIENT_ID')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            raise ValueError(
                "Missing YouTube API credentials. Please set YOUTUBE_CLIENT_ID and "
                "YOUTUBE_CLIENT_SECRET in your .env file or provide a credentials.json file."
            )
        
        credentials_data = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"]
            }
        }
        
        os.makedirs('config', exist_ok=True)
        import json
        with open(self.credentials_file, 'w') as f:
            json.dump(credentials_data, f, indent=2)
    
    def get_youtube_service(self, force_refresh=False):
        """Get authenticated YouTube Data API service"""
        try:
            credentials = self.authenticate(force_refresh=force_refresh)
            return build('youtube', 'v3', credentials=credentials)
        except Exception as e:
            if not force_refresh and ('invalid_grant' in str(e) or 'Bad Request' in str(e)):
                print(f"Authentication failed, trying to refresh token: {e}")
                return self.get_youtube_service(force_refresh=True)
            raise

    def get_analytics_service(self, force_refresh=False):
        """Get authenticated YouTube Analytics API service"""
        try:
            credentials = self.authenticate(force_refresh=force_refresh)
            return build('youtubeAnalytics', 'v2', credentials=credentials)
        except Exception as e:
            if not force_refresh and ('invalid_grant' in str(e) or 'Bad Request' in str(e)):
                print(f"Analytics authentication failed, trying to refresh token: {e}")
                return self.get_analytics_service(force_refresh=True)
            raise