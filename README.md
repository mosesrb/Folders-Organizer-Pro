# 📂 Folders Organizer Pro (v4.0.0)
> **A targeted solution for Windows digital workspace entropy.**

Born from the frustrations of managing massive, cluttered Windows directories, **Folders Organizer Pro** is a high-performance utility designed to turn chaos into structure in seconds.

---

## 🔥 Key Features

### 🧠 Intelligent Rule Engine
Automatically categorizes your files using a hybrid of extension mapping and keyword intelligence.
- **Auto-Sorting**: Detects `Work`, `Media`, `Archive`, `Personal`, and `Code` assets.
- **Custom Persistence**: Saves workspace-specific rules in a local `.organizer_rules.json` file.
- **Local-First**: No data leaves your machine; everything is processed locally.

### 🔢 Sequential Advanced Renamer
Batch renaming with professional precision.
- **Date-Relative Indexing**: Rename based on file creation or modification date.
- **Alpha-Numerical Reindexing**: Clean up messy numbering schemes.
- **Undo Support**: Reclaim your original names with a single click.

### 🕰️ Time Capsule (Date Sorting)
Instantly sweeps thousands of assets into a logical `Year / Month / Day` structure. Ideal for photo dumps and long-term archiving.

### 🕵️ Duplicate Hunter
Identifies identical files using **MD5 content hashing** (not just filename comparison). Safely identifies space-hogs and helps reclaim storage.

### 🏗️ Workspace Flattener
Pulls every file from deep nesting up to the root path and cleanly prunes empty folder shells.

---

## 🛡️ Reliability & Safety

- **🛡️ Simulation Mode (Dry-Run)**: Run any operation in "Preview Mode" to see exactly what *would* happen in the logs before moving a single byte.
- **🔄 Global Undo**: Mistakes happen. Undo Renaming, Sorting, and Categorizing batches instantly.
- **📊 Real-Time Analytics**: Category breakdown, largest asset identification, and high-fidelity asset previews.

---

## 🚀 Quick Start

1. **Prerequisites**
   - Python 3.10+
   - Node.js (for frontend setup)

2. **Setup**
   - Run `setup.bat` (Automated Installer)
   - OR manually:
     ```bash
     pip install pywebview
     cd ui && npm install && npm run build
     ```

3. **Run**
   - Launch `python organizer.py` or use the provided shortcuts.

---

## 💻 Tech Stack
- **Backend**: Python 3.10+ (pywebview)
- **Frontend**: React 18 / Vite (Glassmorphism UI)
- **Styling**: Tailwind CSS

## 🛡️ License
MIT License - Created for local-first, privacy-conscious file management.
