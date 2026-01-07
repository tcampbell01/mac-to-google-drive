# Mac to Google Drive Sync

Automatically sync new files from your Mac to Google Drive once a day.

## Features

- 🔄 Daily synchronization via macOS launchd
- 📁 Tracks previously uploaded files (no duplicates)
- 🎯 Configurable source directory and file filters
- 📊 File size limits and exclude patterns
- 🔐 Secure OAuth 2.0 authentication with Google
- 📝 Detailed logging and progress reports

## Quick Start

1. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Configure Google Drive API**:
   - Download `credentials.json` from Google Cloud Console
   - Place in this directory

3. **Set up configuration**:
   ```bash
   cp config.example.json config.json
   # Edit config.json with your settings
   ```

4. **First run** (authentication):
   ```bash
   python3 mac_to_drive_sync.py --config config.json
   ```

5. **Set up daily automation**:
   ```bash
   # Edit paths in mac_drive_sync.plist
   cp mac_drive_sync.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/mac_drive_sync.plist
   ```

## Configuration Options

```json
{
  "source_directory": "~/Documents",
  "google_drive_folder": "Mac Backup",
  "file_extensions": [".pdf", ".docx", ".jpg"],
  "exclude_patterns": [".DS_Store", "._*"],
  "max_file_size_mb": 100
}
```

## Related Repositories

This is part of a larger file management system:

- **[drive-to-s3-lambda](https://github.com/tcampbell01/google-drive-to-s3)** - Backs up Google Drive to AWS S3
- **[synagogue-file-search](https://github.com/tcampbell01/synagogue-file-search)** - Web interface to search files

## Troubleshooting

- **Authentication errors**: Delete `token.pickle` and re-run
- **File not syncing**: Check `logs/sync.log` for details
- **Permission errors**: Ensure script can read source directory

## License

MIT License - See [LICENSE](./LICENSE) for details.