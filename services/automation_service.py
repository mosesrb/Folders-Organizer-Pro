# Copyright (c) 2026 mosesrb (Moses Bharshankar). Licensed under GNU GPL-v3.
"""
automation_service.py
7 advanced automation operations for Folders Organizer Pro.
All destructive operations support dry_run=True for safe simulation.
"""
import os
import re
import shutil
import datetime
import zipfile
try:
    import py7zr
except ImportError:
    py7zr = None
try:
    import rarfile
except ImportError:
    rarfile = None

from pathlib import Path

# Protected system extensions/names — never touch these during cleanup
_PROTECTED_EXTS = {'.lnk', '.ini', '.sys', '.inf', '.dll', '.icl', '.theme'}
_PROTECTED_NAMES = {'desktop.ini', 'thumbs.db', '.ds_store'}


def _safe_dest(target_dir: Path, filename: str) -> Path:
    """Collision-safe destination. Appends _1, _2... if file exists."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    dest = target_dir / filename
    counter = 1
    while dest.exists():
        dest = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest


# ──────────────────────────────────────────────
# 1. Empty Folder Cleanup
# ──────────────────────────────────────────────
def delete_empty_folders(path: str, dry_run: bool, progress_callback) -> tuple:
    """Recursively finds and removes all empty directories."""
    p = Path(path)
    empty_dirs = []

    def _collect(target: Path):
        for entry in sorted(target.rglob('*'), key=lambda x: len(x.parts), reverse=True):
            if entry.is_dir() and entry != p:
                try:
                    if not any(f for f in entry.iterdir() if f.name != '.organizer_history.json'):
                        empty_dirs.append(entry)
                except PermissionError:
                    pass

    _collect(p)

    if not empty_dirs:
        return [], 0

    total = len(empty_dirs)
    removed = []
    for idx, d in enumerate(empty_dirs):
        if not dry_run:
            try:
                d.rmdir()
                removed.append(str(d))
            except OSError:
                pass
        else:
            removed.append(str(d))
        progress_callback(int(((idx + 1) / total) * 100))

    return removed, total


# ──────────────────────────────────────────────
# 2. Advanced Regex Rename
# ──────────────────────────────────────────────
def advanced_regex_rename(path: str, pattern: str, replacement: str, dry_run: bool, progress_callback) -> tuple:
    """Batch rename files using regex find/replace."""
    p = Path(path)
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    files = [f for f in p.iterdir() if f.is_file() and f.name != '.organizer_history.json']
    matches = [f for f in files if regex.search(f.name)]

    if not matches:
        return [], 0

    total = len(matches)
    history = []
    for idx, file in enumerate(matches):
        new_name = regex.sub(replacement, file.name)
        new_path = file.with_name(new_name)

        if not dry_run:
            # Collision guard
            final = new_path
            counter = 1
            while final.exists():
                try:
                    if final.samefile(file):
                        break
                except: pass
                stem = Path(new_name).stem
                suffix = Path(new_name).suffix
                final = file.parent / f"{stem}_{counter}{suffix}"
                counter += 1
            os.rename(file, final)
            history.append({"action": "move", "src": str(file), "dst": str(final)})
        else:
            history.append((str(file), str(new_path)))

        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 3. Old File Cleanup
# ──────────────────────────────────────────────
def cleanup_old_files(path: str, days: int, dry_run: bool, progress_callback) -> tuple:
    """
    Moves files older than `days` into a '.archived_files' subfolder.
    Skips protected extensions and system filenames.
    """
    p = Path(path)
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    archive_dir = p / '.archived_files'

    candidates = []
    for f in p.iterdir():
        if not f.is_file() or f.name == '.organizer_history.json':
            continue
        if f.name.lower() in _PROTECTED_NAMES:
            continue
        if f.suffix.lower() in _PROTECTED_EXTS:
            continue
        try:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                candidates.append(f)
        except OSError:
            pass

    if not candidates:
        return [], 0

    total = len(candidates)
    history = []
    for idx, f in enumerate(candidates):
        if not dry_run:
            archive_dir.mkdir(exist_ok=True)
            dest = _safe_dest(archive_dir, f.name)
            shutil.move(str(f), str(dest))
            history.append({"action": "move", "src": str(f), "dst": str(dest)})
        else:
            history.append((str(f), str(archive_dir / f.name)))
        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 4. Batch Unzipper
# ──────────────────────────────────────────────
def batch_unzip(path: str, dry_run: bool, progress_callback) -> tuple:
    """Extracts common archives (.zip, .rar, .7z, .tar, etc.) into named subfolders."""
    p = Path(path)
    # Detect a wider range of archive formats
    archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}
    archives = [f for f in p.iterdir() if f.is_file() and f.name != '.organizer_history.json' and f.suffix.lower() in archive_exts]

    if not archives:
        return [], 0, []

    history = []
    errors = []
    for idx, zf in enumerate(archives):
        # Use collision-safe destination
        out_dir = _safe_dest(p, zf.stem)
        
        if not dry_run:
            try:
                # Special handling for different formats
                suffix = zf.suffix.lower()
                
                if suffix == '.7z':
                    if py7zr:
                        with py7zr.SevenZipFile(str(zf), mode='r') as archive:
                            archive.extractall(path=str(out_dir))
                    else:
                        raise ImportError("py7zr library is missing. Cannot extract .7z files.")
                
                elif suffix == '.rar':
                    if rarfile:
                        # Attempt to find unrar/7z if not already configured
                        try:
                            with rarfile.RarFile(str(zf)) as archive:
                                archive.extractall(path=str(out_dir))
                        except rarfile.RarCannotExec:
                            # Try to find common installation paths for unrar.exe or 7z.exe
                            common_paths = [
                                r"C:\Program Files\WinRAR\UnRAR.exe",
                                r"C:\Program Files\7-Zip\7z.exe",
                                r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
                                r"C:\Program Files (x86)\7-Zip\7z.exe"
                            ]
                            found = False
                            for tool in common_paths:
                                if os.path.exists(tool):
                                    rarfile.TOOL_PATH = tool
                                    found = True
                                    break
                            
                            if found:
                                with rarfile.RarFile(str(zf)) as archive:
                                    archive.extractall(path=str(out_dir))
                            else:
                                raise RuntimeError("RAR extraction requires WinRAR or 7-Zip installed in standard locations, or UnRAR.exe in PATH.")
                    else:
                        raise ImportError("rarfile library is missing. Cannot extract .rar files.")
                
                else:
                    # shutil handles multiple formats automatically (zip, tar, etc.)
                    shutil.unpack_archive(str(zf), str(out_dir))
                
                # Double check if anything was extracted
                if out_dir.exists() and not any(out_dir.iterdir()):
                    raise RuntimeError("Archive appeared to extract successfully but resulted in an empty folder.")
                
                history.append({"action": "create", "src": str(zf), "dst": str(out_dir)})
            except Exception as e:
                # Cleanup if folder was partially created or left empty
                if out_dir.exists():
                    try:
                        shutil.rmtree(out_dir)
                    except:
                        pass
                
                err_msg = str(e)
                if isinstance(e, shutil.ReadError):
                    err_msg = f"Format {zf.suffix} not supported by standard library. Please ensure additional tools are installed."
                errors.append(f"{zf.name}: {err_msg}")
        else:
            history.append({"action": "create", "src": str(zf), "dst": str(out_dir)})
        
        progress_callback(int(((idx + 1) / len(archives)) * 100))

    return history, len(history), errors



# ──────────────────────────────────────────────
# 5. Large File Archiver
# ──────────────────────────────────────────────
def archive_large_files(path: str, threshold_mb: float, dry_run: bool, progress_callback) -> tuple:
    """Moves files exceeding threshold_mb into a 'LargeFiles' subfolder."""
    p = Path(path)
    threshold_bytes = threshold_mb * 1024 * 1024
    large_dir = p / 'LargeFiles'

    candidates = []
    for f in p.iterdir():
        if not f.is_file() or f.name == '.organizer_history.json':
            continue
        try:
            if f.stat().st_size >= threshold_bytes:
                candidates.append(f)
        except OSError:
            pass

    if not candidates:
        return [], 0

    total = len(candidates)
    history = []
    for idx, f in enumerate(candidates):
        if not dry_run:
            large_dir.mkdir(exist_ok=True)
            dest = _safe_dest(large_dir, f.name)
            shutil.move(str(f), str(dest))
            history.append({"action": "move", "src": str(f), "dst": str(dest)})
        else:
            history.append((str(f), str(large_dir / f.name)))
        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 6. Additive Backup
# ──────────────────────────────────────────────
def additive_backup(src: str, dest: str, dry_run: bool, progress_callback) -> tuple:
    """
    Copies files from src to dest only if:
    - File does not exist in dest, OR
    - Source file is newer than dest file.
    Never deletes from dest.
    """
    src_p = Path(src)
    dest_p = Path(dest)

    candidates = []
    for f in src_p.rglob('*'):
        if not f.is_file() or f.name == '.organizer_history.json':
            continue
        rel = f.relative_to(src_p)
        target = dest_p / rel
        if not target.exists():
            candidates.append((f, target))
        else:
            try:
                src_mtime = f.stat().st_mtime
                dst_mtime = target.stat().st_mtime
                if src_mtime > dst_mtime:
                    candidates.append((f, target))
            except OSError:
                pass

    if not candidates:
        return [], 0

    total = len(candidates)
    history = []
    for idx, (src_f, dst_f) in enumerate(candidates):
        if not dry_run:
            dst_f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_f), str(dst_f))
            history.append({"action": "copy", "src": str(src_f), "dst": str(dst_f)})
        else:
            history.append((str(src_f), str(dst_f)))
        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 7. Image Format Converter
# ──────────────────────────────────────────────
def convert_image_formats(path: str, source_exts: list, target_ext: str, dry_run: bool, progress_callback) -> tuple:
    """
    Converts images to target_ext using Pillow.
    source_exts: list of extensions to convert e.g. ['.png', '.bmp']
    target_ext: e.g. '.webp' or '.jpg'
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow not installed. Run: pip install Pillow")

    p = Path(path)
    if not target_ext.startswith('.'):
        target_ext = '.' + target_ext

    # Normalize source extensions
    source_set = {(e if e.startswith('.') else f'.{e}').lower() for e in source_exts}

    files = [f for f in p.iterdir() if f.is_file() and f.name != '.organizer_history.json' and f.suffix.lower() in source_set]
    if not files:
        return [], 0

    total = len(files)
    history = []
    pil_format_map = {
        '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG',
        '.webp': 'WEBP', '.bmp': 'BMP', '.tiff': 'TIFF', '.gif': 'GIF'
    }
    out_format = pil_format_map.get(target_ext.lower(), target_ext.upper().lstrip('.'))

    for idx, f in enumerate(files):
        new_name = f.stem + target_ext
        new_path = _safe_dest(p, new_name)

        if not dry_run:
            try:
                img = Image.open(f)
                # Convert RGBA → RGB for JPEG
                if out_format == 'JPEG' and img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(new_path, out_format)
                history.append({"action": "create", "src": str(f), "dst": str(new_path)})
            except Exception as e:
                history.append((str(f), f"ERROR: {e}"))
        else:
            history.append((str(f), str(new_path)))

        progress_callback(int(((idx + 1) / total) * 100))

    return history, total
