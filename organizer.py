import os
import shutil
import webview
import json
import datetime
from pathlib import Path
from typing import List, Dict

# Import refactored services
from services import file_service, duplicate_service, organizer_service, automation_service, media_service

# System-critical Windows directories — operations blocked without explicit user consent
_SYSTEM_CRITICAL_DIRS = {
    'windows', 'system32', 'syswow64', 'program files', 'program files (x86)',
    'programdata', 'appdata', 'system volume information', 'recovery',
    '$recycle.bin', 'boot', 'efi'
}

def is_system_critical_dir(path: str) -> bool:
    """Returns True if path matches a known system-critical directory."""
    p = Path(path)
    # Check all parts of the path
    for part in p.parts:
        if part.lower().rstrip('\\') in _SYSTEM_CRITICAL_DIRS:
            return True
    # Also block root drive paths like C:\ directly
    if p == p.anchor and len(str(p)) <= 4:
        return True
    return False

import subprocess
VERSION = "5.0.3"

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
            self._window.evaluate_js("""document.querySelectorAll('[class*="log"], [class*="console"], [class*="output"], [id*="log"]').forEach(function(el){ el.scrollTop = el.scrollHeight; });""")


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
            system_warning = is_system_critical_dir(result[0])
            return {"path": result[0], "system_warning": system_warning}
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

    def undo_last_operation(self, *args, **kwargs):
        """Reverts the changes made in the last operation.
        Accepts extra args to prevent frontend mismatch.
        """
        if not self._history:
            return {"success": False, "error": "No history found to undo."}

        try:
            total = len(self._history)
            success_count = 0
            fail_count = 0
            errors = []

            # Revert in reverse order
            for idx, entry in enumerate(reversed(self._history)):
                try:
                    # Support both old (tuple) and new (dict) history formats
                    if isinstance(entry, (list, tuple)):
                        action = "move"
                        src, dst = entry
                    else:
                        action = entry.get("action", "move")
                        src = entry.get("src")
                        dst = entry.get("dst")

                    if action == "move":
                        if Path(dst).exists():
                            # Ensure parent exists if it was pruned
                            Path(src).parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(dst, src)
                            success_count += 1
                        else:
                            fail_count += 1
                            errors.append(f"File not found: {Path(dst).name}")
                    elif action == "create":
                        # For unzipping or conversion, we delete the created part
                        target = Path(dst)
                        if target.exists():
                            if target.is_dir():
                                shutil.rmtree(target)
                            else:
                                target.unlink()
                            success_count += 1
                        else:
                            fail_count += 1
                    elif action == "copy":
                        # For backup, we delete the copy in dest
                        target = Path(dst)
                        if target.exists():
                            target.unlink()
                            success_count += 1
                        else:
                            fail_count += 1
                except Exception as file_err:
                    fail_count += 1
                    errors.append(str(file_err))
                
                self._update_progress(int(((idx + 1) / total) * 100))
            
            # Reset history after attempt
            self._history = []
            self._save_history()

            if fail_count == 0:
                return {"success": True, "message": f"Successfully reverted {success_count} changes."}
            else:
                return {
                    "success": True, 
                    "message": f"Reverted {success_count} items. {fail_count} failed.",
                    "details": errors[:5]
                }
        except Exception as e:
            return {"success": False, "error": f"Critical undo failure: {str(e)}"}

    def sequential_rename(self, path: str, prefix: str, mode: str = "files", sort_mode: str = "name", dry_run: bool = False, filter_str: str = "", use_regex: bool = False):
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
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

    def find_duplicates(self, path: str, options=None):
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
        try:
            dupes = duplicate_service.find_duplicates(path, self._update_progress)
            if not dupes:
                return {"success": True, "message": "No duplicates found.", "duplicates": []}
            return {"success": True, "message": f"Found {len(dupes)} groups of duplicates.", "duplicates": dupes}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_duplicates(self, path: str, groups: list, dry_run: bool = False):
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
        try:
            if dry_run:
                total_to_delete = sum(len(group) - 1 for group in groups)
                return {"success": True, "message": f"Simulation: {total_to_delete} duplicate files would be removed."}

            count = duplicate_service.delete_duplicates(groups, self._update_progress)
            return {"success": True, "message": f"Successfully moved {count} duplicates to Recycle Bin."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sort_by_date(self, path: str, grain: str = "month", dry_run: bool = False):
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
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
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
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
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
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
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
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
        if is_system_critical_dir(path):
            return {"success": False, "error": f"Operation blocked: '{path}' is a system-critical directory."}
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

    # ─────────────────────────────────────────────
    # Advanced Automation Methods
    # ─────────────────────────────────────────────

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

    def advanced_regex_rename(self, path: str, pattern: str, replacement: str, dry_run: bool = False):
        """Batch rename files using regex find/replace."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.advanced_regex_rename(path, pattern, replacement, dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files would be renamed." if dry_run else f"Renamed {count} files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup_old_files(self, path: str, days: int = 90, dry_run: bool = False):
        """Archives files older than `days` to a .archived_files subfolder."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.cleanup_old_files(path, days, dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files older than {days} days would be archived." if dry_run else f"Archived {count} old files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def batch_unzip(self, path: str, dry_run: bool = False):
        """Extracts common archives (.zip, .rar, .7z, etc.) into named subfolders."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.batch_unzip(path, dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} archives would be extracted." if dry_run else f"Extracted {count} archives."
            return {"success": True, "message": msg, "items": [h['dst'] for h in history]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def archive_large_files(self, path: str, threshold_mb: float = 500.0, dry_run: bool = False):
        """Moves files over threshold_mb MB into a LargeFiles subfolder."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.archive_large_files(path, threshold_mb, dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files over {threshold_mb}MB would be moved." if dry_run else f"Moved {count} large files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def additive_backup(self, src: str, dest: str, dry_run: bool = False):
        """Copies new/updated files from src to dest. Never deletes."""
        try:
            if is_system_critical_dir(src) or is_system_critical_dir(dest):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.additive_backup(src, dest, dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} files would be backed up." if dry_run else f"Backed up {count} files."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def convert_image_formats(self, path: str, source_exts: list, target_ext: str, dry_run: bool = False):
        """Batch converts images to target format using Pillow."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            history, count = automation_service.convert_image_formats(path, source_exts, target_ext, dry_run, self._update_progress)
            if not dry_run:
                self._history = history
                self._save_history()
            msg = f"Simulation: {count} images would be converted." if dry_run else f"Converted {count} images."
            return {"success": True, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────
    # v5.0 Media Processing Methods
    # ─────────────────────────────────────────────

    def get_audio_files(self, path: str):
        """Returns a list of all audio files (.mp3) in the active workspace."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            p = Path(path)
            if not p.exists() or not p.is_dir():
                return {"success": False, "error": "Invalid workspace path."}
                
            files = []
            for f in p.rglob('*.mp3'):
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
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            p = Path(path)
            if not p.exists() or not p.is_dir():
                return {"success": False, "error": "Invalid workspace path."}
                
            files = []
            for f in p.rglob('*.pdf'):
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
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            p = Path(path)
            if not p.exists() or not p.is_dir():
                return {"success": False, "error": "Invalid workspace path."}
                
            files = []
            exts = ['.jpg', '.jpeg', '.png', '.webp']
            for f in p.rglob('*'):
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

    def convert_mp3_to_wav(self, file_path: str, remove_original: bool = False):
        """Converts a specific MP3 file to WAV."""
        try:
            if is_system_critical_dir(file_path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            dst = media_service.convert_mp3_to_wav(file_path, self._update_progress)
            if not dst:
                return {"success": False, "error": "Conversion failed."}
                
            self._history = [{"action": "create", "src": file_path, "dst": dst}]
            
            # If requested, send the original .mp3 to the Recycle Bin
            if remove_original:
                try:
                    import send2trash
                    send2trash.send2trash(file_path)
                except:
                    pass
                    
            self._save_history()
            return {"success": True, "message": f"Converted to: {os.path.basename(dst)}", "dst": dst}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def batch_convert_mp3_to_wav(self, path: str, remove_original: bool = False, dry_run: bool = False):
        """Converts all MP3 files in a folder to WAV."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            p = Path(path)
            files = [f for f in p.rglob('*.mp3') if f.is_file()]
            if not files: return {"success": True, "message": "No MP3 files found to convert."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} MP3 files would be converted."}

            results = []
            new_history = []
            
            for idx, file in enumerate(files):
                dst = media_service.convert_mp3_to_wav(str(file), self._update_progress)
                if dst:
                    results.append(dst)
                    new_history.append({"action": "create", "src": str(file), "dst": dst})
                    
                    if remove_original:
                        try:
                            import send2trash
                            send2trash.send2trash(str(file))
                        except:
                            pass
                            
                self._update_progress(int(((idx + 1) / len(files)) * 100))
            
            self._history = new_history
            self._save_history()
            return {"success": True, "message": f"Successfully converted {len(results)} MP3 files to WAV."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compress_pdf(self, file_path: str, remove_original: bool = False):
        """Compresses a specific PDF file."""
        try:
            if is_system_critical_dir(file_path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            dst = media_service.compress_pdf(file_path, self._update_progress)
            if dst:
                if remove_original:
                    try:
                        import send2trash
                        send2trash.send2trash(file_path)
                    except:
                        pass
                self._history = [{"action": "create", "src": file_path, "dst": dst}]
                self._save_history()
                return {"success": True, "message": f"Compressed PDF created: {os.path.basename(dst)}", "dst": dst}
            return {"success": False, "error": "Compression failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def batch_compress_pdf(self, path: str, remove_original: bool = False, dry_run: bool = False):
        """Compresses all PDF files in a folder recursively."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            p = Path(path)
            files = [f for f in p.rglob('*.pdf') if f.is_file()]
            if not files: return {"success": True, "message": "No PDF files found to compress."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} PDF files would be compressed."}

            results = []
            new_history = []
            
            for idx, file in enumerate(files):
                dst = media_service.compress_pdf(str(file), self._update_progress)
                if dst:
                    results.append(dst)
                    new_history.append({"action": "create", "src": str(file), "dst": dst})
                    
                    if remove_original:
                        try:
                            import send2trash
                            send2trash.send2trash(str(file))
                        except:
                            pass
                            
                self._update_progress(int(((idx + 1) / len(files)) * 100))
            
            self._history = new_history
            self._save_history()
            return {"success": True, "message": f"Successfully compressed {len(results)} PDF files."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def optimize_image(self, file_path: str, quality: int = 85, remove_original: bool = False):
        """Optimizes a single image."""
        try:
            if is_system_critical_dir(file_path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            dst = media_service.optimize_image(file_path, quality, self._update_progress)
            if dst:
                if remove_original:
                    try:
                        import send2trash
                        send2trash.send2trash(file_path)
                    except:
                        pass
                self._history = [{"action": "create", "src": file_path, "dst": dst}]
                self._save_history()
                return {"success": True, "message": f"Optimized image created: {os.path.basename(dst)}", "dst": dst}
            return {"success": False, "error": "Optimization failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def optimize_images(self, path: str, quality: int = 85, remove_original: bool = False, dry_run: bool = False):
        """Optimizes all images in a folder recursively."""
        try:
            if is_system_critical_dir(path):
                return {"success": False, "error": "System-critical directory. Operation blocked."}
            p = Path(path)
            exts = ['.jpg', '.jpeg', '.png', '.webp']
            files = [f for f in p.rglob('*') if f.is_file() and f.suffix.lower() in exts]
            if not files: return {"success": True, "message": "No images found to optimize."}
            if dry_run: return {"success": True, "message": f"Simulation: {len(files)} images would be optimized."}

            results = []
            new_history = []
            for idx, file in enumerate(files):
                dst = media_service.optimize_image(str(file), quality, self._update_progress)
                if dst:
                    results.append(dst)
                    new_history.append({"action": "create", "src": str(file), "dst": dst})
                    
                    if remove_original:
                        try:
                            import send2trash
                            send2trash.send2trash(str(file))
                        except:
                            pass
                            
                self._update_progress(int(((idx + 1) / len(files)) * 100))
            
            self._history = new_history
            self._save_history()
            
            return {"success": True, "message": f"Successfully optimized {len(results)} images.", "items": results}
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
