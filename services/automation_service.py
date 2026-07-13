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
import tarfile
try:
    import py7zr
except ImportError:
    py7zr = None
try:
    import rarfile
except ImportError:
    rarfile = None

from pathlib import Path
from .file_service import safe_dest as _safe_dest

# Protected system extensions/names — never touch these during cleanup
_PROTECTED_EXTS = {'.lnk', '.ini', '.sys', '.inf', '.dll', '.icl', '.theme'}
_PROTECTED_NAMES = {'desktop.ini', 'thumbs.db', '.ds_store'}


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
def advanced_regex_rename(path: str, pattern: str, replacement: str, dry_run: bool, progress_callback, recursive: bool = False) -> tuple:
    """Batch rename files using regex find/replace.
    recursive=True processes files in subfolders too (previously this
    operation silently only ever touched the top level, with no way to
    tell from the UI).
    """
    p = Path(path)
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    if recursive:
        files = [f for f in p.rglob('*') if f.is_file() and f.name != '.organizer_history.json']
    else:
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
            history.append({"action": "move", "src": str(file), "dst": str(new_path)})

        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 3. Old File Cleanup
# ──────────────────────────────────────────────
def cleanup_old_files(path: str, days: int, dry_run: bool, progress_callback, recursive: bool = False) -> tuple:
    """
    Moves files older than `days` into a '.archived_files' subfolder.
    Skips protected extensions and system filenames.
    recursive=True also finds candidates in subfolders.
    """
    p = Path(path)
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    archive_dir = p / '.archived_files'

    source_iter = p.rglob('*') if recursive else p.iterdir()
    candidates = []
    for f in source_iter:
        if not f.is_file() or f.name == '.organizer_history.json':
            continue
        if f.name.lower() in _PROTECTED_NAMES:
            continue
        if f.suffix.lower() in _PROTECTED_EXTS:
            continue
        if archive_dir in f.parents:
            continue  # don't re-archive already-archived files
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
        dest = archive_dir / f.name
        if not dry_run:
            archive_dir.mkdir(exist_ok=True)
            dest = _safe_dest(archive_dir, f.name)
            shutil.move(str(f), str(dest))
        history.append({"action": "move", "src": str(f), "dst": str(dest)})
        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 4. Batch Unzipper
# ──────────────────────────────────────────────

class ArchiveSecurityError(Exception):
    """Raised when an archive contains a member that would escape the
    intended extraction directory (a.k.a. "zip slip" / path traversal)."""
    pass


def _assert_member_is_safe(member_name: str, out_dir: Path) -> Path:
    """Resolves a member's target path and verifies it stays inside out_dir.
    Rejects absolute paths, '..' traversal, and (on Windows) drive-letter
    or UNC prefixes embedded in the member name.
    """
    if not member_name or member_name.strip() in ('', '.', '..'):
        raise ArchiveSecurityError(f"Unsafe archive entry name: {member_name!r}")

    # Reject absolute paths / drive letters outright before any join.
    raw = member_name.replace('\\', '/')
    if raw.startswith('/') or (len(raw) > 1 and raw[1] == ':'):
        raise ArchiveSecurityError(f"Archive entry has an absolute path: {member_name!r}")

    out_dir_resolved = out_dir.resolve(strict=False)
    target = (out_dir / member_name).resolve(strict=False)

    try:
        target.relative_to(out_dir_resolved)
    except ValueError:
        raise ArchiveSecurityError(
            f"Archive entry '{member_name}' would extract outside the target folder — blocked."
        )
    return target


def _safe_extract_zip(zf_path: str, out_dir: Path):
    with zipfile.ZipFile(zf_path, 'r') as archive:
        for info in archive.infolist():
            _assert_member_is_safe(info.filename, out_dir)
        archive.extractall(path=str(out_dir))


def _safe_extract_tar(tf_path: str, out_dir: Path):
    with tarfile.open(tf_path, 'r:*') as archive:
        for member in archive.getmembers():
            _assert_member_is_safe(member.name, out_dir)
            # Reject symlinks/hardlinks that point outside out_dir too.
            if member.issym() or member.islnk():
                _assert_member_is_safe(member.linkname, out_dir)
        archive.extractall(path=str(out_dir))


def _safe_extract_7z(zf_path: str, out_dir: Path):
    with py7zr.SevenZipFile(zf_path, mode='r') as archive:
        for name in archive.getnames():
            _assert_member_is_safe(name, out_dir)
        archive.extractall(path=str(out_dir))


def _safe_extract_rar(zf_path: str, out_dir: Path):
    with rarfile.RarFile(zf_path) as archive:
        for name in archive.namelist():
            _assert_member_is_safe(name, out_dir)
        archive.extractall(path=str(out_dir))


