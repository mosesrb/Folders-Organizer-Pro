# Copyright (c) 2026 mosesrb (Moses Bharshankar). Licensed under GNU GPL-v3.
"""
automation_service.py
7 advanced automation operations for Folders Organizer Pro, plus batch
folder zipping.
All destructive operations support dry_run=True for safe simulation.
"""
import os
import re
import shutil
import datetime
import zipfile
import tarfile
try:
    import send2trash
except ImportError:
    send2trash = None
try:
    import py7zr
except ImportError:
    py7zr = None
try:
    import rarfile
except ImportError:
    rarfile = None

import uuid
from pathlib import Path
from .file_service import safe_dest as _safe_dest, allocate_unique_destination
from .path_guard import validate_workspace, validate_source, validate_destination, PathSecurityError

# Protected system extensions/names — never touch these during cleanup
_PROTECTED_EXTS = {'.lnk', '.ini', '.sys', '.inf', '.dll', '.icl', '.theme'}
_PROTECTED_NAMES = {'desktop.ini', 'thumbs.db', '.ds_store'}


# ──────────────────────────────────────────────
# 1. Empty Folder Cleanup
# ──────────────────────────────────────────────
def delete_empty_folders(path: str, dry_run: bool, progress_callback) -> tuple:
    """Recursively finds and removes all empty directories, cascading
    bottom-up so a nested chain of empty folders (A/B/C all empty) fully
    collapses in a single pass rather than one level per run."""
    p = Path(path)
    removed = []

    def _prune(d: Path) -> bool:
        """Returns True if `d` is empty (or became empty once its empty
        children were pruned) and — outside dry_run — was removed."""
        is_empty = True
        try:
            entries = list(d.iterdir())
        except PermissionError:
            return False
        for entry in entries:
            if entry.name == '.organizer_history.json':
                continue
            if entry.is_dir():
                if not _prune(entry):
                    is_empty = False
            else:
                is_empty = False
        if is_empty and d != p:
            if not dry_run:
                try:
                    d.rmdir()
                except OSError:
                    return False
            removed.append(str(d))
        return is_empty

    _prune(p)
    progress_callback(100)
    return removed, len(removed)


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

# Archive Quota Limits & Windows Reserved Device Names (FOP-AUD-012)
MAX_ARCHIVE_MEMBERS = 10_000
MAX_EXPANDED_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB limit
MAX_COMPRESSION_RATIO = 100  # 100:1 ratio limit
MAX_DIRECTORY_DEPTH = 20
MIN_FREE_DISK_SPACE_BUFFER = 50 * 1024 * 1024  # 50 MB safety margin

WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}


class ArchiveSecurityError(Exception):
    """Raised when an archive contains a member that would escape the
    intended extraction directory, violate quotas, or use forbidden links."""
    pass


def _assert_member_is_safe(member_name: str, out_dir: Path) -> Path:
    """Resolves a member's target path and verifies it stays inside out_dir.
    Rejects absolute paths, '..' traversal, Windows drive-letter / UNC prefixes,
    null bytes, reserved DOS device names, and excessive nesting depth.
    """
    if not member_name:
        return out_dir

    if member_name.strip() == '..':
        raise ArchiveSecurityError(f"Unsafe archive entry name: {member_name!r}")

    if '\x00' in member_name:
        raise ArchiveSecurityError("Archive entry contains forbidden null byte")

    # Reject absolute paths / drive letters outright before any join.
    raw = member_name.replace('\\', '/')
    if raw.startswith('/') or (len(raw) > 1 and raw[1] == ':'):
        raise ArchiveSecurityError(f"Archive entry has an absolute path: {member_name!r}")

    out_dir_resolved = out_dir.resolve(strict=False)
    target = (out_dir / member_name).resolve(strict=False)

    try:
        rel = target.relative_to(out_dir_resolved)
    except ValueError:
        raise ArchiveSecurityError(
            f"Archive entry '{member_name}' would extract outside the target folder — blocked."
        )

    # Check nesting depth limit (FOP-AUD-012)
    if len(rel.parts) > MAX_DIRECTORY_DEPTH:
        raise ArchiveSecurityError(
            f"Archive entry '{member_name}' nesting depth ({len(rel.parts)}) exceeds limit of {MAX_DIRECTORY_DEPTH}"
        )

    # Reject Windows reserved device names in any path segment
    for part in rel.parts:
        base = part.split('.')[0].upper()
        if base in WINDOWS_RESERVED_NAMES:
            raise ArchiveSecurityError(f"Archive entry contains reserved device name: {part}")

    return target


