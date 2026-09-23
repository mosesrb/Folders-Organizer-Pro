# Copyright (c) 2026 mosesrb (Moses Bharshankar). Licensed under GNU GPL-v3.
"""
duplicate_service.py
Duplicate file detection and safe deletion for Folders Organizer Pro.
Hardened for FOP-AUD-015:
- Uses SHA-256 and direct byte comparison (replaces MD5).
- Re-validates canonical workspace scope for all paths.
- Re-stats and re-hashes every candidate against the kept file immediately before deletion.
- Aborts candidate deletion if kept file was removed or candidate content changed.
"""
import os
import uuid
import datetime
import hashlib
from pathlib import Path
from typing import Optional, Union, Tuple, List

try:
    import send2trash
except ImportError:
    send2trash = None

from . import path_guard


def compute_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file using 64KB streaming blocks."""
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def files_are_identical(path_a: Path, path_b: Path) -> bool:
    """Verifies that two files have identical byte contents using 64KB chunk comparison."""
    try:
        if path_a.stat().st_size != path_b.stat().st_size:
            return False
        with path_a.open('rb') as fa, path_b.open('rb') as fb:
            while True:
                ca = fa.read(65536)
                cb = fb.read(65536)
                if ca != cb:
                    return False
                if not ca:
                    return True
    except OSError:
        return False


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


# Server-side scan registry for tracking active duplicate scans (FOP-AUD-015)
_active_scans: dict[str, dict] = {}


def find_duplicates(path: str, progress_callback=None, keep_by: str = "oldest") -> list:
    """Finds duplicate files based on content hash using multi-stage SHA-256 verification."""
    cb = progress_callback if progress_callback is not None else (lambda _: None)
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

    # Phase 2: Head Hashing (first 4096 bytes using SHA-256)
    head_hashes = {}
    total_files = sum(len(p) for p in potential_dupes)
    processed = 0

    for group in potential_dupes:
        for f_path in group:
            try:
                with open(f_path, 'rb') as f:
                    chunk = f.read(4096)
                    h = hashlib.sha256(chunk).hexdigest()
                    size = os.path.getsize(f_path)
                    head_hashes.setdefault((size, h), []).append(f_path)
            except OSError:
                pass
            processed += 1
            cb(int((processed / total_files) * 50))

    # Phase 3: Full Hashing (SHA-256 with streaming 64KB blocks)
    real_duplicates = []
    candidates = [paths for (size, h), paths in head_hashes.items() if len(paths) > 1]
    total_candidates = sum(len(p) for p in candidates)
    processed_candidates = 0

    scan_groups_meta = []
    for group in candidates:
        full_hashes = {}
        for f_path in group:
            try:
                h_str = compute_sha256(Path(f_path))
                full_hashes.setdefault(h_str, []).append(f_path)
            except OSError:
                pass
            processed_candidates += 1
            if total_candidates > 0:
                cb(50 + int((processed_candidates / total_candidates) * 50))

        for fh, fpaths in full_hashes.items():
            if len(fpaths) > 1:
                sorted_paths = _sort_group_keep_first(fpaths, keep_by)
                # Phase 4: Direct byte verification against the kept copy
                verified_group = [sorted_paths[0]]
                for cand in sorted_paths[1:]:
                    if files_are_identical(Path(sorted_paths[0]), Path(cand)):
                        verified_group.append(cand)

                if len(verified_group) > 1:
                    real_duplicates.append(verified_group)
                    scan_groups_meta.append({
                        "group_id": f"grp_{uuid.uuid4().hex[:12]}",
                        "kept_file": verified_group[0],
                        "files": verified_group,
                        "sha256": fh,
                        "size": os.path.getsize(verified_group[0]),
                    })

    # Cache active scan state in backend
    scan_id = uuid.uuid4().hex
    _active_scans[scan_id] = {
        "workspace": str(Path(path).resolve()),
        "groups": scan_groups_meta,
        "timestamp": datetime.datetime.now().isoformat()
    }

    return real_duplicates


def delete_duplicates(
    groups: list,
    progress_callback=None,
    keep_by: str = "oldest",
    workspace: Optional[str] = None,
    return_details: bool = False
) -> Union[int, Tuple[int, List[str]]]:
    """Safely deletes duplicate files, keeping the deterministic primary file (index 0).
    
    Hardened for FOP-AUD-015:
    1. Validates all paths reside strictly within the validated workspace.
    2. Re-checks existence of the kept file; if missing, entire group is skipped.
    3. Immediately re-stats and re-hashes candidate files against the kept file.
    4. Performs byte-for-byte verification before moving candidate to Recycle Bin.
    """
    cb = progress_callback if progress_callback is not None else (lambda _: None)

    w_canon = None
    if workspace:
        w_canon = path_guard.validate_workspace(workspace)
    elif groups and len(groups) > 0 and len(groups[0]) > 0:
        w_canon = Path(groups[0][0]).resolve().parent

    # Re-apply deterministic ordering only if all files exist; if any file is missing,
    # preserve original order so the missing kept file at index 0 is detected and data loss is prevented.
    ordered_groups = []
    for g in groups:
        if all(Path(f).exists() for f in g):
            ordered_groups.append(_sort_group_keep_first(g, keep_by))
        else:
            ordered_groups.append(list(g))
    groups = ordered_groups

    total_to_delete = sum(len(group) - 1 for group in groups if len(group) > 1)
    if total_to_delete == 0:
        return (0, []) if return_details else 0

    if send2trash is None:
        err = "Recycle Bin service (send2trash) is not available. Deletion blocked."
        return (0, [err]) if return_details else 0

    deleted_count = 0
    errors: list[str] = []

    for group in groups:
        if len(group) <= 1:
            continue

        # 1. Canonical workspace scope validation (FOP-AUD-015)
        if w_canon is not None:
            scope_violation = False
            for f_str in group:
                try:
                    path_guard.validate_source(f_str, w_canon)
                except path_guard.PathSecurityError as e:
                    errors.append(f"Security error: path '{f_str}' is outside workspace or system-critical: {e}")
                    scope_violation = True
                    break
            if scope_violation:
                continue

        # 2. Re-verify the kept file
        kept_path = Path(group[0])
        if not kept_path.is_file():
            errors.append(f"Kept file '{kept_path.name}' no longer exists. Skipping group to prevent data loss.")
            continue

        try:
            kept_size = kept_path.stat().st_size
            kept_hash = compute_sha256(kept_path)
        except OSError as e:
            errors.append(f"Could not access kept file '{kept_path.name}': {e}. Skipping group.")
            continue

        # 3. Immediately re-validate candidate files before trashing
        for f_str in group[1:]:
            cand_path = Path(f_str)
            if not cand_path.is_file():
                continue
            if cand_path.resolve() == kept_path.resolve():
                continue

            try:
                cand_size = cand_path.stat().st_size
            except OSError as e:
                errors.append(f"Could not stat '{cand_path.name}': {e}. Skipping.")
                continue

            # Size check
            if cand_size != kept_size:
                errors.append(f"File '{cand_path.name}' modified after scan (size mismatch: {cand_size} vs {kept_size}). Skipping.")
                continue

            # Strong SHA-256 hash check
            try:
                cand_hash = compute_sha256(cand_path)
            except OSError as e:
                errors.append(f"Could not hash '{cand_path.name}': {e}. Skipping.")
                continue

            if cand_hash != kept_hash:
                errors.append(f"File '{cand_path.name}' content changed after scan (hash mismatch). Skipping.")
                continue

            # Direct byte-level identity verification
            if not files_are_identical(kept_path, cand_path):
                errors.append(f"File '{cand_path.name}' byte comparison failed against kept file. Skipping.")
                continue

            # Pre-flight passed: file is 100% confirmed identical to kept file right now
            try:
                send2trash.send2trash(str(cand_path))
                deleted_count += 1
            except Exception as e:
                errors.append(f"Failed to move '{cand_path.name}' to Recycle Bin: {e}")

            if total_to_delete > 0:
                cb(int((deleted_count / total_to_delete) * 100))

    if return_details:
        return deleted_count, errors
    return deleted_count
