import os
import hashlib
import send2trash
from pathlib import Path


def _sort_group_keep_first(group: list, keep_by: str = "oldest") -> list:
    """Returns the group re-ordered so the file to KEEP is always index 0,
    using a deterministic, explainable rule instead of whatever arbitrary
    order os.scandir() happened to return.

    keep_by:
      - "oldest":       keep the file with the earliest modified time (default —
                         treats the first-created copy as the "original")
      - "newest":       keep the file with the latest modified time
      - "shortest_path": keep the file living closest to the scan root
                         (fewer path segments = less "buried")
    """
    def _mtime(f):
        try:
            return os.path.getmtime(f)
        except OSError:
            return float('inf')

    def _depth(f):
        return len(Path(f).parts)

    if keep_by == "newest":
        return sorted(group, key=_mtime, reverse=True)
    elif keep_by == "shortest_path":
        return sorted(group, key=lambda f: (_depth(f), _mtime(f)))
    # default: oldest
    return sorted(group, key=_mtime)

def find_duplicates(path: str, progress_callback, keep_by: str = "oldest"):
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
                real_duplicates.append(_sort_group_keep_first(fpaths, keep_by))

    return real_duplicates

def delete_duplicates(groups: list, progress_callback, keep_by: str = "oldest"):
    # Re-apply the same deterministic ordering here too, in case the caller
    # passes groups back in a different order than find_duplicates returned
    # (e.g. after round-tripping through the UI/JSON bridge). This guarantees
    # index 0 — the file that's kept — is always chosen by the stated rule,
    # never by arbitrary filesystem iteration order.
    groups = [_sort_group_keep_first(g, keep_by) for g in groups]

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