def _check_disk_space(target_dir: Path, required_bytes: int):
    """Verifies that the target filesystem has sufficient free space."""
    try:
        check_path = target_dir if target_dir.exists() else target_dir.parent
        usage = shutil.disk_usage(str(check_path))
        if usage.free < required_bytes + MIN_FREE_DISK_SPACE_BUFFER:
            raise ArchiveSecurityError(
                f"Insufficient disk space: required {required_bytes} bytes (+50MB safety buffer), available {usage.free} bytes"
            )
    except OSError:
        pass


class ArchiveQuotaTracker:
    """Tracks extraction metrics and enforces expansion quotas to defeat archive/zip bombs."""
    def __init__(self, archive_size: int, max_bytes: int = MAX_EXPANDED_BYTES, max_ratio: int = MAX_COMPRESSION_RATIO):
        self.archive_size = max(1, archive_size)
        self.max_bytes = max_bytes
        self.max_ratio = max_ratio
        self.total_extracted = 0

    def add_bytes(self, num_bytes: int):
        self.total_extracted += num_bytes
        if self.total_extracted > self.max_bytes:
            raise ArchiveSecurityError(
                f"Archive exceeded maximum expansion limit of {self.max_bytes} bytes (decompression bomb protection)"
            )
        # Check compression ratio only once significant bytes (>1MB) have been decompressed
        if self.total_extracted > 1_000_000 and (self.total_extracted / self.archive_size) > self.max_ratio:
            raise ArchiveSecurityError(
                f"Archive compression ratio ({self.total_extracted / self.archive_size:.1f}:1) exceeded safety limit of {self.max_ratio}:1"
            )


def _safe_extract_zip(zf_path: str, out_dir: Path):
    zf_file = Path(zf_path)
    archive_size = zf_file.stat().st_size
    tracker = ArchiveQuotaTracker(archive_size)

    with zipfile.ZipFile(zf_path, 'r') as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveSecurityError(
                f"Archive member count ({len(members)}) exceeds limit of {MAX_ARCHIVE_MEMBERS}"
            )

        declared_total = sum(info.file_size for info in members)
        if declared_total > MAX_EXPANDED_BYTES:
            raise ArchiveSecurityError(
                f"Declared uncompressed size ({declared_total} bytes) exceeds limit of {MAX_EXPANDED_BYTES} bytes"
            )

        if declared_total > 1_000_000 and (declared_total / max(1, archive_size)) > MAX_COMPRESSION_RATIO:
            raise ArchiveSecurityError(
                f"Archive compression ratio ({declared_total / archive_size:.1f}:1) exceeds limit of {MAX_COMPRESSION_RATIO}:1"
            )

        _check_disk_space(out_dir, declared_total)

        for info in members:
            # Reject symlinks in zip (POSIX symlink attribute in upper 16 bits)
            mode = info.external_attr >> 16
            if (mode & 0o170000) == 0o120000:
                raise ArchiveSecurityError(f"Symlinks are not allowed in zip archives: {info.filename}")

            target = _assert_member_is_safe(info.filename, out_dir)

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, 'r') as src, target.open('wb') as dst:
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        tracker.add_bytes(len(chunk))
                        dst.write(chunk)


def _safe_extract_tar(tf_path: str, out_dir: Path):
    tf_file = Path(tf_path)
    archive_size = tf_file.stat().st_size
    tracker = ArchiveQuotaTracker(archive_size)

    with tarfile.open(tf_path, 'r:*') as archive:
        members = archive.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveSecurityError(
                f"Archive member count ({len(members)}) exceeds limit of {MAX_ARCHIVE_MEMBERS}"
            )

        declared_total = sum(m.size for m in members if m.isreg())
        if declared_total > MAX_EXPANDED_BYTES:
            raise ArchiveSecurityError(
                f"Declared uncompressed size ({declared_total} bytes) exceeds limit of {MAX_EXPANDED_BYTES} bytes"
            )

        if declared_total > 1_000_000 and (declared_total / max(1, archive_size)) > MAX_COMPRESSION_RATIO:
            raise ArchiveSecurityError(
                f"Archive compression ratio ({declared_total / archive_size:.1f}:1) exceeds limit of {MAX_COMPRESSION_RATIO}:1"
            )

        _check_disk_space(out_dir, declared_total)

        out_dir_resolved = out_dir.resolve(strict=False)
        for member in members:
            # Reject special device nodes / FIFOs
            if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                raise ArchiveSecurityError(f"Special device nodes are not permitted: {member.name}")

            target = _assert_member_is_safe(member.name, out_dir)

            # Check links
            if member.issym() or member.islnk():
                link_target = (out_dir / member.name).parent / member.linkname
                try:
                    link_target.resolve(strict=False).relative_to(out_dir_resolved)
                except ValueError:
                    raise ArchiveSecurityError(f"Link target escapes destination directory: {member.linkname}")
                raise ArchiveSecurityError(f"Symlinks and hardlinks are not allowed in tar archives: {member.name}")

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isreg():
                target.parent.mkdir(parents=True, exist_ok=True)
                f_in = archive.extractfile(member)
                if f_in is not None:
                    with f_in, target.open('wb') as dst:
                        while True:
                            chunk = f_in.read(65536)
                            if not chunk:
                                break
                            tracker.add_bytes(len(chunk))
                            dst.write(chunk)


