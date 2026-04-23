import os
import hashlib
import send2trash
from pathlib import Path

def find_duplicates(path: str, progress_callback):
    """Finds duplicate files based on content hash using multi-stage verification."""
    files_by_size = {}

    def scan_dir(target_path):
        try:
            with os.scandir(target_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        try:
                            size = entry.stat().st_size
                            if size > 0:
                                files_by_size.setdefault(size, []).append(entry.path)
                        except OSError:
                            continue
                    elif entry.is_dir(follow_symlinks=False):
                        scan_dir(entry.path)
        except PermissionError:
            pass

    scan_dir(path)

    potential_dupes = [paths for size, paths in files_by_size.items() if len(paths) > 1]
    if not potential_dupes:
        return []

    # Phase 2: Head Hashing (first 1024 bytes)
    head_hashes = {}
    total_files = sum(len(p) for p in potential_dupes)
    processed = 0

    for group in potential_dupes:
        for f_path in group:
            try:
                with open(f_path, 'rb') as f:
                    chunk = f.read(1024)
                    h = hashlib.md5(chunk).hexdigest()
                    size = os.path.getsize(f_path)
                    head_hashes.setdefault((size, h), []).append(f_path)
            except OSError:
                pass
            processed += 1
            progress_callback(int((processed / total_files) * 50))

    # Phase 3: Full Hashing
    real_duplicates = []
    candidates = [paths for (size, h), paths in head_hashes.items() if len(paths) > 1]
    total_candidates = sum(len(p) for p in candidates)
    processed_candidates = 0

    for group in candidates:
        full_hashes = {}
        for f_path in group:
            try:
                h = hashlib.md5()
                with open(f_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                full_hashes.setdefault(h.hexdigest(), []).append(f_path)
            except OSError:
                pass
            processed_candidates += 1
            if total_candidates > 0:
                progress_callback(50 + int((processed_candidates / total_candidates) * 50))

        for fh, fpaths in full_hashes.items():
            if len(fpaths) > 1:
                real_duplicates.append(fpaths)

    return real_duplicates

def delete_duplicates(groups: list, progress_callback):
    total_to_delete = sum(len(group) - 1 for group in groups)
    if total_to_delete == 0:
        return 0

    deleted_count = 0
    for group in groups:
        for f_str in group[1:]:
            f_path = Path(f_str)
            if f_path.exists():
                try:
                    send2trash.send2trash(str(f_path))
                    deleted_count += 1
                except:
                    continue
            progress_callback(int((deleted_count / total_to_delete) * 100))
    return deleted_count
