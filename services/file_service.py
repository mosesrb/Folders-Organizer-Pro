import os
import shutil
import datetime
from pathlib import Path

def get_size_str(size_bytes: int) -> str:
    """Helper to format sizes."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

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
