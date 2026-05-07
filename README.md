# ScrubMetaDub

**ScrubMetaDub** is a powerful, user-friendly tool for removing metadata from images (JPG, PNG, TIFF, WebP) and PDFs. It helps protect privacy by scrubbing EXIF data, GPS coordinates, camera information, and other embedded metadata that could reveal sensitive information.

## Features

- **Comprehensive Metadata Removal**: Removes all EXIF data, GPS coordinates, camera settings, and timestamps from images
- **PDF Support**: Scrubs document information (DocInfo) and XMP metadata from PDF files
- **Selective Scrubbing**: Option to remove specific EXIF tags while preserving others
- **Batch Processing**: Process multiple files and entire folders at once
- **Backup & Safety**: Automatic backup to ZIP archives before processing
- **Verification**: Re-scan output files to verify metadata removal
- **Advanced Processing**:
  - Watermarking
  - Image resizing
  - Format conversion
  - Timestamp preservation
- **GUI & CLI**: Both graphical interface and command-line options
- **Export Metadata**: Save metadata to text files before scrubbing
- **Session Reports**: Generate PDF reports of processing sessions
- **Drag & Drop**: Easy file addition in GUI mode
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

### Requirements

- Python 3.6+
- Required: `Pillow` (PIL) library for image processing
- Optional: `pikepdf` for PDF support
- Optional: `tkinterdnd2` for drag-and-drop in GUI
- Optional: `reportlab` for PDF reports

### Install Dependencies

```bash
pip install pillow pikepdf tkinterdnd2 reportlab
```

### Download

Clone or download the `scrubmetadub.py` file from this repository.

## Usage

### GUI Mode (Recommended for beginners)

```bash
python scrubmetadub.py --gui
```

Or simply run without arguments:

```bash
python scrubmetadub.py
```

The GUI provides an intuitive interface with:
- File/folder selection
- Preview metadata before scrubbing
- Visual comparison of before/after images
- Progress tracking
- Configurable options via tabs

### Command Line Mode

```bash
python scrubmetadub.py [files/folders] [options]
```

#### Examples

Scrub a single image:
```bash
python scrubmetadub.py photo.jpg
```

Scrub multiple files:
```bash
python scrubmetadub.py image1.jpg image2.png document.pdf
```

Scrub a folder recursively:
```bash
python scrubmetadub.py /path/to/photos/
```

Overwrite originals (dangerous!):
```bash
python scrubmetadub.py --overwrite photos/
```

Remove only GPS data:
```bash
python scrubmetadub.py --remove-tags GPS photos/
```

Resize and convert format:
```bash
python scrubmetadub.py --resize 800x600 --convert png photos/
```

Generate report:
```bash
python scrubmetadub.py --report --export-metadata photos/
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite original files instead of creating copies |
| `--output DIR` | Specify output directory |
| `--prefix TEXT` | Add prefix to output filenames |
| `--suffix TEXT` | Add suffix to output filenames |
| `--delete` | Delete original files after successful scrubbing |
| `--backup` | Create ZIP backup before processing |
| `--preserve-time` | Keep original file timestamps |
| `--open` | Open output folder when done |
| `--remove-tags TAGS` | Remove specific EXIF tags (comma-separated) |
| `--verify` | Re-scan files to verify metadata removal |
| `--watermark TEXT` | Add watermark to images |
| `--resize WxH` | Resize images (e.g., 800x600, 800x, x600) |
| `--convert FORMAT` | Convert to different format (jpg, png, webp, etc.) |
| `--export-metadata` | Save metadata to .txt files before scrubbing |
| `--report` | Generate PDF session report |
| `--gui` | Launch graphical interface |

## Supported Formats

- **Images**: JPG/JPEG, PNG, TIFF/TIF, WebP
- **Documents**: PDF

## Safety Features

- **Backup Creation**: Automatically creates timestamped ZIP backups
- **Non-Destructive by Default**: Creates new files with "_scrubbed" suffix
- **Verification**: Optional re-scanning to confirm metadata removal
- **Error Handling**: Graceful handling of corrupted files
- **Dependency Checks**: Warns about missing optional libraries

## Privacy & Security

ScrubMetaDub helps protect your privacy by removing:

- GPS coordinates and location data
- Camera make/model and serial numbers
- Date/time stamps
- Software used to create/edit files
- User comments and descriptions
- Thumbnail images
- Color profiles and ICC data

## Troubleshooting

### Common Issues

**"Pillow library missing"**
```bash
pip install pillow
```

**"pikepdf not installed"**
```bash
pip install pikepdf
```

**GUI not launching**
- Ensure Tkinter is installed (usually included with Python)
- Try command-line mode first

**Permission errors**
- Ensure write access to output directories
- On Linux/macOS, check file permissions

### Dependencies

The script checks for optional dependencies at startup and provides installation instructions for missing libraries.

## Version History

- **v1.1.0**: Added PDF support, selective tag removal, watermarking, resizing, format conversion, session reports
- **v1.0.0**: Initial release with basic image metadata scrubbing

## License

This project is open-source. Please check the license file for details.

## Contributing

Contributions welcome! Please submit issues and pull requests on GitHub.

## Disclaimer

Use at your own risk. Always backup important files before processing. The authors are not responsible for data loss.