def _safe_extract_7z(zf_path: str, out_dir: Path):
    zf_file = Path(zf_path)
    archive_size = zf_file.stat().st_size

    with py7zr.SevenZipFile(zf_path, mode='r') as archive:
        files = archive.files
        if len(files) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveSecurityError(
                f"Archive member count ({len(files)}) exceeds limit of {MAX_ARCHIVE_MEMBERS}"
            )

        declared_total = sum(f.uncompressed or 0 for f in files)
        if declared_total > MAX_EXPANDED_BYTES:
            raise ArchiveSecurityError(
                f"Declared uncompressed size ({declared_total} bytes) exceeds limit of {MAX_EXPANDED_BYTES} bytes"
            )

        if declared_total > 1_000_000 and (declared_total / max(1, archive_size)) > MAX_COMPRESSION_RATIO:
            raise ArchiveSecurityError(
                f"Archive compression ratio ({declared_total / archive_size:.1f}:1) exceeds limit of {MAX_COMPRESSION_RATIO}:1"
            )

        _check_disk_space(out_dir, declared_total)

        for f in files:
            if getattr(f, 'is_symlink', False):
                raise ArchiveSecurityError(f"Symlinks are not allowed in 7z archives: {f.filename}")
            _assert_member_is_safe(f.filename, out_dir)

        archive.extractall(path=str(out_dir))


