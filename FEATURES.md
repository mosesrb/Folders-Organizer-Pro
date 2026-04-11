# 📂 Folders Organizer Pro (v4)
> **A targeted solution for Windows digital workspace entropy.**

Born from the frustrations of managing massive, cluttered Windows directories, **Folders Organizer Pro** is a high-performance utility designed to turn chaos into structure in seconds.

---

## 🔥 Key Features

### 🧠 Intelligent Rule Engine
Automatically categorizes your files using a hybrid of extension mapping and keyword intelligence.
- **Auto-Sorting**: Detects `Work`, `Media`, `Archive`, `Personal`, and `Code` assets.
- **Custom Persistence**: Saves workspace-specific rules in a local `.organizer_rules.json` file.
- **Local-First**: No data leaves your machine; everything is processed using native filesystem operations.

### 🔢 Sequential Advanced Renamer
Batch renaming with professional precision.
- **Date-Relative Indexing**: Rename based on file creation or modification date.
- **Alpha-Numerical Reindexing**: Clean up messy numbering schemes.
- **Undo Support**: Reclaim your original names with a single click if you change your mind.

### 🕰️ Time Capsule (Date Sorting)
Instantly sweeps thousands of assets into a logical `Year / Month / Day` structure.
- Ideal for photo dumps, log management, and long-term archiving.

### 🕵️ Duplicate Hunter
Identifies identical files using **MD5 content hashing** (not just filename comparison).
- Safely identifies space-hogs and helps reclaim gigabytes of storage.

### 🏗️ Workspace Flattener
Pulls every file from deep nesting up to the root path and cleanly prunes the empty folder shells left behind.

---

## 🛡️ Reliability & Safety

### 🛡️ Simulation Mode (Dry-Run)
The ultimate anxiety-saver. Run any operation in "Preview Mode" to see exactly what *would* happen in the logs before moving a single byte.

### 🔄 Global Undo
Mistakes happen. The internal history tracker allows you to undo Renaming, Sorting, and Categorizing batches instantly.

### 📊 Real-Time Analytics
- **Category breakdown** visualization.
- **Largest assets** identification.
- **High-fidelity previews** for images and videos with metadata analysis.

---

## 💻 Tech Stack
- **Backend**: Python 3.10+ (pywebview)
- **Frontend**: React 18 / Vite (Glassmorphism UI)
- **Styling**: Tailwind CSS
