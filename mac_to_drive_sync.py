#!/usr/bin/env python3
"""
Mac to Google Drive Sync Script

This script automatically syncs new files from a local directory to Google Drive.
It tracks which files have been uploaded and only uploads new files on subsequent runs.
"""

import os
import json
import pickle
import argparse
import traceback
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Set, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Default configuration
DEFAULT_CONFIG = {
    'source_directory': os.path.expanduser('~/Documents'),
    'google_drive_folder': 'Mac Backup',
    'credentials_file': 'credentials.json',
    'token_file': 'token.pickle',
    'sync_state_file': 'sync_state.json',
    'file_extensions': [],  # Empty list means all files
    'exclude_patterns': ['.DS_Store', '._*', 'Thumbs.db'],
    'max_file_size_mb': 100,
}


class GoogleDriveSync:
    """Handles syncing files to Google Drive."""
    
    def __init__(self, config: dict):
        self.config = config
        self.service = None
        self.drive_folder_id = None
        self.synced_files: Set[str] = set()
        self.load_sync_state()
        
    def load_sync_state(self):
        """Load the state of previously synced files."""
        sync_state_file = self.config['sync_state_file']
        if os.path.exists(sync_state_file):
            try:
                with open(sync_state_file, 'r') as f:
                    state = json.load(f)
                    self.synced_files = set(state.get('synced_files', []))
                    print(f"Loaded sync state: {len(self.synced_files)} files previously synced")
            except Exception as e:
                print(f"Error loading sync state: {e}")
                self.synced_files = set()
        else:
            print("No previous sync state found, will sync all files")
            
    def save_sync_state(self):
        """Save the state of synced files."""
        sync_state_file = self.config['sync_state_file']
        try:
            state = {
                'synced_files': list(self.synced_files),
                'last_sync': datetime.now().isoformat()
            }
            with open(sync_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            print(f"Saved sync state: {len(self.synced_files)} files tracked to {sync_state_file}")
        except Exception as e:
            print(f"Error saving sync state: {e}")
            import traceback
            traceback.print_exc()
            
    def authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        token_file = self.config['token_file']
        credentials_file = self.config['credentials_file']
        
        # Load saved credentials
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
                
        # If credentials are invalid or don't exist, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {credentials_file}\n"
                        "Please download your OAuth 2.0 credentials from Google Cloud Console"
                    )
                print("Starting OAuth authentication flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
                
            # Save credentials for future runs
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
                
        self.service = build('drive', 'v3', credentials=creds)
        print("Successfully authenticated with Google Drive")
        
    def get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Get or create a folder in Google Drive."""
        try:
            # Search for existing folder
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                return folder_id
            
            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')
            print(f"Created folder: {folder_name} (ID: {folder_id})")
            return folder_id
            
        except HttpError as error:
            print(f"Error accessing Google Drive folder: {error}")
            raise
            
    def get_folder_id_for_path(self, file_path: Path, source_dir: Path) -> str:
        """Get or create folder structure for file path."""
        # Get relative path from source directory
        rel_path = file_path.relative_to(source_dir)
        path_parts = list(rel_path.parent.parts)
        
        # If preserve_source_structure is enabled, prepend source directory name
        if self.config.get('preserve_source_structure', False):
            source_name = source_dir.name
            path_parts = [source_name] + path_parts
        
        if not path_parts:
            return self.drive_folder_id
            
        current_parent = self.drive_folder_id
        for folder_name in path_parts:
            current_parent = self.get_or_create_folder(folder_name, current_parent)
            
        return current_parent
            
    def should_sync_file(self, file_path: Path) -> bool:
        """Determine if a file should be synced."""
        # Check if already synced
        file_key = str(file_path.resolve())
        if file_key in self.synced_files:
            return False
            
        # Skip .icloud placeholder files
        if file_path.suffix == '.icloud':
            return False
            
        # Check if file is in excluded directory
        exclude_dirs = self.config.get('exclude_directories', [])
        file_parts = file_path.parts
        for exclude_dir in exclude_dirs:
            # Handle absolute paths (like /Applications) vs relative names
            if exclude_dir.startswith('/'):
                # Absolute path - check if file path starts with this
                if str(file_path).startswith(exclude_dir):
                    return False
            else:
                # Relative name - check if it's anywhere in the path
                if exclude_dir in file_parts:
                    return False
                # Also check if the file itself is the excluded directory
                if file_path.name == exclude_dir:
                    return False
            
        # Check modification time if enabled
        if self.config.get('check_modification_time', False):
            hours_threshold = self.config.get('hours_threshold', 24)
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            time_diff = datetime.now() - file_mtime
            if time_diff.total_seconds() > (hours_threshold * 3600):
                return False
            
        # Check file extensions filter
        extensions = self.config.get('file_extensions', [])
        if extensions and file_path.suffix.lower() not in extensions:
            return False
            
        # Check exclude patterns
        exclude_patterns = self.config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            # Handle different pattern types
            if pattern.startswith('._') and file_path.name.startswith('._'):
                return False
            elif pattern.startswith('~$') and file_path.name.startswith('~$'):
                return False
            elif pattern.startswith('.$') and file_path.name.startswith('.$'):
                return False
            elif pattern.startswith('*') and file_path.name.endswith(pattern[1:]):
                return False
            elif pattern == file_path.name:
                return False
            elif '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(file_path.name, pattern):
                    return False
                
        # Check file size
        max_size_mb = self.config.get('max_file_size_mb', 100)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            print(f"Skipping large file: {file_path.name} ({file_size_mb:.2f} MB)")
            return False
            
        return True
        
    def upload_file(self, file_path: Path, source_dir: Path) -> bool:
        """Upload a file to Google Drive maintaining directory structure."""
        try:
            # Get the correct parent folder ID
            parent_folder_id = self.get_folder_id_for_path(file_path, source_dir)
            
            file_metadata = {
                'name': file_path.name,
                'parents': [parent_folder_id]
            }
            
            # MediaFileUpload will automatically detect MIME type based on file extension
            media = MediaFileUpload(str(file_path), resumable=True)
            
            # Show relative path for better context
            rel_path = file_path.relative_to(source_dir)
            print(f"Uploading: {rel_path}...", end=' ')
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            # Mark as synced using consistent path format
            file_key = str(file_path.resolve())
            self.synced_files.add(file_key)
            print(f"✓ (ID: {file.get('id')}) - Tracked: {file_key}")
            
            # Save state after each successful upload
            self.save_sync_state()
            return True
            
        except HttpError as error:
            print(f"✗ Error: {error}")
            return False
        except Exception as error:
            print(f"✗ Error: {error}")
            return False
            
    def sync_directory(self) -> dict:
        """Sync all new files from the source directories."""
        source_dirs = self.config.get('source_directories', [self.config.get('source_directory', '~/Documents')])
        
        # Progress indicator setup
        scanning_complete = threading.Event()
        
        def progress_indicator():
            print("Scanning files... This may take some time, please wait.")
            while not scanning_complete.is_set():
                if scanning_complete.wait(20):  # Wait 20 seconds or until scanning is done
                    break
                print("Still scanning files... This may take some time, please wait.")
        
        # Start progress indicator thread
        progress_thread = threading.Thread(target=progress_indicator, daemon=True)
        progress_thread.start()
        
        all_files = []
        for source_dir_str in source_dirs:
            source_dir = Path(source_dir_str).expanduser()
            
            if not source_dir.exists():
                print(f"Warning: Source directory not found: {source_dir}")
                continue
                
            print(f"\nScanning directory: {source_dir}")
            
            # Find all files in this directory
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    all_files.append(file_path)
        
        # Stop progress indicator
        scanning_complete.set()
        
        print(f"Found {len(all_files)} total files across all directories")
        
        # Filter files that need syncing
        files_to_sync = [f for f in all_files if self.should_sync_file(f)]
        print(f"New files to sync: {len(files_to_sync)}")
        
        if not files_to_sync:
            print("No new files to sync")
            return {'uploaded': 0, 'failed': 0, 'skipped': 0}
            
        # Upload files
        uploaded = 0
        failed = 0
        
        print(f"\nStarting upload to Google Drive folder: {self.config['google_drive_folder']}")
        print("-" * 60)
        
        for file_path in files_to_sync:
            # Find the source directory for this file to maintain relative structure
            source_dir = None
            for source_dir_str in source_dirs:
                potential_source = Path(source_dir_str).expanduser()
                try:
                    file_path.relative_to(potential_source)
                    source_dir = potential_source
                    break
                except ValueError:
                    continue
                    
            if source_dir and self.upload_file(file_path, source_dir):
                uploaded += 1
            else:
                failed += 1
                
        print("-" * 60)
        print(f"Upload complete: {uploaded} succeeded, {failed} failed")
        
        return {
            'uploaded': uploaded,
            'failed': failed,
            'skipped': len(all_files) - len(files_to_sync)
        }
        
    def run(self):
        """Run the sync process."""
        try:
            print("=" * 60)
            print("Mac to Google Drive Sync")
            print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            
            # Authenticate
            self.authenticate()
            
            # Get or create Drive folder
            folder_name = self.config['google_drive_folder']
            self.drive_folder_id = self.get_or_create_folder(folder_name)
            
            # Sync files
            results = self.sync_directory()
            
            # Save state
            self.save_sync_state()
            
            # Clean up local files if enabled
            if self.config.get('cleanup_local_files', False) and results['uploaded'] > 0:
                print(f"\nCleaning up {results['uploaded']} uploaded files from local storage...")
                source_dir = Path(self.config['source_directory']).expanduser()
                for file_key in list(self.synced_files):
                    file_path = Path(file_key)
                    if file_path.exists():
                        try:
                            os.system(f"brctl evict '{file_path}'")
                            print(f"Evicted: {file_path.relative_to(source_dir)}")
                        except Exception as e:
                            print(f"Could not evict {file_path.name}: {e}")
            
            print("\n" + "=" * 60)
            print("Sync Summary:")
            print(f"  Files uploaded: {results['uploaded']}")
            print(f"  Files failed: {results['failed']}")
            print(f"  Files skipped (already synced): {results['skipped']}")
            print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            
            return results['failed'] == 0
            
        except Exception as e:
            print(f"\nError during sync: {e}")
            traceback.print_exc()
            return False


def load_config(config_file: Optional[str] = None) -> dict:
    """Load configuration from file or use defaults."""
    config = DEFAULT_CONFIG.copy()
    
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                config.update(user_config)
            print(f"Loaded configuration from: {config_file}")
        except Exception as e:
            print(f"Error loading config file: {e}")
            print("Using default configuration")
    
    return config


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Sync new files from Mac to Google Drive',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (~/Documents to Google Drive)
  python sync_to_drive.py
  
  # Use custom configuration file
  python sync_to_drive.py --config my_config.json
  
  # Specify source directory directly
  python sync_to_drive.py --source ~/Downloads
  
  # Specify Google Drive folder name
  python sync_to_drive.py --folder "My Backup"
        """
    )
    
    parser.add_argument(
        '--config',
        help='Path to configuration file (JSON)',
        default=None
    )
    
    parser.add_argument(
        '--source',
        help='Source directory to sync (overrides config)',
        default=None
    )
    
    parser.add_argument(
        '--folder',
        help='Google Drive folder name (overrides config)',
        default=None
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without uploading'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with command-line arguments
    if args.source:
        config['source_directory'] = args.source
        
    if args.folder:
        config['google_drive_folder'] = args.folder
        
    # Handle dry-run mode
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No files will be uploaded")
        print("=" * 60)
        print("\nConfiguration:")
        print(json.dumps(config, indent=2))
        
        # Preview what would be synced
        source_dir = Path(config['source_directory']).expanduser()
        if not source_dir.exists():
            print(f"\nError: Source directory not found: {source_dir}")
            return
            
        # Create a temporary sync object to use filtering logic
        sync = GoogleDriveSync(config)
        
        print(f"\nScanning directory: {source_dir}")
        all_files = []
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                all_files.append(file_path)
                
        print(f"Found {len(all_files)} total files")
        
        # Filter files that would be synced
        files_to_sync = [f for f in all_files if sync.should_sync_file(f)]
        already_synced = len(all_files) - len(files_to_sync) - len([f for f in all_files if not sync.should_sync_file(f)])
        
        print(f"\nFiles that would be synced: {len(files_to_sync)}")
        if files_to_sync:
            print("\nPreview (first 10 files):")
            for i, file_path in enumerate(files_to_sync[:10]):
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"  {i+1}. {file_path.name} ({size_mb:.2f} MB)")
            if len(files_to_sync) > 10:
                print(f"  ... and {len(files_to_sync) - 10} more files")
        
        print(f"\nFiles already synced (would be skipped): {len(sync.synced_files)}")
        print("\nNo files were uploaded (dry-run mode)")
        print("=" * 60)
        return
        
    # Run sync
    sync = GoogleDriveSync(config)
    success = sync.run()
    
    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
