"""Shared canonical path policy and filesystem boundary security guard.

Provides single-source-of-truth validation for all workspace roots, source items,
destination targets, and custom rule folders across the application.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath
from typing import Set

class PathSecurityError(ValueError):
    """Raised when a path violates workspace containment, system safety,
    or Windows filename validity constraints."""
    pass

# System-critical directories where operations must be unconditionally blocked
_SYSTEM_CRITICAL_DIRS: Set[str] = {
    'windows', 'winnt', 'system32', 'syswow64', 'drivers',
    'program files', 'program files (x86)', 'common files',
    'programdata', 'appdata', 'system volume information',
    'recovery', '$recycle.bin', 'boot', 'bootmgr', 'efi', 'msocache'
}

# Windows reserved DOS device names (forbid as stems or directory names)
_RESERVED_DEVICE_NAMES: Set[str] = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10))
}

# Illegal characters in Windows filenames: < > : " | ? * and ASCII control characters (0-31)
_ILLEGAL_CHAR_REGEX = re.compile(r'[\x00-\x1f<>:"|?*]')

_DEVICE_PREFIXES = ('\\\\.\\', '//./')


def is_bare_root(p: PureWindowsPath) -> bool:
    """Returns True if the path represents a bare volume, drive, device, or UNC root."""
    if not p.anchor:
        return False
    clean_str = str(p).rstrip('\\/')
    clean_anchor = p.anchor.rstrip('\\/')
    return clean_str == clean_anchor


def is_system_critical(path: str | Path) -> bool:
    """Returns True if path targets a drive root, UNC root, device namespace,
    or a known system-critical Windows directory."""
    if path is None:
        return True
    
    path_str = str(path).strip()
    if not path_str:
        return True

    # Block Win32 device namespace paths (e.g. \\.\C:, \\.\PhysicalDrive0)
    if path_str.startswith(_DEVICE_PREFIXES):
        return True

    # Reject null bytes immediately
    if '\0' in path_str:
        return True

    # Try resolving to realpath if possible, otherwise use original string
    try:
        resolved_str = str(Path(path_str).resolve(strict=False))
    except Exception:
        resolved_str = path_str

    candidates = (
        PureWindowsPath(resolved_str),
        PureWindowsPath(path_str)
    )

    for candidate in candidates:
        # 1. Check if it is a bare drive root, extended drive root (\\?\C:\), or UNC share root
        if is_bare_root(candidate):
            return True

        # 2. Check parts against known critical directories
        for part in candidate.parts:
            part_clean = part.lower().rstrip('\\/')
            if part_clean in _SYSTEM_CRITICAL_DIRS:
                return True

    # 3. Check dynamically against active Windows environment system roots
    for env_var in ('SystemRoot', 'ProgramFiles', 'ProgramFiles(x86)', 'ProgramData', 'WinDir'):
        env_val = os.environ.get(env_var)
        if env_val:
            try:
                env_p = PureWindowsPath(env_val).resolve(strict=False) if hasattr(PureWindowsPath, 'resolve') else PureWindowsPath(os.path.realpath(env_val))
                for cand in candidates:
                    cand_pure = PureWindowsPath(os.path.realpath(str(cand))) if hasattr(cand, '__fspath__') else PureWindowsPath(str(cand))
                    if str(cand_pure).lower() == str(env_p).lower():
                        return True
            except Exception:
                pass

    return False


def canonicalize_path(path: str | Path) -> Path:
    """Resolves symlinks, junctions, and relative segments into a normalized absolute Path.
    Rejects null bytes, Win32 device namespaces, and Alternate Data Streams (ADS)."""
    if path is None:
        raise PathSecurityError("Path cannot be None.")

    path_str = str(path).strip()
    if not path_str:
        raise PathSecurityError("Path cannot be empty.")

    if '\0' in path_str:
        raise PathSecurityError("Null bytes are not permitted in filesystem paths.")

    if path_str.startswith(_DEVICE_PREFIXES):
        raise PathSecurityError("Win32 device namespace paths are prohibited.")

    # Detect Alternate Data Streams (ADS): colon at position > 1 or colon without drive letter
    clean_norm = path_str.replace('/', '\\')
    if clean_norm.startswith('\\\\?\\'):
        rest = clean_norm[4:]
        if len(rest) > 2 and rest[1] == ':':
            # e.g. \\?\C:\foo:bar
            after_drive = rest[2:]
            if ':' in after_drive:
                raise PathSecurityError("Alternate Data Streams (ADS) are prohibited.")
        elif ':' in rest:
            raise PathSecurityError("Alternate Data Streams (ADS) are prohibited.")
    else:
        if len(clean_norm) > 2 and clean_norm[1] == ':':
            # e.g. C:\foo:bar
            if ':' in clean_norm[2:]:
                raise PathSecurityError("Alternate Data Streams (ADS) are prohibited.")
        elif ':' in clean_norm:
            raise PathSecurityError("Alternate Data Streams (ADS) are prohibited.")

    try:
        resolved = Path(path_str).resolve(strict=False)
        return resolved
    except Exception as e:
        raise PathSecurityError(f"Cannot resolve path '{path_str}': {e}") from e


def validate_workspace(path: str | Path) -> Path:
    """Validates that a workspace path exists, is a directory, and is not system-critical."""
    canon = canonicalize_path(path)

    if not canon.exists():
        raise PathSecurityError(f"Workspace directory does not exist: '{canon}'")

    if not canon.is_dir():
        raise PathSecurityError(f"Workspace path is not a directory: '{canon}'")

    if is_system_critical(canon) or is_system_critical(path):
        raise PathSecurityError(f"Drive roots and system-critical directories cannot be used as workspaces: '{path}'")

    return canon


def validate_source(path: str | Path, workspace: str | Path) -> Path:
    """Validates that a source file/folder exists, is contained within the workspace,
    and is not the workspace root itself."""
    w_canon = validate_workspace(workspace)
    s_canon = canonicalize_path(path)

    if not s_canon.exists():
        raise PathSecurityError(f"Source does not exist: '{s_canon}'")

    try:
        is_rel = s_canon.is_relative_to(w_canon)
    except ValueError:
        is_rel = False

    if not is_rel:
        raise PathSecurityError(f"Source path '{s_canon}' escapes authorized workspace '{w_canon}'.")

    if s_canon == w_canon:
        raise PathSecurityError("Source item cannot be the workspace root directory itself.")

    if is_system_critical(s_canon):
        raise PathSecurityError(f"Source item is located in a system-critical directory: '{s_canon}'.")

    return s_canon


def validate_destination(path: str | Path, workspace: str | Path, allow_sibling: bool = False) -> Path:
    """Validates a destination target path. Ensures it does not escape the workspace
    via traversal or absolute redirection (unless allow_sibling is explicitly True, e.g. for backups).
    Checks for illegal Windows characters and reserved device names."""
    w_canon = validate_workspace(workspace)
    
    if path is None:
        raise PathSecurityError("Destination path cannot be None.")
    
    raw_str = str(path).strip()
    if not raw_str:
        raise PathSecurityError("Destination path cannot be empty.")

    # Check for raw directory traversal tokens before resolution
    raw_normalized = raw_str.replace('\\', '/')
    parts = [p for p in raw_normalized.split('/') if p]
    for part in parts:
        if part == '..':
            raise PathSecurityError(f"Directory traversal ('..') is prohibited in destination: '{raw_str}'")
        # Check for reserved DOS device names
        stem = part.split('.')[0].lower()
        if stem in _RESERVED_DEVICE_NAMES:
            raise PathSecurityError(f"Reserved Windows device name '{stem}' is prohibited in destination: '{raw_str}'")
        # Check for illegal characters in destination segments
        # (Exclude drive letter separator ':' from part check if it's the drive root part)
        part_to_check = part
        if len(part) == 2 and part[1] == ':':
            part_to_check = part[0]
        if _ILLEGAL_CHAR_REGEX.search(part_to_check):
            raise PathSecurityError(f"Illegal Windows characters in destination component '{part}': '{raw_str}'")
        if part.endswith('.') or part.endswith(' '):
            raise PathSecurityError(f"Trailing dots or spaces in destination component '{part}' are prohibited.")

    # If relative, anchor to workspace
    p_obj = Path(raw_str)
    if not p_obj.is_absolute():
        # Check if resolving relative to cwd already places it inside w_canon
        cwd_resolved = canonicalize_path(p_obj)
        try:
            is_inside_w = cwd_resolved.is_relative_to(w_canon)
        except ValueError:
            is_inside_w = False

        if is_inside_w or allow_sibling:
            dest_canon = cwd_resolved
        else:
            dest_canon = canonicalize_path(w_canon / p_obj)
    else:
        dest_canon = canonicalize_path(p_obj)

    if not allow_sibling:
        try:
            is_rel = dest_canon.is_relative_to(w_canon)
        except ValueError:
            is_rel = False

        if not is_rel:
            raise PathSecurityError(f"Destination '{dest_canon}' escapes authorized workspace '{w_canon}'.")

        if dest_canon == w_canon:
            raise PathSecurityError("Destination cannot be the workspace root directory itself.")
    else:
        # Sibling allowed (e.g. backup destination)
        if dest_canon == w_canon:
            raise PathSecurityError("Backup destination cannot be identical to the source workspace.")
        try:
            is_inside = dest_canon.is_relative_to(w_canon)
        except ValueError:
            is_inside = False
        if is_inside:
            raise PathSecurityError("Backup destination cannot be inside the source workspace (would cause recursive backup loop).")

        try:
            w_inside_dest = w_canon.is_relative_to(dest_canon)
        except ValueError:
            w_inside_dest = False
        if w_inside_dest:
            raise PathSecurityError("Source workspace cannot be inside the backup destination.")

    if is_system_critical(dest_canon):
        raise PathSecurityError(f"Destination targets a system-critical directory: '{dest_canon}'.")

    return dest_canon


def sanitize_folder_name(name: str) -> str:
    """Sanitizes and validates a relative folder or category name (e.g. for custom rules).
    Rejects traversal (..), absolute paths, drive roots, illegal characters, and device names.
    Returns a clean, forward-slash normalized relative subpath."""
    if name is None:
        raise PathSecurityError("Folder name cannot be None.")

    clean = name.strip()
    if not clean:
        raise PathSecurityError("Folder name cannot be empty.")

    clean_norm = clean.replace('\\', '/')
    if clean_norm.startswith('/'):
        raise PathSecurityError(f"Absolute folder paths are not permitted in rule folders: '{clean}'")

    # Check for drive specification
    if len(clean) > 1 and clean[1] == ':':
        raise PathSecurityError(f"Drive-qualified paths are not permitted in rule folders: '{clean}'")

    parts = [p.strip() for p in clean_norm.split('/') if p.strip()]
    if not parts:
        raise PathSecurityError("Folder name cannot resolve to empty path.")

    sanitized_parts = []
    for part in parts:
        if part == '..':
            raise PathSecurityError(f"Directory traversal ('..') is not permitted in rule folders: '{clean}'")
        if part == '.':
            continue

        if part.endswith('.') or part.endswith(' '):
            raise PathSecurityError(f"Trailing dots or spaces are not permitted in folder name '{part}'.")

        stem = part.split('.')[0].lower()
        if stem in _RESERVED_DEVICE_NAMES:
            raise PathSecurityError(f"Reserved device name '{stem}' is not permitted in rule folder '{part}'.")

        if _ILLEGAL_CHAR_REGEX.search(part):
            raise PathSecurityError(f"Folder name '{part}' contains illegal characters.")

        sanitized_parts.append(part)

    if not sanitized_parts:
        raise PathSecurityError("Folder name cannot resolve to empty path.")

    return '/'.join(sanitized_parts)


def is_safe_relative_subpath(subpath: str) -> bool:
    """Returns True if the subpath is safe and strictly relative with no traversal."""
    try:
        sanitize_folder_name(subpath)
        return True
    except PathSecurityError:
        return False
