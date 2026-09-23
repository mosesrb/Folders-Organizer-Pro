import os
import shutil
import datetime
from pathlib import Path
from typing import Optional, Set

def get_size_str(size_bytes: int) -> str:
    """Helper to format sizes."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

class DestinationAllocator:
    """Allocates collision-free destination paths, checking both filesystem existence
    and destinations already reserved across the current batch operation (FOP-AUD-003)."""

    def __init__(self, target_dir: Path):
        self.target_dir = Path(target_dir)
        self._reserved: set[Path] = set()

    def allocate(self, filename: str) -> Path:
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        candidate = self.target_dir / filename
        counter = 1
        while candidate.exists() or candidate in self._reserved:
            candidate = self.target_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        self._reserved.add(candidate)
        return candidate

    def reserve(self, path: Path) -> None:
        self._reserved.add(Path(path))

    def is_reserved(self, path: Path) -> bool:
        return Path(path) in self._reserved


def allocate_unique_destination(target_path: Path, reserved: Optional[set[Path]] = None) -> Path:
    """Finds a collision-free destination for target_path, appending _1, _2...
    if target_path exists on disk or is present in reserved (FOP-AUD-005)."""
    p = Path(target_path)
    res = reserved if reserved is not None else set()
    if not p.exists() and p not in res:
        res.add(p)
        return p

    stem = p.stem
    suffix = p.suffix
    parent = p.parent
    counter = 1
    candidate = parent / f"{stem}_{counter}{suffix}"
    while candidate.exists() or candidate in res:
        counter += 1
        candidate = parent / f"{stem}_{counter}{suffix}"

    res.add(candidate)
    return candidate


def safe_dest(target_dir: Path, filename: str, reserved: Optional[set[Path]] = None) -> Path:
    """Returns a collision-free destination path, appending _1, _2... as needed.
    Respects existing files and optionally an in-memory reservation set."""
    return allocate_unique_destination(Path(target_dir) / filename, reserved)

def list_top_level_folders(path: str) -> list:
    """Returns the immediate subfolders of `path` with a quick item count
    and total size, for UI pickers that let the user select several
    folders to operate on at once (e.g. batch zipping).
    """
    p = Path(path)
    results = []
    try:
        with os.scandir(p) as it:
            for entry in it:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                item_count = 0
                total_size = 0
                try:
                    for f in Path(entry.path).rglob('*'):
                        if f.is_file():
                            item_count += 1
                            try:
                                total_size += f.stat().st_size
                            except OSError:
                                pass
                except PermissionError:
                    pass
                results.append({
                    "name": entry.name,
                    "item_count": item_count,
                    "size_str": get_size_str(total_size),
                })
    except PermissionError:
        pass
    results.sort(key=lambda x: x["name"].lower())
    return results

def is_locked(path: Path) -> bool:
    """Checks if a file or folder is currently locked by another process."""
    try:
        if path.is_file():
            with open(path, 'a'):
                pass
        else:
            if not os.access(path, os.W_OK):
                return True
        return False
    except (IOError, OSError):
        return True

def scan_analyze(path: str, category_map: dict):
    stats = {
        "total_size": 0,
        "categories": {},
        "top_files": []
    }
    all_files = []

    def _scan(target_path):
        try:
            with os.scandir(target_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        try:
                            if entry.name == '.organizer_history.json': continue
                            f_stat = entry.stat()
                            size = f_stat.st_size
                            ext = Path(entry.name).suffix.lower()
                            stats["total_size"] += size

                            found_cat = "Other"
                            for cat, exts in category_map.items():
                                if ext in exts:
                                    found_cat = cat
                                    break

                            stats["categories"][found_cat] = stats["categories"].get(found_cat, 0) + size
                            all_files.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size": size,
                                "size_str": get_size_str(size),
                                "type": found_cat
                            })
                        except OSError: continue
                    elif entry.is_dir(follow_symlinks=False):
                        _scan(entry.path)
        except PermissionError: pass

    _scan(path)
    all_files.sort(key=lambda x: x["size"], reverse=True)
    stats["top_files"] = all_files[:10]
    stats["total_size_str"] = get_size_str(stats["total_size"])
    stats["categories_formatted"] = {k: get_size_str(v) for k, v in stats["categories"].items()}
    return stats
