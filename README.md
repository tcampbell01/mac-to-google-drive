# Mac to Google Drive Auto Sync

Automatically sync new files from your Mac to Google Drive once a day. This script tracks which files have been uploaded and only syncs new files on subsequent runs.

## Features

- 🔄 Automatic daily synchronization
- 📁 Tracks previously uploaded files (no duplicates)
- 🎯 Configurable source directory and file filters
- 📊 File size limits and exclude patterns
- 🔐 Secure OAuth 2.0 authentication with Google
- 📝 Detailed logging and progress reports
- ⚙️ Easy configuration via JSON file or command-line arguments

## Prerequisites

- macOS (for launchd scheduling)
- Python 3.7 or higher
- Google Cloud Project with Drive API enabled
- Google OAuth 2.0 credentials

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/tcampbell01/mac-to-google-drive.git
cd mac-to-google-drive
```

### 2. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Set Up Google Drive API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Download the credentials file
   - Save it as `credentials.json` in the project directory

### 4. Configure the Script

Create a configuration file (or use the example):

```bash
cp config.example.json config.json
```

Edit `config.json` to customize your settings:

```json
{
  "source_directory": "~/Documents",
  "google_drive_folder": "Mac Backup",
  "credentials_file": "credentials.json",
  "token_file": "token.pickle",
  "sync_state_file": "sync_state.json",
  "file_extensions": [],
  "exclude_patterns": [".DS_Store", "._*", "Thumbs.db"],
  "max_file_size_mb": 100
}
```

**Configuration Options:**

- `source_directory`: Local directory to sync from (default: `~/Documents`)
- `google_drive_folder`: Name of the folder in Google Drive to sync to
- `credentials_file`: Path to your Google OAuth credentials file
- `token_file`: Path where authentication token will be saved
- `sync_state_file`: Path where sync state is tracked
- `file_extensions`: List of file extensions to sync (empty = all files). Example: `[".pdf", ".docx", ".jpg"]`
- `exclude_patterns`: Files matching these patterns will be skipped
- `max_file_size_mb`: Maximum file size to upload (in MB)

### 5. First Run (Authentication)

Run the script manually for the first time to authenticate:

```bash
python3 sync_to_drive.py --config config.json
```

This will:
1. Open a browser window for Google authentication
2. Ask you to grant Drive API permissions
3. Save the authentication token for future runs
4. Sync all new files from your source directory

## Setting Up Daily Automation

### Using launchd (macOS)

1. Edit the plist file to set your paths:

```bash
# Open the plist file
nano com.user.mac-to-google-drive.plist
```

Replace `YOUR_USERNAME` with your actual username and update paths as needed.

2. Create logs directory:

```bash
mkdir -p logs
```

3. Copy the plist file to LaunchAgents:

```bash
cp com.user.mac-to-google-drive.plist ~/Library/LaunchAgents/
```

4. Load the launch agent:

```bash
launchctl load ~/Library/LaunchAgents/com.user.mac-to-google-drive.plist
```

5. Verify it's loaded:

```bash
launchctl list | grep mac-to-google-drive
```

The script will now run automatically every day at 2:00 AM. You can change the schedule by modifying the `StartCalendarInterval` in the plist file.

### Managing the Scheduled Task

**Unload (stop) the scheduled task:**
```bash
launchctl unload ~/Library/LaunchAgents/com.user.mac-to-google-drive.plist
```

**Reload (after making changes):**
```bash
launchctl unload ~/Library/LaunchAgents/com.user.mac-to-google-drive.plist
launchctl load ~/Library/LaunchAgents/com.user.mac-to-google-drive.plist
```

**Test the scheduled task manually:**
```bash
launchctl start com.user.mac-to-google-drive
```

**Check logs:**
```bash
tail -f logs/sync.log
tail -f logs/sync_error.log
```

## Usage

### Command-Line Options

```bash
# Run with default configuration
python3 sync_to_drive.py

# Use custom configuration file
python3 sync_to_drive.py --config my_config.json

# Override source directory
python3 sync_to_drive.py --source ~/Downloads

# Override Google Drive folder name
python3 sync_to_drive.py --folder "My Backup"

# Dry run (preview without uploading)
python3 sync_to_drive.py --dry-run
```

### How It Works

1. **First Run**: The script scans your source directory and uploads all files to Google Drive
2. **Subsequent Runs**: Only new files (files not in the sync state) are uploaded
3. **State Tracking**: A `sync_state.json` file tracks which files have been uploaded
4. **Smart Filtering**: Files are filtered based on:
   - Previously synced (skipped)
   - File extensions (if specified)
   - Exclude patterns (e.g., .DS_Store)
   - File size limits

## Security Considerations

- **Credentials**: The `credentials.json` and `token.pickle` files contain sensitive data
  - These files are automatically excluded from git via `.gitignore`
  - Keep these files secure and never share them
- **Authentication**: Uses OAuth 2.0 for secure authentication
- **Permissions**: The script only requests file-level access (not full Drive access)

## Troubleshooting

### Authentication Issues

If you encounter authentication errors:

1. Delete `token.pickle` and re-authenticate:
   ```bash
   rm token.pickle
   python3 sync_to_drive.py
   ```

2. Verify your credentials file is valid and from the correct Google Cloud project

### Files Not Syncing

1. Check the logs for errors
2. Verify file extensions and exclude patterns in your config
3. Check file size limits
4. Ensure the file hasn't been synced before (check `sync_state.json`)

### Permission Errors

Ensure the script has permission to:
- Read files in your source directory
- Write to the project directory (for state files and logs)

### Reset Sync State

To re-sync all files (start fresh):

```bash
rm sync_state.json
python3 sync_to_drive.py
```

## File Structure

```
mac-to-google-drive/
├── sync_to_drive.py              # Main script
├── requirements.txt              # Python dependencies
├── config.example.json           # Example configuration
├── config.json                   # Your configuration (create this)
├── credentials.json              # Google OAuth credentials (download this)
├── com.user.mac-to-google-drive.plist  # launchd configuration
├── token.pickle                  # Saved authentication token (auto-generated)
├── sync_state.json               # Sync state tracking (auto-generated)
├── logs/                         # Log files (auto-generated)
│   ├── sync.log
│   └── sync_error.log
└── README.md                     # This file
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.