def _safe_extract_rar(zf_path: str, out_dir: Path):
    zf_file = Path(zf_path)
    archive_size = zf_file.stat().st_size
    tracker = ArchiveQuotaTracker(archive_size)

    with rarfile.RarFile(zf_path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveSecurityError(
                f"Archive member count ({len(members)}) exceeds limit of {MAX_ARCHIVE_MEMBERS}"
            )

        declared_total = sum(info.file_size for info in members)
        if declared_total > MAX_EXPANDED_BYTES:
            raise ArchiveSecurityError(
                f"Declared uncompressed size ({declared_total} bytes) exceeds limit of {MAX_EXPANDED_BYTES} bytes"
            )

        if declared_total > 1_000_000 and (declared_total / max(1, archive_size)) > MAX_COMPRESSION_RATIO:
            raise ArchiveSecurityError(
                f"Archive compression ratio ({declared_total / archive_size:.1f}:1) exceeds limit of {MAX_COMPRESSION_RATIO}:1"
            )

        _check_disk_space(out_dir, declared_total)

        for info in members:
            if info.is_symlink():
                raise ArchiveSecurityError(f"Symlinks are not allowed in RAR archives: {info.filename}")
            target = _assert_member_is_safe(info.filename, out_dir)

            if info.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open('wb') as dst:
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        tracker.add_bytes(len(chunk))
                        dst.write(chunk)


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
    reserved_dests: set[Path] = set()
    for idx, zf in enumerate(archives):
        # Use collision-safe destination, sibling to the archive itself
        out_dir = allocate_unique_destination(zf.parent / zf.stem, reserved=reserved_dests)
        
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
    try:
        src_p = validate_workspace(src)
        dest_p = validate_destination(dest, src_p, allow_sibling=True)
    except PathSecurityError as e:
        raise ValueError(str(e))

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
# 8. Batch Folder Zipper
# ──────────────────────────────────────────────
def batch_zip_folders(path: str, folder_names: list, target_ext: str, delete_originals: bool,
                       dry_run: bool, progress_callback) -> tuple:
    """
    Zips each named top-level subfolder of `path` into its own archive,
    written back into `path` alongside the other folders. `target_ext`
    lets the archive come out with something other than a plain '.zip'
    extension (e.g. '.cbz' for a folder of comic pages, '.bak' for a
    disguised backup) — the archive is always standard zip format
    internally, only the file extension changes, which is what most tools
    that expect a specific extension actually care about. This folds
    "zip a folder" and "give it a different extension" into one operation
    instead of two.

    Each archive contains the source folder as its own root entry (e.g.
    zipping 'Photos' produces 'Photos.zip' containing 'Photos/img1.jpg'),
    so re-extracting it reproduces the original folder structure exactly.

    Skips a folder if an item with the resulting archive name already
    exists, reporting it as an error rather than overwriting silently.
    delete_originals=True sends the source folder to the Recycle Bin after
    a *successful* zip — never in dry_run, and never if the zip step failed
    for that folder. The archive itself is undo-able via the app's normal
    history/undo; the Recycle Bin is what makes the deletion recoverable
    (the app's undo history doesn't reverse folder deletions).
    """
    p = validate_workspace(path)
    if not target_ext.startswith('.'):
        target_ext = '.' + target_ext

    targets = []
    errors = []
    for name in folder_names:
        try:
            folder = validate_source(p / name, p)
            if folder.is_dir():
                targets.append(folder)
            else:
                errors.append(f"{name}: not a directory.")
        except PathSecurityError as e:
            errors.append(f"{name}: blocked for safety: {e}")

    if not targets:
        return [], 0, errors

    total = len(targets)
    history = []

    for idx, folder in enumerate(targets):
        archive_path = folder.parent / f"{folder.name}{target_ext}"

        if archive_path.exists():
            errors.append(f"{folder.name}: an item named '{archive_path.name}' already exists — skipped.")
            progress_callback(int(((idx + 1) / total) * 100))
            continue

        if not dry_run:
            tmp_zip = folder.parent / f".{folder.name}.zipping.tmp"
            try:
                with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file in folder.rglob('*'):
                        if file.is_file() and file.name != '.organizer_history.json':
                            zf.write(file, file.relative_to(folder.parent))
                tmp_zip.replace(archive_path)
                history.append({"action": "create", "src": str(folder), "dst": str(archive_path)})
                if delete_originals:
                    if send2trash is None:
                        raise RuntimeError("Recycle Bin service (send2trash) is not available. Deletion blocked.")
                    send2trash.send2trash(str(folder))
                    history.append({"action": "delete", "src": str(folder), "dst": ""})
            except Exception as e:
                errors.append(f"{folder.name}: {e}")
                if tmp_zip.exists():
                    try:
                        tmp_zip.unlink()
                    except OSError:
                        pass
        else:
            history.append({"action": "create", "src": str(folder), "dst": str(archive_path)})
            if delete_originals:
                history.append({"action": "delete", "src": str(folder), "dst": ""})

        progress_callback(int(((idx + 1) / total) * 100))

    return history, len(history), errors


# ──────────────────────────────────────────────
# 9. Image Format Converter
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

    pil_format_map = {
        '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG',
        '.webp': 'WEBP', '.bmp': 'BMP', '.tiff': 'TIFF', '.gif': 'GIF'
    }
    if target_ext.lower() not in pil_format_map:
        raise ValueError(f"Unsupported target image format: {target_ext}")
    out_format = pil_format_map[target_ext.lower()]

    if isinstance(source_exts, str):
        source_exts = [x.strip() for x in source_exts.split(',') if x.strip()]

    # Normalize source extensions
    source_set = {(e if e.startswith('.') else f'.{e}').lower() for e in source_exts}

    source_iter = p.rglob('*') if recursive else p.iterdir()
    files = [f for f in source_iter if f.is_file() and f.name != '.organizer_history.json' and f.suffix.lower() in source_set]
    if not files:
        return [], 0

    total = len(files)
    history = []

    # FOP-AUD-008: Bounded resource limits and explicit format restrictions
    MAX_IMAGE_PIXELS = 100_000_000
    MAX_IMAGE_DIMENSION = 16384
    ALLOWED_IMAGE_FORMATS = ["JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"]
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    reserved_dests: set[Path] = set()
    for idx, f in enumerate(files):
        new_name = f.stem + target_ext
        new_path = allocate_unique_destination(f.parent / new_name, reserved=reserved_dests)

        if not dry_run:
            tmp_path = f.parent / f".tmp_{uuid.uuid4().hex[:8]}_{new_path.name}"
            try:
                with Image.open(f, formats=ALLOWED_IMAGE_FORMATS) as img:
                    width, height = img.size
                    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                        raise ValueError(
                            f"Image dimensions ({width}x{height}) exceed maximum allowed dimension of {MAX_IMAGE_DIMENSION}px"
                        )
                    if width * height > MAX_IMAGE_PIXELS:
                        raise ValueError(
                            f"Image pixel count ({width * height}) exceeds maximum allowed limit of {MAX_IMAGE_PIXELS} pixels"
                        )

                    # Convert RGBA → RGB for JPEG
                    if out_format == 'JPEG' and img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.save(tmp_path, out_format)

                os.replace(str(tmp_path), str(new_path))
                history.append({"action": "create", "src": str(f), "dst": str(new_path)})
            except Exception as e:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                history.append({"action": "error", "src": str(f), "dst": f"ERROR: {e}"})
        else:
            history.append({"action": "create", "src": str(f), "dst": str(new_path)})

        progress_callback(int(((idx + 1) / total) * 100))

    return history, total