def batch_unzip(path: str, dry_run: bool, progress_callback, recursive: bool = False) -> tuple:
    """Extracts common archives (.zip, .rar, .7z, .tar, etc.) into named subfolders.
    recursive=True also finds archives in subfolders (each extracted next to
    where it was found, not dumped at the workspace root)."""
    p = Path(path)
    # Detect a wider range of archive formats
    archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}
    source_iter = p.rglob('*') if recursive else p.iterdir()
    archives = [f for f in source_iter if f.is_file() and f.name != '.organizer_history.json' and f.suffix.lower() in archive_exts]

    if not archives:
        return [], 0, []

    history = []
    errors = []
    for idx, zf in enumerate(archives):
        # Use collision-safe destination, sibling to the archive itself
        out_dir = _safe_dest(zf.parent, zf.stem)
        
        if not dry_run:
            try:
                # Special handling for different formats
                suffix = zf.suffix.lower()
                
                out_dir.mkdir(parents=True, exist_ok=True)

                if suffix == '.7z':
                    if py7zr:
                        _safe_extract_7z(str(zf), out_dir)
                    else:
                        raise ImportError("py7zr library is missing. Cannot extract .7z files.")
                
                elif suffix == '.rar':
                    if rarfile:
                        # Attempt to find unrar/7z if not already configured
                        try:
                            _safe_extract_rar(str(zf), out_dir)
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
                                _safe_extract_rar(str(zf), out_dir)
                            else:
                                raise RuntimeError("RAR extraction requires WinRAR or 7-Zip installed in standard locations, or UnRAR.exe in PATH.")
                    else:
                        raise ImportError("rarfile library is missing. Cannot extract .rar files.")

                elif suffix == '.zip':
                    _safe_extract_zip(str(zf), out_dir)

                elif suffix in {'.tar', '.gz', '.bz2', '.xz'}:
                    _safe_extract_tar(str(zf), out_dir)

                else:
                    # Fallback for any other format shutil recognizes.
                    # Not member-validated — only reached for extensions outside
                    # our known-safe set, which archive_exts above already excludes.
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
                elif isinstance(e, ArchiveSecurityError):
                    err_msg = f"Blocked for safety: {e}"
                errors.append(f"{zf.name}: {err_msg}")
        else:
            history.append({"action": "create", "src": str(zf), "dst": str(out_dir)})
        
        progress_callback(int(((idx + 1) / len(archives)) * 100))

    return history, len(history), errors



# ──────────────────────────────────────────────
# 5. Large File Archiver
# ──────────────────────────────────────────────
def archive_large_files(path: str, threshold_mb: float, dry_run: bool, progress_callback, recursive: bool = False) -> tuple:
    """Moves files exceeding threshold_mb into a 'LargeFiles' subfolder.
    recursive=True also finds candidates in subfolders."""
    p = Path(path)
    threshold_bytes = threshold_mb * 1024 * 1024
    large_dir = p / 'LargeFiles'

    source_iter = p.rglob('*') if recursive else p.iterdir()
    candidates = []
    for f in source_iter:
        if not f.is_file() or f.name == '.organizer_history.json':
            continue
        if large_dir in f.parents:
            continue  # don't re-archive already-archived files
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
        dest = large_dir / f.name
        if not dry_run:
            large_dir.mkdir(exist_ok=True)
            dest = _safe_dest(large_dir, f.name)
            shutil.move(str(f), str(dest))
        history.append({"action": "move", "src": str(f), "dst": str(dest)})
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
        progress_callback(int(((idx + 1) / total) * 100))

    return history, total


# ──────────────────────────────────────────────
# 7. Image Format Converter
# ──────────────────────────────────────────────
def convert_image_formats(path: str, source_exts: list, target_ext: str, dry_run: bool, progress_callback, recursive: bool = False) -> tuple:
    """
    Converts images to target_ext using Pillow.
    source_exts: list of extensions to convert e.g. ['.png', '.bmp']
    target_ext: e.g. '.webp' or '.jpg'
    recursive=True also converts images found in subfolders.
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

    source_iter = p.rglob('*') if recursive else p.iterdir()
    files = [f for f in source_iter if f.is_file() and f.name != '.organizer_history.json' and f.suffix.lower() in source_set]
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
        new_path = _safe_dest(f.parent, new_name) if not dry_run else (f.parent / new_name)

        if not dry_run:
            try:
                img = Image.open(f)
                # Convert RGBA → RGB for JPEG
                if out_format == 'JPEG' and img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(new_path, out_format)
                history.append({"action": "create", "src": str(f), "dst": str(new_path)})
            except Exception as e:
                history.append({"action": "error", "src": str(f), "dst": f"ERROR: {e}"})
        else:
            history.append({"action": "create", "src": str(f), "dst": str(new_path)})

        progress_callback(int(((idx + 1) / total) * 100))

    return history, total
