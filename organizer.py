import os
import webview
import json
import datetime
from pathlib import Path
from typing import List, Dict

# Import refactored services
from services import file_service, duplicate_service, organizer_service

VERSION = "4.0.0"

class OrganizerAPI:
    def __init__(self):
        self._window = None
        self._history = [] # Stores (old_path, new_path) tuples
        self._current_workspace = None

    def set_window(self, window):
        self._window = window

    def _update_progress(self, progress: int):
        if self._window:
            self._window.evaluate_js(f"window.dispatchEvent(new CustomEvent('progressUpdate', {{ detail: {progress} }}))")

    def _load_history(self, workspace_path: str):
        """Loads undo history from a hidden file in the workspace."""
        try:
            history_path = Path(workspace_path) / '.organizer_history.json'
            if history_path.exists():
                with open(history_path, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            else:
                self._history = []
        except:
            self._history = []

    def _save_history(self):
        """Saves current undo history to the workspace."""
        if not self._current_workspace:
            return
        try:
            history_path = Path(self._current_workspace) / '.organizer_history.json'
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, indent=2)
        except:
            pass

    def select_folder(self):
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            self._current_workspace = result[0]
            self._load_history(self._current_workspace)
            return result[0]
        return None

    def undo_last_operation(self, path=None):
        """Reverts the changes made in the last rename operation."""
        if not self._history:
            return {"success": False, "error": "No history found to undo."}

        try:
            total = len(self._history)
            for idx, entry in enumerate(reversed(self._history)):
                old_p, new_p = entry
                if Path(new_p).exists():
                    os.rename(new_p, old_p)
                self._update_progress(int(((idx + 1) / total) * 100))
            
            self._history = []
            self._save_history()
            return {"success": True, "message": f"Successfully reverted {total} changes."}
        except Exception as e:
            return {"success": False, "error": f"Undo failed: {str(e)}"}

    def sequential_rename(self, path: str, prefix: str, mode: str = "files", sort_mode: str = "name", dry_run: bool = False, filter_str: str = "", use_regex: bool = False):
        try:
            new_history, count = organizer_service.sequential_rename(
                path, prefix, mode, sort_mode, dry_run, filter_str, use_regex, self._update_progress
            )
            if not dry_run:
                self._history = new_history
                self._save_history()

            msg = f"Simulation: {count} items would be renamed." if dry_run else f"Successfully organized {count} items."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_duplicates(self, path: str):
        try:
            dupes = duplicate_service.find_duplicates(path, self._update_progress)
            if not dupes:
                return {"success": True, "message": "No duplicates found.", "duplicates": []}
            return {"success": True, "message": f"Found {len(dupes)} groups of duplicates.", "duplicates": dupes}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_duplicates(self, path: str, groups: list, dry_run: bool = False):
        try:
            if dry_run:
                total_to_delete = sum(len(group) - 1 for group in groups)
                return {"success": True, "message": f"Simulation: {total_to_delete} duplicate files would be removed."}

            count = duplicate_service.delete_duplicates(groups, self._update_progress)
            return {"success": True, "message": f"Successfully moved {count} duplicates to Recycle Bin."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sort_by_date(self, path: str, grain: str = "month", dry_run: bool = False):
        try:
            new_history, count = organizer_service.sort_by_date(path, grain, dry_run, self._update_progress)
            if not dry_run:
                self._history = new_history
                self._save_history()

            msg = f"Simulation: {count} files would be sorted." if dry_run else f"Successfully sorted {count} files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def zip_folders(self, path: str, dry_run: bool = False):
        try:
            p = Path(path)
            folders = [f for f in p.iterdir() if f.is_dir()]
            if not folders: return {"success": True, "message": "No folders found."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(folders)} folders would be zipped."}

            for idx, folder in enumerate(folders):
                if file_service.is_locked(folder):
                    return {"success": False, "error": f"Cannot access {folder.name}."}
                shutil.make_archive(str(folder), 'zip', str(folder))
                self._update_progress(int(((idx + 1) / len(folders)) * 100))
            return {"success": True, "message": f"Successfully created {len(folders)} archives."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def change_extensions(self, path: str, old_ext: str, new_ext: str, dry_run: bool = False, filter_str: str = ""):
        try:
            p = Path(path)
            if not old_ext.startswith('.'): old_ext = '.' + old_ext
            if not new_ext.startswith('.'): new_ext = '.' + new_ext
            files = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() == old_ext.lower()]
            if filter_str:
                files = [f for f in files if filter_str.lower() in f.name.lower()]

            if not files: return {"success": True, "message": f"No matching {old_ext} files found."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} files would be converted."}

            for idx, file in enumerate(files):
                if file_service.is_locked(file):
                    return {"success": False, "error": f"File '{file.name}' is busy."}
                file.rename(file.with_suffix(new_ext))
                self._update_progress(int(((idx + 1) / len(files)) * 100))
            return {"success": True, "message": f"Successfully converted {len(files)} files."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def flatten_workspace(self, path: str, dry_run: bool = False):
        try:
            new_history, count = organizer_service.flatten_workspace(path, dry_run, self._update_progress)
            if not dry_run:
                self._history = new_history
                self._save_history()
            msg = f"Simulation: {count} files would be flattened." if dry_run else f"Successfully flattened {count} files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_workspace(self, path: str):
        try:
            category_map = {
                'Media': ['.mp4', '.mkv', '.mov', '.avi', '.mp3', '.wav', '.flac', '.jpg', '.jpeg', '.png', '.gif', '.raw'],
                'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx'],
                'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
                'Code': ['.py', '.js', '.jsx', '.html', '.css', '.json', '.cpp', '.h', '.cs', '.go'],
                'Executable': ['.exe', '.msi', '.bat', '.sh']
            }
            stats = file_service.scan_analyze(path, category_map)
            return {"success": True, "stats": stats}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_file_metadata(self, file_path: str):
        try:
            p = Path(file_path)
            if not p.exists(): return {"success": False, "error": "File not found"}
            stat = p.stat()
            return {
                "success": True,
                "metadata": {
                    "name": p.name,
                    "size": file_service.get_size_str(stat.st_size),
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    "extension": p.suffix.lower(),
                    "uri": p.absolute().as_uri()
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def smart_categorize(self, path: str, dry_run: bool = False, custom_rules: list = None):
        try:
            new_history, count = organizer_service.smart_categorize(path, dry_run, custom_rules, self._update_progress)
            if not dry_run:
                self._history = new_history
                self._save_history()
            msg = f"Simulation: {count} files would be categorized." if dry_run else f"Successfully categorized {count} files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_rules(self, path: str):
        try:
            rules_path = Path(path) / '.organizer_rules.json'
            rules = []
            if rules_path.exists():
                with open(rules_path, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
            return {"success": True, "rules": rules, "has_history": len(self._history) > 0}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_rules(self, path: str, rules: list):
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
    url = dist_path.absolute().as_uri() if dist_path.exists() else 'http://localhost:5173'
    
    window = webview.create_window(
        'Folders Organizer Pro', url, js_api=api,
        width=1100, height=850, resizable=True,
        min_size=(1000, 750), background_color='#0f172a'
    )
    api.set_window(window)
    webview.start(debug=False, icon=str(icon_path) if icon_path.exists() else None)

if __name__ == '__main__':
    start_app()
