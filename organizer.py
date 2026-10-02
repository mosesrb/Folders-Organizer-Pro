import sys
import os
import shutil
import webview
import json
import datetime
import time
import uuid
import threading
from functools import wraps
from pathlib import Path, PureWindowsPath
from typing import List, Dict

def get_base_dir() -> Path:
    """Returns the base directory of the application.
    Supports PyInstaller bundle directory (sys._MEIPASS) as well as regular source execution.
    """
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', sys.executable)).resolve()
    return Path(__file__).resolve().parent

# Import refactored services
from services import (
    file_service,
    duplicate_service,
    organizer_service,
    automation_service,
    media_service,
    path_guard,
    operation_registry,
    journal_service,
)

def is_system_critical_dir(path: str) -> bool:
    """Returns True if path matches a known system-critical directory or drive root."""
    return path_guard.is_system_critical(path)

import subprocess
VERSION = "5.1.0"

def requires_lock(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            self._last_history_error = None
            result = func(self, *args, **kwargs)
            # If the wrapped call touched undo-history persistence and it
            # failed, surface it instead of letting the operation report a
            # clean "Successfully..." message while Undo silently won't work.
            if isinstance(result, dict) and result.get("success") and self._last_history_error:
                result["message"] = f"{result.get('message', '')} ⚠ {self._last_history_error}".strip()
                result["history_warning"] = self._last_history_error
            return result
    return wrapper

class OrganizerAPI:
    def __init__(self):
        self._window = None
        self._history = [] # Stores (old_path, new_path) tuples
        self._current_workspace = None
        self._lock = threading.Lock()
        self._last_history_error = None

    def set_window(self, window):
        self._window = window

    def _update_progress(self, progress: int):
        if self._window:
            self._window.evaluate_js(f"window.dispatchEvent(new CustomEvent('progressUpdate', {{ detail: {progress} }}))")
            self._window.evaluate_js("""document.querySelectorAll('[class*="log"], [class*="console"], [class*="output"], [id*="log"]').forEach(function(el){ el.scrollTop = el.scrollHeight; });""")


    def _load_history(self, workspace_path: str):
        """Loads undo history from a workspace journal using strict schema validation.
        Quarantines invalid or out-of-scope history files (FOP-AUD-001)."""
        self._last_history_error = None
        if not workspace_path:
            self._history = []
            return
        try:
            batch, error = journal_service.load_and_validate_journal(workspace_path)
            if error:
                self._history = []
                self._last_history_error = error
            elif batch:
                self._history = [e.to_dict() for e in batch.entries]
            else:
                self._history = []
        except Exception as e:
            self._history = []
            self._last_history_error = f"Could not read undo history for this workspace: {e}"

    def _save_history(self):
        """Saves current undo history to the workspace using schema v2.0 journal persistence."""
        self._last_history_error = None
        if not self._current_workspace:
            return True
        try:
            if self._history:
                parsed_entries = []
                valid_actions = {a.value for a in journal_service.JournalAction}
                for e in self._history:
                    if isinstance(e, dict):
                        if str(e.get("action", "")).lower() not in valid_actions:
                            continue
                        parsed_entries.append(journal_service.JournalEntry.from_dict(e))
                    elif isinstance(e, (list, tuple)):
                        parsed_entries.append(
                            journal_service.JournalEntry(
                                action="move",
                                src=str(e[0]),
                                dst=str(e[1]),
                            )
                        )
                batch = journal_service.JournalBatch(
                    version=journal_service.JOURNAL_SCHEMA_VERSION,
                    operation_id=f"op_{int(time.time())}_{uuid.uuid4().hex[:6]}",
                    operation_name="operation",
                    workspace=str(path_guard.canonicalize_path(self._current_workspace)),
                    created_at=time.time(),
                    entries=parsed_entries,
                    status="completed",
                )
                journal_service.save_journal(batch, self._current_workspace)
            else:
                journal_service.save_journal(None, self._current_workspace)
            return True
        except Exception as e:
            self._last_history_error = f"Operation succeeded, but undo history could not be saved: {e}"
            return False

    def get_operation_registry(self):
        """Returns the centralized capabilities manifest for all operations."""
        return {"success": True, "registry": operation_registry.get_frontend_manifest()}

    def check_history(self, path: str = None) -> dict:
        """Returns whether a valid undo journal exists on disk for the workspace."""
        ws = path or self._current_workspace
        if not ws:
            return {"success": True, "has_history": False}
        try:
            w_canon = path_guard.validate_workspace(ws)
            batch, _ = journal_service.load_journal(w_canon)
            return {"success": True, "has_history": bool(batch and batch.entries)}
        except Exception:
            return {"success": True, "has_history": False}

    def select_folder(self, purpose="workspace"):
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            path = result[0]
            history_warning = None
            if purpose == "workspace":
                self._current_workspace = path
                self._load_history(self._current_workspace)
                history_warning = self._last_history_error

            system_warning = is_system_critical_dir(path)
            return {
                "path": path,
                "system_warning": system_warning,
                "history_warning": history_warning,
                "has_history": bool(self._history),
            }
        return None

    def select_file(self, file_types: str = "All files (*.*)"):
        """Opens a file dialog to select a single file."""
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
        if result:
            return result[0]
        return None

    def open_in_explorer(self, file_path: str):
        """Opens the file location in Windows Explorer and selects the file."""
        if os.path.exists(file_path):
            try:
                # /select,path opens the folder and highlights the file
                subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
                return True
            except:
                # Fallback to just opening the directory
                try:
                    os.startfile(os.path.dirname(file_path))
                    return True
                except:
                    return False
        return False

    @requires_lock
    def undo_last_operation(self, *args, **kwargs):
        """Reverts the changes made in the last operation using journal_service.
        All deletions are safely routed to the Recycle Bin (send2trash).
        Preserves failed entries on partial recovery (FOP-AUD-001, FOP-AUD-014)."""
        if not self._current_workspace:
            return {"success": False, "error": "No workspace selected."}

        res = journal_service.revert_journal(self._current_workspace, self._update_progress)
        self._load_history(self._current_workspace)
        return res

    @requires_lock
    def sequential_rename(self, path: str, prefix: str, mode: str = "files", sort_mode: str = "name", dry_run: bool = False, filter_str: str = "", use_regex: bool = False):
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            new_history, count = organizer_service.sequential_rename(
                str(w_canon), prefix, mode, sort_mode, dry_run, filter_str, use_regex, self._update_progress
            )
            if not dry_run:
                self._history = new_history
                self._save_history()

            msg = f"Simulation: {count} items would be renamed." if dry_run else f"Successfully organized {count} items."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = new_history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_duplicates(self, path: str, options=None, keep_by: str = "oldest"):
        """keep_by controls which file in each duplicate group is treated as
        the one to keep (index 0): 'oldest' (default), 'newest', or
        'shortest_path'. Previously this was an undocumented, arbitrary
        filesystem-iteration-order choice — now it's explicit and deterministic.
        """
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            dupes = duplicate_service.find_duplicates(str(w_canon), self._update_progress, keep_by)
            if not dupes:
                return {"success": True, "message": "No duplicates found.", "duplicates": []}
            return {"success": True, "message": f"Found {len(dupes)} groups of duplicates.", "duplicates": dupes, "keep_by": keep_by}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def delete_duplicates(self, path: str, groups: list, dry_run: bool = False, keep_by: str = "oldest"):
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            if dry_run:
                total_to_delete = sum(len(group) - 1 for group in groups if len(group) > 1)
                return {"success": True, "message": f"Simulation: {total_to_delete} duplicate files would be removed."}

            count, errors = duplicate_service.delete_duplicates(
                groups,
                self._update_progress,
                keep_by=keep_by,
                workspace=str(w_canon),
                return_details=True
            )
            if errors:
                return {
                    "success": True,
                    "message": f"Moved {count} duplicates to Recycle Bin with {len(errors)} warning(s).",
                    "count": count,
                    "warnings": errors
                }
            return {"success": True, "message": f"Successfully moved {count} duplicates to Recycle Bin.", "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def sort_by_date(self, path: str, grain: str = "month", dry_run: bool = False):
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            new_history, count = organizer_service.sort_by_date(str(w_canon), grain, dry_run, self._update_progress)
            if not dry_run:
                self._history = new_history
                self._save_history()

            msg = f"Simulation: {count} files would be sorted." if dry_run else f"Successfully sorted {count} files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = new_history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    # zip_folders (unconditionally zipped every folder in the workspace, no
    # selection, no collision guard, no undo history) was removed in favor
    # of batch_zip_folders below, which fixes all of those gaps. It was
    # dead code — nothing in the UI ever called it.

    @requires_lock
    def change_extensions(self, path: str, old_ext: str, new_ext: str, dry_run: bool = False, filter_str: str = "", recursive: bool = False):
        tx = None
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            p = w_canon
            if not old_ext.startswith('.'): old_ext = '.' + old_ext
            if not new_ext.startswith('.'): new_ext = '.' + new_ext
            source_iter = p.rglob('*') if recursive else p.iterdir()
            files = [
                f for f in source_iter
                if f.is_file() and f.suffix.lower() == old_ext.lower()
                and f.name != '.organizer_history.json'
                and not f.name.startswith('.organizer_history.quarantined_')
            ]
            if filter_str:
                files = [f for f in files if filter_str.lower() in f.name.lower()]

            if not files: return {"success": True, "message": f"No matching {old_ext} files found."}
            if dry_run:
                items = [{"action": "move", "src": str(f), "dst": str(f.with_suffix(new_ext))} for f in files]
                return {"success": True, "message": f"Simulation: {len(files)} files would be converted.", "items": items}

            tx = journal_service.TransactionJournal(w_canon, "change_extensions")
            skipped = []
            for idx, file in enumerate(files):
                if file_service.is_locked(file):
                    skipped.append(file.name)
                    self._update_progress(int(((idx + 1) / len(files)) * 100))
                    continue
                new_path = file.with_suffix(new_ext)
                file.rename(new_path)
                tx.record_step(journal_service.JournalAction.MOVE, file, new_path)
                self._update_progress(int(((idx + 1) / len(files)) * 100))

            tx.commit()
            self._load_history(str(w_canon))
            msg = f"Successfully converted {len(tx.batch.entries)} files."
            if skipped:
                msg += f" Skipped {len(skipped)} file(s) that were in use."
            return {"success": True, "message": msg}
        except Exception as e:
            if tx and tx.batch.entries:
                tx.abort_with_partial()
                self._load_history(str(w_canon))
            return {"success": False, "error": str(e)}

    @requires_lock
    def flatten_workspace(self, path: str, dry_run: bool = False):
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            new_history, count = organizer_service.flatten_workspace(str(w_canon), dry_run, self._update_progress)
            if not dry_run:
                self._history = new_history
                self._save_history()
            msg = f"Simulation: {count} files would be flattened." if dry_run else f"Successfully flattened {count} files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = new_history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_workspace(self, path: str):
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            category_map = {
                'Media': ['.mp4', '.mkv', '.mov', '.avi', '.mp3', '.wav', '.flac', '.jpg', '.jpeg', '.png', '.gif', '.raw'],
                'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx'],
                'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
                'Code': ['.py', '.js', '.jsx', '.html', '.css', '.json', '.cpp', '.h', '.cs', '.go'],
                'Executable': ['.exe', '.msi', '.bat', '.sh']
            }
            stats = file_service.scan_analyze(str(w_canon), category_map)
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

    @requires_lock
    def smart_categorize(self, path: str, dry_run: bool = False, custom_rules: list = None):
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            new_history, count = organizer_service.smart_categorize(str(w_canon), dry_run, custom_rules, self._update_progress)
            if not dry_run:
                self._history = new_history
                self._save_history()
            msg = f"Simulation: {count} files would be categorized." if dry_run else f"Successfully categorized {count} files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = new_history
            return resp
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

    @requires_lock
    def save_rules(self, path: str, rules: list):
        try:
            rules_path = Path(path) / '.organizer_rules.json'
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2)
            return {"success": True, "message": f"Saved {len(rules)} rule(s) to workspace."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # Advanced Automation Methods
    # ─────────────────────────────────────────────

    @requires_lock
    def delete_empty_folders(self, path: str, dry_run: bool = False):
        """Removes all empty subdirectories recursively."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            removed, count = automation_service.delete_empty_folders(path, dry_run, self._update_progress)
            msg = f"Simulation: {count} empty folders would be removed." if dry_run else f"Removed {count} empty folders."
            return {"success": True, "message": msg, "items": removed}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def advanced_regex_rename(self, path: str, pattern: str, replacement: str, dry_run: bool = False, recursive: bool = False):
        """Batch rename files using regex find/replace."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.advanced_regex_rename(path, pattern, replacement, dry_run, self._update_progress, recursive)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files would be renamed." if dry_run else f"Renamed {count} files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def cleanup_old_files(self, path: str, days: int = 90, dry_run: bool = False, recursive: bool = False):
        """Archives files older than `days` to a .archived_files subfolder."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            history, count = automation_service.cleanup_old_files(str(w_canon), days, dry_run, self._update_progress, recursive)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files older than {days} days would be archived." if dry_run else f"Archived {count} old files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def batch_unzip(self, path: str, dry_run: bool = False, recursive: bool = False):
        """Extracts common archives (.zip, .rar, .7z, etc.) into named subfolders."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            history, count, errors = automation_service.batch_unzip(str(w_canon), dry_run, self._update_progress, recursive)
            if not dry_run:
                self._history = history
                self._save_history()
            
            msg = f"Extracted {count} archives."
            if dry_run:
                msg = f"Simulation: {count} archives would be extracted."
            
            if errors:
                msg += f" ({len(errors)} failures. See logs for details.)"
                
            return {
                "success": True, 
                "message": msg, 
                "items": history,
                "errors": errors
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def archive_large_files(self, path: str, threshold_mb: float = 500.0, dry_run: bool = False, recursive: bool = False):
        """Moves files over threshold_mb MB into a LargeFiles subfolder."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            history, count = automation_service.archive_large_files(str(w_canon), threshold_mb, dry_run, self._update_progress, recursive)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files over {threshold_mb}MB would be moved." if dry_run else f"Moved {count} large files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def additive_backup(self, src: str, dest: str, dry_run: bool = False):
        """Copies new/updated files from src to dest. Never deletes."""
        try:
            src_canon = path_guard.validate_workspace(src)
            dest_canon = path_guard.validate_destination(dest, src_canon, allow_sibling=True)
            self._current_workspace = str(src_canon)
            history, count = automation_service.additive_backup(str(src_canon), str(dest_canon), dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files would be backed up." if dry_run else f"Backed up {count} files."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_subfolders(self, path: str):
        """Lists the immediate subfolders of `path` with item counts/sizes,
        for pickers that let the user select several folders to operate on
        at once (e.g. the Batch Folder Zipper)."""
        try:
            w_canon = path_guard.validate_workspace(path)
            folders = file_service.list_top_level_folders(str(w_canon))
            return {"success": True, "folders": folders}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def batch_zip_folders(self, path: str, folder_names: list, target_ext: str = '.zip',
                           delete_originals: bool = False, dry_run: bool = False):
        """Zips each of the named top-level subfolders into its own archive
        (optionally with a custom extension), optionally removing the
        source folder once it's safely zipped."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            if not folder_names:
                return {"success": False, "error": "No folders selected."}
            history, count, errors = automation_service.batch_zip_folders(
                str(w_canon), folder_names, target_ext, delete_originals, dry_run, self._update_progress
            )
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {len(folder_names)} folder(s) would be zipped." if dry_run else f"Zipped {count} item(s) from {len(folder_names)} folder(s)."
            if errors:
                msg += f" ({len(errors)} failures. See logs for details.)"
            resp = {"success": True, "message": msg, "errors": errors}
            if dry_run: resp["items"] = history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def convert_image_formats(self, path: str, source_exts: list, target_ext: str, dry_run: bool = False, recursive: bool = False):
        """Batch converts images to target format using Pillow."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            if isinstance(source_exts, str):
                source_exts = [x.strip() for x in source_exts.split(",") if x.strip()]
            history, count = automation_service.convert_image_formats(str(w_canon), source_exts, target_ext, dry_run, self._update_progress, recursive)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} images would be converted." if dry_run else f"Converted {count} images."
            resp = {"success": True, "message": msg}
            if dry_run: resp["items"] = history
            return resp
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # v5.0 Media Processing Methods
    # ─────────────────────────────────────────────

    def get_audio_files(self, path: str):
        """Returns a list of all audio files (.mp3) in the active workspace."""
        try:
            w_canon = path_guard.validate_workspace(path)
            files = []
            for f in w_canon.rglob('*.mp3'):
                if f.is_file():
                    stat = f.stat()
                    files.append({
                        "name": f.name,
                        "size": file_service.get_size_str(stat.st_size),
                        "path": str(f)
                    })
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_pdf_files(self, path: str):
        """Returns a list of all PDF files in the active workspace."""
        try:
            w_canon = path_guard.validate_workspace(path)
            files = []
            for f in w_canon.rglob('*.pdf'):
                if f.is_file():
                    stat = f.stat()
                    files.append({
                        "name": f.name,
                        "size": file_service.get_size_str(stat.st_size),
                        "path": str(f)
                    })
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_image_files(self, path: str):
        """Returns a list of all image files in the active workspace."""
        try:
            w_canon = path_guard.validate_workspace(path)
            files = []
            exts = ['.jpg', '.jpeg', '.png', '.webp']
            for f in w_canon.rglob('*'):
                if f.is_file() and f.suffix.lower() in exts:
                    stat = f.stat()
                    files.append({
                        "name": f.name,
                        "size": file_service.get_size_str(stat.st_size),
                        "path": str(f)
                    })
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def convert_mp3_to_wav(self, file_path: str, remove_original: bool = False):
        """Converts a specific MP3 file to WAV."""
        try:
            p_src = Path(file_path).resolve()
            if path_guard.is_system_critical(p_src):
                return {"success": False, "error": f"Operation blocked: '{file_path}' is a system-critical file."}
            dst, err = media_service.convert_mp3_to_wav(str(p_src), self._update_progress)
            if not dst:
                return {"success": False, "error": err or "Conversion failed."}

            if remove_original:
                recycle_ok = False
                recycle_err = None
                try:
                    import send2trash
                    send2trash.send2trash(str(p_src))
                    recycle_ok = True
                except Exception as te:
                    recycle_err = str(te)

                if recycle_ok:
                    return {"success": True, "message": f"Converted to: {os.path.basename(dst)} (Original moved to Recycle Bin)", "dst": dst}
                else:
                    return {"success": True, "message": f"Converted to: {os.path.basename(dst)}, but failed to move original to Recycle Bin: {recycle_err}", "dst": dst, "warning": f"Recycle Bin error: {recycle_err}"}

            self._history = [{"action": "create", "src": str(p_src), "dst": dst}]
            self._save_history()
            return {"success": True, "message": f"Converted to: {os.path.basename(dst)}", "dst": dst}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def batch_convert_mp3_to_wav(self, path: str, remove_original: bool = False, dry_run: bool = False):
        """Converts all MP3 files in a folder to WAV."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            files = [f for f in w_canon.rglob('*.mp3') if f.is_file()]
            if not files: return {"success": True, "message": "No MP3 files found to convert."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} MP3 files would be converted."}

            results = []
            new_history = []
            failures = []
            recycled_count = 0
            recycle_failures = []

            for idx, file in enumerate(files):
                dst, err = media_service.convert_mp3_to_wav(str(file), self._update_progress)
                if dst:
                    results.append(dst)
                    if remove_original:
                        try:
                            import send2trash
                            send2trash.send2trash(str(file))
                            recycled_count += 1
                        except Exception as te:
                            recycle_failures.append(f"Failed to recycle {file.name}: {te}")
                    else:
                        new_history.append({"action": "create", "src": str(file), "dst": dst})
                else:
                    failures.append(err or file.name)
                self._update_progress(int(((idx + 1) / len(files)) * 100))

            if not remove_original:
                self._history = new_history
                self._save_history()
            msg = f"Successfully converted {len(results)} MP3 files to WAV."
            if remove_original:
                if len(results) > 0 and len(recycle_failures) == 0:
                    msg += " (Originals moved to Recycle Bin)."
                elif recycled_count > 0:
                    msg += f" ({recycled_count} moved to Recycle Bin; {len(recycle_failures)} could not be recycled)."
                else:
                    msg += f" (Warning: {len(recycle_failures)} original(s) could not be moved to Recycle Bin)."
            if failures:
                msg += f" {len(failures)} conversion(s) failed."
            all_errors = failures + recycle_failures
            return {"success": True, "message": msg, "errors": all_errors}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def compress_pdf(self, file_path: str, remove_original: bool = False):
        """Compresses a specific PDF file."""
        try:
            p_src = Path(file_path).resolve()
            if path_guard.is_system_critical(p_src):
                return {"success": False, "error": f"Operation blocked: '{file_path}' is a system-critical file."}
            dst, err = media_service.compress_pdf(str(p_src), self._update_progress)
            if dst:
                if remove_original:
                    recycle_ok = False
                    recycle_err = None
                    try:
                        import send2trash
                        send2trash.send2trash(str(p_src))
                        recycle_ok = True
                    except Exception as te:
                        recycle_err = str(te)

                    if recycle_ok:
                        return {"success": True, "message": f"Compressed PDF created: {os.path.basename(dst)} (Original moved to Recycle Bin)", "dst": dst}
                    else:
                        return {"success": True, "message": f"Compressed PDF created: {os.path.basename(dst)}, but failed to move original to Recycle Bin: {recycle_err}", "dst": dst, "warning": f"Recycle Bin error: {recycle_err}"}

                self._history = [{"action": "create", "src": str(p_src), "dst": dst}]
                self._save_history()
                return {"success": True, "message": f"Compressed PDF created: {os.path.basename(dst)}", "dst": dst}
            return {"success": False, "error": err or "Compression failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def batch_compress_pdf(self, path: str, remove_original: bool = False, dry_run: bool = False):
        """Compresses all PDF files in a folder recursively."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            files = [f for f in w_canon.rglob('*.pdf') if f.is_file()]
            if not files: return {"success": True, "message": "No PDF files found to compress."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} PDF files would be compressed."}

            results = []
            new_history = []
            failures = []
            recycled_count = 0
            recycle_failures = []

            for idx, file in enumerate(files):
                dst, err = media_service.compress_pdf(str(file), self._update_progress)
                if dst:
                    results.append(dst)
                    if remove_original:
                        try:
                            import send2trash
                            send2trash.send2trash(str(file))
                            recycled_count += 1
                        except Exception as te:
                            recycle_failures.append(f"Failed to recycle {file.name}: {te}")
                    else:
                        new_history.append({"action": "create", "src": str(file), "dst": dst})
                else:
                    failures.append(err or file.name)
                self._update_progress(int(((idx + 1) / len(files)) * 100))

            if not remove_original:
                self._history = new_history
                self._save_history()
            msg = f"Successfully compressed {len(results)} PDF files."
            if remove_original:
                if len(results) > 0 and len(recycle_failures) == 0:
                    msg += " (Originals moved to Recycle Bin)."
                elif recycled_count > 0:
                    msg += f" ({recycled_count} moved to Recycle Bin; {len(recycle_failures)} could not be recycled)."
                else:
                    msg += f" (Warning: {len(recycle_failures)} original(s) could not be moved to Recycle Bin)."
            if failures:
                msg += f" {len(failures)} compression(s) failed."
            all_errors = failures + recycle_failures
            return {"success": True, "message": msg, "errors": all_errors}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def optimize_image(self, file_path: str, quality: int = 85, remove_original: bool = False):
        """Optimizes a single image."""
        try:
            p_src = Path(file_path).resolve()
            if path_guard.is_system_critical(p_src):
                return {"success": False, "error": f"Operation blocked: '{file_path}' is a system-critical file."}
            dst, err = media_service.optimize_image(str(p_src), quality, self._update_progress)
            if dst:
                if remove_original:
                    recycle_ok = False
                    recycle_err = None
                    try:
                        import send2trash
                        send2trash.send2trash(str(p_src))
                        recycle_ok = True
                    except Exception as te:
                        recycle_err = str(te)

                    if recycle_ok:
                        return {"success": True, "message": f"Optimized image created: {os.path.basename(dst)} (Original moved to Recycle Bin)", "dst": dst}
                    else:
                        return {"success": True, "message": f"Optimized image created: {os.path.basename(dst)}, but failed to move original to Recycle Bin: {recycle_err}", "dst": dst, "warning": f"Recycle Bin error: {recycle_err}"}

                self._history = [{"action": "create", "src": str(p_src), "dst": dst}]
                self._save_history()
                return {"success": True, "message": f"Optimized image created: {os.path.basename(dst)}", "dst": dst}
            return {"success": False, "error": err or "Optimization failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @requires_lock
    def optimize_images(self, path: str, quality: int = 85, remove_original: bool = False, dry_run: bool = False):
        """Optimizes all images in a folder recursively."""
        try:
            w_canon = path_guard.validate_workspace(path)
            self._current_workspace = str(w_canon)
            exts = ['.jpg', '.jpeg', '.png', '.webp']
            files = [f for f in w_canon.rglob('*') if f.is_file() and f.suffix.lower() in exts]
            if not files: return {"success": True, "message": "No images found to optimize."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} images would be optimized."}

            results = []
            new_history = []
            failures = []
            recycled_count = 0
            recycle_failures = []
            for idx, file in enumerate(files):
                dst, err = media_service.optimize_image(str(file), quality, self._update_progress)
                if dst:
                    results.append(dst)
                    if remove_original:
                        try:
                            import send2trash
                            send2trash.send2trash(str(file))
                            recycled_count += 1
                        except Exception as te:
                            recycle_failures.append(f"Failed to recycle {file.name}: {te}")
                    else:
                        new_history.append({"action": "create", "src": str(file), "dst": dst})
                else:
                    failures.append(err or file.name)
                self._update_progress(int(((idx + 1) / len(files)) * 100))

            if not remove_original:
                self._history = new_history
                self._save_history()
            msg = f"Successfully optimized {len(results)} images."
            if remove_original:
                if len(results) > 0 and len(recycle_failures) == 0:
                    msg += " (Originals moved to Recycle Bin)."
                elif recycled_count > 0:
                    msg += f" ({recycled_count} moved to Recycle Bin; {len(recycle_failures)} could not be recycled)."
                else:
                    msg += f" (Warning: {len(recycle_failures)} original(s) could not be moved to Recycle Bin)."
            if failures:
                msg += f" {len(failures)} failed."
            all_errors = failures + recycle_failures
            return {"success": True, "message": msg, "items": results, "errors": all_errors}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Alias to ensure exact match with operation_registry naming
    batch_optimize_images = optimize_images

def start_app():
    api = OrganizerAPI()
    base_dir = get_base_dir()
    dist_path = base_dir / 'ui' / 'dist' / 'index.html'
    icon_path = base_dir / 'icon.ico'

    if dist_path.exists():
        url = dist_path.absolute().as_uri()
    elif os.environ.get("FOP_DEV_SERVER") == "1":
        url = 'http://localhost:5173'
        print("[WARNING] Running in development mode with FOP_DEV_SERVER=1 against http://localhost:5173")
    else:
        raise FileNotFoundError(
            f"Production UI bundle not found at '{dist_path}'. "
            "Please build the UI before launching (run 'npm run build' in 'ui/'), "
            "or set environment variable FOP_DEV_SERVER=1 to allow local Vite development."
        )
    
    window = webview.create_window(
        'Folders Organizer Pro', url, js_api=api,
        width=1440, height=920, resizable=True,
        min_size=(1180, 780), background_color='#F3EEE4'
    )
    api.set_window(window)
    webview.start(debug=False, icon=str(icon_path) if icon_path.exists() else None)

if __name__ == '__main__':
    start_app()

