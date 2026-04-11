import os
VERSION = "4.0.0"

import shutil
import zipfile
import webview
from pathlib import Path
from typing import List, Dict
import hashlib
import re
import datetime
import json

class OrganizerAPI:
    def __init__(self):
        self._window = None
        self._history = [] # Stores (old_path, new_path) tuples

    def set_window(self, window):
        self._window = window

    def _update_progress(self, progress: int):
        if self._window:
            self._window.evaluate_js(f"window.dispatchEvent(new CustomEvent('progressUpdate', {{ detail: {progress} }}))")

    def _get_size_str(self, size_bytes: int) -> str:
        """Helper to format sizes."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def select_folder(self):
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            return result[0]
        return None

    def is_locked(self, path: Path):
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

    def undo_last_operation(self, path=None):
        """Reverts the changes made in the last rename operation."""
        if not self._history:
            return {"success": False, "error": "No history found to undo."}

        try:
            total = len(self._history)
            for idx, (old_p, new_p) in enumerate(reversed(self._history)):
                if Path(new_p).exists():
                    os.rename(new_p, old_p)
                self._update_progress(int(((idx + 1) / total) * 100))
            
            self._history = []
            return {"success": True, "message": f"Successfully reverted {total} changes."}
        except Exception as e:
            return {"success": False, "error": f"Undo failed: {str(e)}"}

    def sequential_rename(self, path: str, prefix: str, mode: str = "files", sort_mode: str = "name", dry_run: bool = False, filter_str: str = "", use_regex: bool = False):
        """
        Renames items with support for simulation, sorting, name filtering, and REGEX.
        """
        try:
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": "Path does not exist"}

            # Get items
            if mode == "files":
                items = [f for f in p.iterdir() if f.is_file()]
            else:
                items = [f for f in p.iterdir() if f.is_dir()]
            
            # Apply Filter or Regex
            if filter_str:
                if use_regex:
                    try:
                        regex = re.compile(filter_str, re.IGNORECASE)
                        items = [f for f in items if regex.search(f.name)]
                    except re.error as e:
                        return {"success": False, "error": f"Invalid Regex: {str(e)}"}
                else:
                    items = [f for f in items if filter_str.lower() in f.name.lower()]

            if not items:
                return {"success": True, "message": "No items matched the criteria."}

            # Smart Sort
            if sort_mode == "date":
                items.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            else:
                items.sort(key=lambda x: x.name.lower())

            padding = max(2, len(str(len(items))))
            
            new_history = []
            total = len(items)

            for idx, item in enumerate(items):
                ext = item.suffix if mode == "files" else ""
                
                # If regex is used and there's a prefix, we treat prefix as the replacement pattern
                # Otherwise use sequential numbering
                if use_regex and prefix:
                     try:
                         new_name = re.sub(filter_str, prefix, item.name, flags=re.IGNORECASE)
                     except Exception as e:
                         return {"success": False, "error": f"Regex Replace failed: {str(e)}"}
                else:
                    new_name = f"{prefix}{str(idx + 1).zfill(padding)}{ext}"
                
                new_path = item.with_name(new_name)

                if not dry_run:
                    if self.is_locked(item):
                        return {"success": False, "error": f"Item '{item.name}' is busy."}
                    
                    # Handle collisions
                    final_path = new_path
                    col_idx = 1
                    while final_path.exists() and final_path != item:
                        name_stem = Path(new_name).stem if mode == "files" else new_name
                        final_path = item.with_name(f"{name_stem}_{col_idx}{ext}")
                        col_idx += 1
                        
                    new_history.append((str(item), str(final_path)))
                    os.rename(item, final_path)
                
                self._update_progress(int(((idx + 1) / total) * 100))

            if not dry_run:
                self._history = new_history

            msg = f"Simulation: {len(items)} items would be renamed." if dry_run else f"Successfully organized {len(items)} items."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_duplicates(self, path: str, dry_run: bool = False):
        """Finds duplicate files based on content hash."""
        try:
            p = Path(path)
            files_by_size = {}
            for root, _, files in os.walk(path):
                for f in files:
                    full_p = Path(root) / f
                    size = full_p.stat().st_size
                    if size > 0:
                        files_by_size.setdefault(size, []).append(full_p)

            duplicates = []
            potential_dupes = {s: paths for s, paths in files_by_size.items() if len(paths) > 1}
            total_potential = sum(len(p) for p in potential_dupes.values())
            processed = 0

            hashes = {}
            for size, paths in potential_dupes.items():
                for f_path in paths:
                    # Quick hash (first 1024 bytes)
                    try:
                        with open(f_path, 'rb') as f:
                            chunk = f.read(1024)
                            h = hashlib.md5(chunk).hexdigest()
                            hashes.setdefault((size, h), []).append(str(f_path))
                    except: continue
                    processed += 1
                    self._update_progress(int((processed / total_potential) * 100))

            # Final check for full duplicates
            real_duplicates = []
            for (size, h), paths in hashes.items():
                if len(paths) > 1:
                    # For larger files, do a full hash check
                    if size > 1024:
                        full_hashes = {}
                        for p_str in paths:
                            try:
                                with open(p_str, 'rb') as f:
                                    full_h = hashlib.md5(f.read()).hexdigest()
                                    full_hashes.setdefault(full_h, []).append(p_str)
                            except: continue
                        for fh, fpaths in full_hashes.items():
                            if len(fpaths) > 1:
                                real_duplicates.append(fpaths)
                    else:
                        real_duplicates.append(paths)

            if not real_duplicates:
                return {"success": True, "message": "No duplicates found.", "duplicates": []}
            
            return {"success": True, "message": f"Found {len(real_duplicates)} groups of duplicates.", "duplicates": real_duplicates}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_duplicates(self, path: str, groups: list, dry_run: bool = False):
        """Deletes all but the first file in each duplicate group."""
        try:
            total_to_delete = sum(len(group) - 1 for group in groups)
            if total_to_delete == 0:
                return {"success": True, "message": "Nothing to delete."}

            if dry_run:
                return {"success": True, "message": f"Simulation: {total_to_delete} duplicate files would be removed."}

            deleted_count = 0
            backup_dir = Path(path) / ".duplicates_backup"
            if not backup_dir.exists(): backup_dir.mkdir()

            for group in groups:
                # Keep the first one, move others to backup
                for f_str in group[1:]:
                    f_path = Path(f_str)
                    if f_path.exists():
                        shutil.move(str(f_path), str(backup_dir / f_path.name))
                        deleted_count += 1
                    self._update_progress(int((deleted_count / total_to_delete) * 100))

            return {"success": True, "message": f"Moved {deleted_count} duplicates to .duplicates_backup"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sort_by_date(self, path: str, grain: str = "month", dry_run: bool = False):
        """Sorts files into Year/Month folders, with full undo support."""
        try:
            p = Path(path)
            files = [f for f in p.iterdir() if f.is_file()]
            if not files:
                return {"success": True, "message": "No files found to sort."}

            if dry_run:
                return {"success": True, "message": f"Simulation: {len(files)} files would be sorted into date folders."}

            total = len(files)
            new_history = []
            for idx, file in enumerate(files):
                mtime = datetime.datetime.fromtimestamp(file.stat().st_mtime)
                year = str(mtime.year)
                month = mtime.strftime("%B")
                day = str(mtime.day)

                target_dir = p / year / month
                if grain == "day":
                    target_dir = target_dir / day

                if not target_dir.exists():
                    target_dir.mkdir(parents=True, exist_ok=True)

                dest = target_dir / file.name
                shutil.move(str(file), str(dest))
                new_history.append((str(file), str(dest)))
                self._update_progress(int(((idx + 1) / total) * 100))

            self._history = new_history
            return {"success": True, "message": f"Successfully sorted {len(files)} files."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def zip_folders(self, path: str, dry_run: bool = False):
        try:
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": "Path does not exist"}

            folders = [f for f in p.iterdir() if f.is_dir()]
            if not folders:
                return {"success": True, "message": "No folders found."}

            if dry_run:
                return {"success": True, "message": f"Simulation: {len(folders)} folders would be zipped."}

            total = len(folders)
            for idx, folder in enumerate(folders):
                if self.is_locked(folder):
                    return {"success": False, "error": f"Cannot access {folder.name}."}
                shutil.make_archive(str(folder), 'zip', str(folder))
                self._update_progress(int(((idx + 1) / total) * 100))
            
            return {"success": True, "message": f"Successfully created {len(folders)} archives."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def change_extensions(self, path: str, old_ext: str, new_ext: str, dry_run: bool = False, filter_str: str = ""):
        try:
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": "Path does not exist"}

            if not old_ext.startswith('.'): old_ext = '.' + old_ext
            if not new_ext.startswith('.'): new_ext = '.' + new_ext

            files = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() == old_ext.lower()]
            if filter_str:
                files = [f for f in files if filter_str.lower() in f.name.lower()]

            if not files:
                return {"success": True, "message": f"No matching {old_ext} files found."}

            if dry_run:
                return {"success": True, "message": f"Simulation: {len(files)} files would be converted."}

            total = len(files)
            for idx, file in enumerate(files):
                if self.is_locked(file):
                    return {"success": False, "error": f"File '{file.name}' is busy."}
                file.rename(file.with_suffix(new_ext))
                self._update_progress(int(((idx + 1) / total) * 100))

            return {"success": True, "message": f"Successfully converted {len(files)} files."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def flatten_workspace(self, path: str, dry_run: bool = False):
        """Moves all files from subfolders to the root and removes empty subfolders, with full undo support."""
        try:
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": "Path does not exist"}

            files_to_move = []
            for root, dirs, files in os.walk(path):
                if root == path: continue
                for file in files:
                    files_to_move.append(Path(root) / file)

            if not files_to_move:
                return {"success": True, "message": "No nested files found to flatten."}

            if dry_run:
                return {"success": True, "message": f"Simulation: {len(files_to_move)} nested files would be moved to root."}

            total = len(files_to_move)
            new_history = []
            for idx, file in enumerate(files_to_move):
                dest = p / file.name
                if dest.exists():
                    dest = p / f"{file.stem}_{idx}{file.suffix}"
                shutil.move(str(file), str(dest))
                new_history.append((str(file), str(dest)))
                self._update_progress(int(((idx + 1) / total) * 100))

            # Cleanup empty dirs
            for root, dirs, files in os.walk(path, topdown=False):
                if root == path: continue
                if not os.listdir(root):
                    os.rmdir(root)

            self._history = new_history
            return {"success": True, "message": f"Successfully flattened {total} files and pruned folders."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_workspace(self, path: str):
        """Analyzes the workspace for storage usage and top files."""
        try:
            p = Path(path)
            stats = {
                "total_size": 0,
                "categories": {},
                "top_files": []
            }
            
            category_map = {
                'Media': ['.mp4', '.mkv', '.mov', '.avi', '.mp3', '.wav', '.flac', '.jpg', '.jpeg', '.png', '.gif', '.raw'],
                'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx'],
                'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
                'Code': ['.py', '.js', '.jsx', '.html', '.css', '.json', '.cpp', '.h', '.cs', '.go'],
                'Executable': ['.exe', '.msi', '.bat', '.sh']
            }

            all_files = []
            for root, _, files in os.walk(path):
                for f in files:
                    fp = Path(root) / f
                    try:
                        size = fp.stat().st_size
                        ext = fp.suffix.lower()
                        stats["total_size"] += size
                        
                        found_cat = "Other"
                        for cat, exts in category_map.items():
                            if ext in exts:
                                found_cat = cat
                                break
                        
                        stats["categories"][found_cat] = stats["categories"].get(found_cat, 0) + size
                        all_files.append({
                            "name": f,
                            "path": str(fp),
                            "size": size,
                            "size_str": self._get_size_str(size),
                            "type": found_cat
                        })
                    except: continue

            # Top 10 largest
            all_files.sort(key=lambda x: x["size"], reverse=True)
            stats["top_files"] = all_files[:10]
            stats["total_size_str"] = self._get_size_str(stats["total_size"])
            
            # Format category sizes
            stats["categories_formatted"] = {k: self._get_size_str(v) for k, v in stats["categories"].items()}

            return {"success": True, "stats": stats}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_file_metadata(self, file_path: str):
        """Returns metadata and preview-friendly data for a file."""
        try:
            p = Path(file_path)
            if not p.exists(): return {"success": False, "error": "File not found"}
            
            stat = p.stat()
            meta = {
                "name": p.name,
                "size": self._get_size_str(stat.st_size),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                "extension": p.suffix.lower()
            }
            
            # For preview, we provide the absolute path as a URI
            meta["uri"] = p.absolute().as_uri()
            
            return {"success": True, "metadata": meta}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def smart_categorize(self, path: str, dry_run: bool = False, custom_rules: list = None):
        """Moves files into smart category folders. Accepts custom rules, merges with defaults, supports undo."""
        try:
            p = Path(path)

            # Default extension map
            category_map = {
                'Media/Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
                'Media/Video': ['.mp4', '.mkv', '.mov', '.avi', '.wmv'],
                'Media/Audio': ['.mp3', '.wav', '.flac', '.m4a'],
                'Documents': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.pptx', '.rtf'],
                'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
                'Code': ['.py', '.js', '.jsx', '.html', '.css', '.json', '.xml'],
            }

            # Default keyword rules
            keywords = {
                'Work': ['invoice', 'receipt', 'contract', 'resume', 'report', 'project', 'official'],
                'Personal': ['id', 'passport', 'medical', 'tax', 'legal', 'photo', 'home']
            }

            # Merge custom rules — they take precedence over defaults
            if custom_rules:
                for rule in custom_rules:
                    folder = rule.get('folder', '').strip()
                    if not folder:
                        continue
                    rule_exts = [
                        e.strip().lower() if e.strip().startswith('.') else f'.{e.strip().lower()}'
                        for e in rule.get('extensions', []) if e.strip()
                    ]
                    rule_keys = [k.strip().lower() for k in rule.get('keywords', []) if k.strip()]
                    if rule_exts:
                        category_map[folder] = rule_exts
                    if rule_keys:
                        keywords[folder] = rule_keys

            files = [f for f in p.iterdir() if f.is_file()]
            if not files:
                return {"success": True, "message": "No files found to categorize."}

            if dry_run:
                return {"success": True, "message": f"Simulation: {len(files)} files would be categorized."}

            new_history = []
            processed = 0
            for file in files:
                target_cat = None
                name_lower = file.name.lower()

                # Keywords first
                for cat, keys in keywords.items():
                    if any(k in name_lower for k in keys):
                        target_cat = cat
                        break

                # Extension fallback
                if not target_cat:
                    ext = file.suffix.lower()
                    for cat, exts in category_map.items():
                        if ext in exts:
                            target_cat = cat
                            break

                if not target_cat:
                    target_cat = "Uncategorized"

                target_dir = p / target_cat
                if not target_dir.exists():
                    target_dir.mkdir(parents=True, exist_ok=True)

                dest = target_dir / file.name
                shutil.move(str(file), str(dest))
                new_history.append((str(file), str(dest)))
                processed += 1
                self._update_progress(int((processed / len(files)) * 100))

            self._history = new_history
            return {"success": True, "message": f"Successfully categorized {processed} files into smart folders."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_rules(self, path: str):
        """Loads custom categorize rules from a hidden JSON file in the workspace."""
        try:
            rules_path = Path(path) / '.organizer_rules.json'
            if rules_path.exists():
                with open(rules_path, 'r', encoding='utf-8') as f:
                    return {"success": True, "rules": json.load(f)}
            return {"success": True, "rules": []}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_rules(self, path: str, rules: list):
        """Saves custom categorize rules to a hidden JSON file in the workspace."""
        try:
            rules_path = Path(path) / '.organizer_rules.json'
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2)
            return {"success": True, "message": f"Saved {len(rules)} rule(s) to workspace."}
        except Exception as e:
            return {"success": False, "error": str(e)}

def start_app():
    api = OrganizerAPI()
    base_dir = Path(__file__).parent
    dist_path = base_dir / 'ui' / 'dist' / 'index.html'
    icon_path = base_dir / 'icon.ico'
    
    if dist_path.exists():
        url = dist_path.absolute().as_uri()
    else:
        url = 'http://localhost:5173'
    
    window = webview.create_window(
        'Folders Organizer Pro',
        url,
        js_api=api,
        width=1100,
        height=850,
        resizable=True,
        min_size=(1000, 750),
        background_color='#0f172a'
    )
    api.set_window(window)
    webview.start(debug=False, icon=str(icon_path) if icon_path.exists() else None)

if __name__ == '__main__':
    start_app()
