import os
import shutil
import re
import datetime
import json
from pathlib import Path
from .file_service import is_locked

def sequential_rename(path: str, prefix: str, mode: str, sort_mode: str, dry_run: bool, filter_str: str, use_regex: bool, progress_callback):
    p = Path(path)
    if not p.exists():
        raise ValueError("Path does not exist")

    if mode == "files":
        items = [f for f in p.iterdir() if f.is_file()]
    else:
        items = [f for f in p.iterdir() if f.is_dir()]

    if filter_str:
        if use_regex:
            regex = re.compile(filter_str, re.IGNORECASE)
            items = [f for f in items if regex.search(f.name)]
        else:
            items = [f for f in items if filter_str.lower() in f.name.lower()]

    if not items:
        return [], 0

    if sort_mode == "date":
        items.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    else:
        items.sort(key=lambda x: x.name.lower())

    padding = max(2, len(str(len(items))))
    new_history = []
    total = len(items)

    for idx, item in enumerate(items):
        ext = item.suffix if mode == "files" else ""
        if use_regex and prefix:
            new_name = re.sub(filter_str, prefix, item.name, flags=re.IGNORECASE)
        else:
            new_name = f"{prefix}{str(idx + 1).zfill(padding)}{ext}"

        new_path = item.with_name(new_name)

        if not dry_run:
            if is_locked(item):
                raise IOError(f"Item '{item.name}' is busy.")

            final_path = new_path
            col_idx = 1
            while final_path.exists() and final_path != item:
                name_stem = Path(new_name).stem if mode == "files" else new_name
                final_path = item.with_name(f"{name_stem}_{col_idx}{ext}")
                col_idx += 1

            new_history.append((str(item), str(final_path)))
            os.rename(item, final_path)

        progress_callback(int(((idx + 1) / total) * 100))

    return new_history, len(items)

def sort_by_date(path: str, grain: str, dry_run: bool, progress_callback):
    p = Path(path)
    files = [f for f in p.iterdir() if f.is_file()]
    if not files:
        return [], 0

    if dry_run:
        return [], len(files)

    total = len(files)
    new_history = []
    for idx, file in enumerate(files):
        mtime = datetime.datetime.fromtimestamp(file.stat().st_mtime)
        year = str(mtime.year)
        month = mtime.strftime("%B")
        target_dir = p / year / month
        if grain == "day":
            target_dir = target_dir / str(mtime.day)

        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / file.name
        shutil.move(str(file), str(dest))
        new_history.append((str(file), str(dest)))
        progress_callback(int(((idx + 1) / total) * 100))

    return new_history, total

def flatten_workspace(path: str, dry_run: bool, progress_callback):
    p = Path(path)
    files_to_move = []

    def collect_files(target_path):
        try:
            with os.scandir(target_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        if Path(entry.path).parent != p:
                            files_to_move.append(Path(entry.path))
                    elif entry.is_dir(follow_symlinks=False):
                        collect_files(entry.path)
        except PermissionError: pass

    collect_files(path)
    if not files_to_move:
        return [], 0

    if dry_run:
        return [], len(files_to_move)

    total = len(files_to_move)
    new_history = []
    for idx, file in enumerate(files_to_move):
        dest = p / file.name
        if dest.exists():
            dest = p / f"{file.stem}_{idx}{file.suffix}"
        shutil.move(str(file), str(dest))
        new_history.append((str(file), str(dest)))
        progress_callback(int(((idx + 1) / total) * 100))

    def prune_empty_dirs(target_path):
        try:
            with os.scandir(target_path) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        prune_empty_dirs(entry.path)
            if target_path != path and not os.listdir(target_path):
                os.rmdir(target_path)
        except (PermissionError, OSError): pass

    prune_empty_dirs(path)
    return new_history, total

def smart_categorize(path: str, dry_run: bool, custom_rules: list, progress_callback):
    p = Path(path)
    category_map = {
        'Media/Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
        'Media/Video': ['.mp4', '.mkv', '.mov', '.avi', '.wmv'],
        'Media/Audio': ['.mp3', '.wav', '.flac', '.m4a'],
        'Documents': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.pptx', '.rtf'],
        'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'Code': ['.py', '.js', '.jsx', '.html', '.css', '.json', '.xml'],
    }
    keywords = {
        'Work': ['invoice', 'receipt', 'contract', 'resume', 'report', 'project', 'official'],
        'Personal': ['id', 'passport', 'medical', 'tax', 'legal', 'photo', 'home']
    }

    if custom_rules:
        for rule in custom_rules:
            folder = rule.get('folder', '').strip()
            if not folder: continue
            rule_exts = [e.strip().lower() if e.strip().startswith('.') else f'.{e.strip().lower()}' for e in rule.get('extensions', []) if e.strip()]
            rule_keys = [k.strip().lower() for k in rule.get('keywords', []) if k.strip()]
            if rule_exts: category_map[folder] = rule_exts
            if rule_keys: keywords[folder] = rule_keys

    files = [f for f in p.iterdir() if f.is_file()]
    if not files: return [], 0
    if dry_run: return [], len(files)

    new_history = []
    for idx, file in enumerate(files):
        target_cat = None
        name_lower = file.name.lower()
        for cat, keys in keywords.items():
            if any(k in name_lower for k in keys):
                target_cat = cat
                break
        if not target_cat:
            ext = file.suffix.lower()
            for cat, exts in category_map.items():
                if ext in exts:
                    target_cat = cat
                    break
        if not target_cat: target_cat = "Uncategorized"

        target_dir = p / target_cat
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / file.name
        shutil.move(str(file), str(dest))
        new_history.append((str(file), str(dest)))
        progress_callback(int(((idx + 1) / len(files)) * 100))

    return new_history, len(files)
