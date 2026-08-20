# Folders Organizer Pro

Folders Organizer Pro is a local Windows desktop application for scanning, sorting, batch renaming, deduplicating, and archiving files and directory trees. It combines a Python backend with a React user interface, packaged as a native desktop window using PyWebView.

All operations run entirely on the local system with no cloud dependencies, external servers, or background telemetry.

---

## Overview & Architecture

```
┌─────────────────────────────────┐       window.pywebview.api       ┌─────────────────────────────────┐
│     React 18 UI (Vite)          │ ───────────────────────────────▶ │     Python Engine (organizer.py)│
│  - 3-column workspace layout    │ ◀─────────────────────────────── │  - Input validation & guards    │
│  - "Filing Cabinet" theme       │         Live event stream        │  - Undo snapshots & dry-run     │
│  - Light & Dark mode support    │                                  └────────────────┬────────────────┘
└─────────────────────────────────┘                                                   │
                                                                     ┌────────────────┴────────────────┐
                                                                     │            services/            │
                                                                     │  - file_service                 │
                                                                     │  - organizer_service            │
                                                                     │  - duplicate_service            │
                                                                     │  - automation_service           │
                                                                     │  - media_service                │
                                                                     └─────────────────────────────────┘
```

---

## Key Features

### 1. Organization & Sorting
- **Smart Categorization**: Group files into structured subdirectories (Documents, Images, Audio, Video, Code, Archives) based on file type.
- **Custom Rules Engine**: Define keyword-to-folder mapping rules with priority handling over default classifications.
- **Date-Based Organization**: Sort files into structured hierarchies by year, month, or day using file metadata.
- **Directory Flattening**: Recursively pull nested files to the root directory with collision resolution.

### 2. Batch Renaming
- **Pattern-Based Renaming**: Apply custom prefixes, suffixes, and sequential numbering formats.
- **Extension Changer**: Batch update or standardize file extensions across directories with full undo support.
- **Regex Search & Replace**: Match and replace filename patterns using Python regular expressions.

### 3. Duplicate Detection
- **Content-Based Hashing**: Identifies duplicate files using multi-stage hashing (file size verification, partial hash, and full MD5 hash) regardless of filename differences.
- **Selective Retention**: Keep oldest, newest, or shallowest copies when clearing duplicate groups.
- **Recycle Bin Integration**: Removes duplicates safely via `send2trash` instead of permanent filesystem deletion.

### 4. Advanced Automation
- **Batch Folder Zipper**: Archive multiple selected directories into individual `.zip` archives with support for custom file extensions (such as `.cbz` or `.bak`) and optional safe deletion of source folders.
- **Archive Extraction**: Extract `.zip`, `.tar`, `.7z`, and `.rar` archives with zip-slip path traversal guards.
- **Additive Backup**: Incremental folder synchronization that copies only new or modified files.
- **Empty Directory Pruning**: Recursive bottom-up cleanup of empty directory trees.

### 5. Media Processing
- **Audio Conversion**: MP3 to WAV conversion using `miniaudio`.
- **Image Optimization**: Batch compression and resizing via `Pillow`.
- **PDF Compression**: Document compression using `pypdf`.

---

## Safety & System Guards

Bulk filesystem operations include safeguards against data loss:

- **Simulation Mode (Dry Run)**: Test any operation before writing to disk. The application calculates planned source-to-destination paths and displays them in a preview modal.
- **System Directory Guard**: Destructive operations are blocked on system-critical paths, including `C:\`, `C:\Windows`, `C:\Program Files`, `C:\Program Files (x86)`, and bare drive roots.
- **Atomic Undo History**: Mutating operations record changes to a local `.organizer_history.json` snapshot using atomic writes, allowing one-click rollback of renames and file moves.
- **Path Traversal Protection**: Archive extractions validate member paths to block directory traversal attacks (`../` extraction).

---

## Quick Start

### Prerequisites
- **Python 3.10+** (with `pip`)
- **Node.js 18+** and `npm` (for building the UI)

### Automated Setup (Windows)

1. Clone or download the repository.
2. Run `setup.bat` to install Python dependencies, install npm packages, and build the React frontend:
   ```cmd
   setup.bat
   ```
3. Launch the application:
   ```cmd
   Start Organizer.bat
   ```

### Manual Installation

If you prefer setting up the environment manually:

```bash
# 1. Install backend dependencies
pip install -r requirements.txt

# 2. Build the React frontend
cd ui
npm install
npm run build
cd ..

# 3. Start the application
python organizer.py
```

---

## Development & Testing

### Running the Frontend Dev Server
To work on the React UI in a standard browser with mock API fallbacks:

```bash
cd ui
npm run dev
```

### Running Backend Unit Tests
The test suite covers service operations, path guards, archive safety, and duplicate detection without requiring the PyWebView GUI:

```bash
python -m unittest tests.test_services
```

---

## Repository Structure

```
Folders-Organizer-Pro/
├── organizer.py             # PyWebView application entrypoint & API bridge
├── requirements.txt         # Python dependencies
├── setup.bat                # Automated setup and build script
├── Start Organizer.bat      # Application launcher script
├── branding/                # SVG source assets and icon files
├── docs/                    # UI screenshots and project documentation
│   └── assets/              # Interface screenshots
├── services/                # Backend business logic
│   ├── automation_service.py # Cleanup, backups, and batch zipping
│   ├── duplicate_service.py  # Content hashing & duplicate management
│   ├── file_service.py       # Workspace scanning & folder analytics
│   ├── media_service.py      # Audio, image, and PDF processing
│   └── organizer_service.py  # Sorting, flattening, and renaming engine
├── tests/                   # Unit test suite
│   └── test_services.py     # Backend service and safety guard tests
└── ui/                      # React frontend
    ├── package.json
    ├── tailwind.config.js   # "Filing Cabinet" theme definition
    └── src/
        ├── App.jsx          # Main application UI and view components
        └── index.css        # CSS variables for light/dark themes
```

---

## License

Distributed under the GNU General Public License v3 (GPLv3). See [LICENSE](LICENSE) for full details.

