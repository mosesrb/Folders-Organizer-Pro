"""Transactional operation journal and safe undo engine.

Resolves FOP-AUD-001, FOP-AUD-004, and FOP-AUD-014 by enforcing strict schema validation,
workspace containment, non-permanent Recycle Bin deletion, incremental transaction
logging, and preservation of recovery state on partial failure.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import send2trash

from .path_guard import (
    PathSecurityError,
    canonicalize_path,
    is_system_critical,
    validate_destination,
    validate_source,
    validate_workspace,
)

JOURNAL_SCHEMA_VERSION = "2.0"
HISTORY_FILENAME = ".organizer_history.json"


class JournalAction(str, Enum):
    MOVE = "move"
    CREATE = "create"
    COPY = "copy"


@dataclass
class JournalEntry:
    action: str
    src: str
    dst: str
    timestamp: float = field(default_factory=time.time)
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    initial_stat: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JournalEntry:
        return cls(
            action=str(data.get("action", "")).lower(),
            src=str(data.get("src", "")),
            dst=str(data.get("dst", "")),
            timestamp=float(data.get("timestamp", time.time())),
            entry_id=str(data.get("entry_id", uuid.uuid4().hex[:12])),
            initial_stat=data.get("initial_stat"),
        )


@dataclass
class JournalBatch:
    version: str
    operation_id: str
    operation_name: str
    workspace: str
    created_at: float = field(default_factory=time.time)
    entries: List[JournalEntry] = field(default_factory=list)
    status: str = "completed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "operation_id": self.operation_id,
            "operation_name": self.operation_name,
            "workspace": self.workspace,
            "created_at": self.created_at,
            "entries": [e.to_dict() for e in self.entries],
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JournalBatch:
        raw_entries = data.get("entries", [])
        parsed_entries = [JournalEntry.from_dict(e) for e in raw_entries]
        return cls(
            version=str(data.get("version", JOURNAL_SCHEMA_VERSION)),
            operation_id=str(data.get("operation_id", uuid.uuid4().hex[:12])),
            operation_name=str(data.get("operation_name", "unknown")),
            workspace=str(data.get("workspace", "")),
            created_at=float(data.get("created_at", time.time())),
            entries=parsed_entries,
            status=str(data.get("status", "completed")),
        )


def quarantine_invalid_history(history_file: Path, reason: str) -> Path:
    """Safely renames an untrusted or corrupted history file out of active operation."""
    timestamp = int(time.time())
    quarantine_name = f".organizer_history.quarantined_{timestamp}_{uuid.uuid4().hex[:6]}.json"
    quarantine_path = history_file.parent / quarantine_name
    try:
        if history_file.exists():
            shutil.move(str(history_file), str(quarantine_path))
            meta_path = quarantine_path.with_suffix(".reason.txt")
            meta_path.write_text(f"Quarantined at {time.ctime(timestamp)}\nReason: {reason}\n", encoding="utf-8")
    except Exception:
        pass
    return quarantine_path


def load_and_validate_journal(workspace_path: str | Path) -> Tuple[Optional[JournalBatch], Optional[str]]:
    """Loads and strictly validates the workspace journal.
    If the file is missing, returns (None, None).
    If the file is untrusted, malformed, or targets paths outside workspace,
    it is immediately quarantined and an error message is returned."""
    try:
        w_canon = validate_workspace(workspace_path)
    except PathSecurityError as e:
        return None, f"Invalid workspace: {e}"

    history_file = w_canon / HISTORY_FILENAME
    if not history_file.exists():
        return None, None

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        quarantine_invalid_history(history_file, f"Malformed JSON: {e}")
        return None, f"Corrupt history file quarantined: {e}"

    # Check for legacy list format (FOP-AUD-001 reproduction vulnerability)
    if isinstance(raw_data, list):
        quarantine_invalid_history(
            history_file,
            "Legacy unverified list-based history format is prohibited for security."
        )
        return None, "Untrusted legacy history format rejected and quarantined."

    if not isinstance(raw_data, dict):
        quarantine_invalid_history(history_file, "Root element of history is not an object.")
        return None, "Untrusted history file structure rejected."

    # Validate schema version
    version = raw_data.get("version")
    if version != JOURNAL_SCHEMA_VERSION:
        quarantine_invalid_history(history_file, f"Unsupported history version '{version}'.")
        return None, f"Unsupported history version '{version}' quarantined."

    # Validate recorded workspace matches current canonical workspace
    recorded_workspace = raw_data.get("workspace", "").strip()
    try:
        recorded_canon = canonicalize_path(recorded_workspace)
        if recorded_canon != w_canon:
            quarantine_invalid_history(
                history_file,
                f"Workspace mismatch: recorded '{recorded_canon}' != actual '{w_canon}'"
            )
            return None, "History workspace origin mismatch; rejected for security."
    except Exception as e:
        quarantine_invalid_history(history_file, f"Unresolvable workspace path: {e}")
        return None, "Invalid workspace path in history file."

    # Validate entries and containment
    batch = JournalBatch.from_dict(raw_data)
    valid_actions = {a.value for a in JournalAction}

    for idx, entry in enumerate(batch.entries):
        if entry.action not in valid_actions:
            quarantine_invalid_history(history_file, f"Unknown action '{entry.action}' at entry {idx}.")
            return None, f"Unknown action '{entry.action}' in history; rejected."

        # Validate destination containment
        try:
            dst_path = canonicalize_path(entry.dst)
            if not dst_path.is_relative_to(w_canon) or dst_path == w_canon:
                quarantine_invalid_history(
                    history_file,
                    f"Destination escape at entry {idx}: '{dst_path}' outside '{w_canon}'"
                )
                return None, f"Entry {idx} target escapes workspace; history quarantined."
            if is_system_critical(dst_path):
                quarantine_invalid_history(history_file, f"System critical target at entry {idx}.")
                return None, "Entry targets a system critical path; quarantined."
        except Exception as e:
            quarantine_invalid_history(history_file, f"Invalid destination path at entry {idx}: {e}")
            return None, f"Invalid destination path at entry {idx}."

        # Validate source containment if MOVE
        if entry.action == JournalAction.MOVE.value:
            try:
                src_path = canonicalize_path(entry.src)
                if not src_path.is_relative_to(w_canon) or src_path == w_canon:
                    quarantine_invalid_history(
                        history_file,
                        f"Source escape at entry {idx}: '{src_path}' outside '{w_canon}'"
                    )
                    return None, f"Entry {idx} source escapes workspace; history quarantined."
                if is_system_critical(src_path):
                    quarantine_invalid_history(history_file, f"System critical source at entry {idx}.")
                    return None, "Entry source is a system critical path; quarantined."
            except Exception as e:
                quarantine_invalid_history(history_file, f"Invalid source path at entry {idx}: {e}")
                return None, f"Invalid source path at entry {idx}."
    return batch, None


# Alias for load_and_validate_journal
load_journal = load_and_validate_journal


def save_journal(batch: Optional[JournalBatch], workspace_path: str | Path) -> None:
    """Atomically writes or cleans up the workspace history file."""
    w_canon = validate_workspace(workspace_path)
    history_file = w_canon / HISTORY_FILENAME

    if batch is None or not batch.entries:
        if history_file.exists():
            try:
                history_file.unlink()
            except OSError:
                pass
        return

    tmp_file = w_canon / f"{HISTORY_FILENAME}.tmp_{uuid.uuid4().hex[:6]}"
    try:
        data = batch.to_dict()
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_file), str(history_file))
    finally:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass


class TransactionJournal:
    """Incremental transaction journal writer for batch operations.
    Ensures partial progress is immediately durable on disk so crashes
    or mid-batch errors can still be safely reverted (FOP-AUD-004)."""

    def __init__(self, workspace_path: str | Path, operation_name: str):
        self.workspace = validate_workspace(workspace_path)
        self.operation_name = operation_name
        self.batch = JournalBatch(
            version=JOURNAL_SCHEMA_VERSION,
            operation_id=f"{operation_name}_{int(time.time())}_{uuid.uuid4().hex[:6]}",
            operation_name=operation_name,
            workspace=str(self.workspace),
            created_at=time.time(),
            entries=[],
            status="in_progress",
        )

    def record_step(
        self,
        action: str | JournalAction,
        src: str | Path,
        dst: str | Path,
        initial_stat: Optional[Dict[str, Any]] = None,
    ) -> JournalEntry:
        """Records a single completed filesystem mutation and flushes to disk."""
        act_str = action.value if isinstance(action, JournalAction) else str(action).lower()
        entry = JournalEntry(
            action=act_str,
            src=str(src),
            dst=str(dst),
            timestamp=time.time(),
            initial_stat=initial_stat,
        )
        self.batch.entries.append(entry)
        save_journal(self.batch, self.workspace)
        return entry

    def commit(self) -> None:
        """Marks the transaction batch as cleanly completed."""
        self.batch.status = "completed"
        save_journal(self.batch, self.workspace)

    def abort_with_partial(self) -> None:
        """Marks the transaction batch as partially completed due to failure."""
        self.batch.status = "partial_failure"
        save_journal(self.batch, self.workspace)


def revert_journal(
    workspace_path: str | Path,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """Safely reverts the last operation recorded in the workspace journal.
    Uses send2trash for created/copied objects (never permanent unlink or rmtree).
    Preserves failed entries in history so recovery is not lost."""
    callback = progress_callback or (lambda _: None)

    batch, error = load_and_validate_journal(workspace_path)
    if error:
        return {"success": False, "error": error}
    if not batch or not batch.entries:
        return {"success": False, "error": "No valid history found to undo."}

    w_canon = validate_workspace(workspace_path)
    total = len(batch.entries)
    success_count = 0
    fail_count = 0
    errors: List[str] = []

    remaining_entries = list(batch.entries)

    # Process in reverse order (LIFO)
    for idx, entry in enumerate(reversed(batch.entries)):
        item_success = False
        try:
            dst_path = canonicalize_path(entry.dst)
            # Verify containment again before touch
            if not dst_path.is_relative_to(w_canon) or dst_path == w_canon or is_system_critical(dst_path):
                raise PathSecurityError(f"Target '{dst_path}' is outside authorized workspace.")

            if entry.action == JournalAction.MOVE.value:
                src_path = canonicalize_path(entry.src)
                if not src_path.is_relative_to(w_canon) or src_path == w_canon or is_system_critical(src_path):
                    raise PathSecurityError(f"Source destination '{src_path}' is outside authorized workspace.")

                if dst_path.exists():
                    src_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst_path), str(src_path))
                    item_success = True
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"File not found to restore: '{dst_path.name}'")

            elif entry.action in (JournalAction.CREATE.value, JournalAction.COPY.value):
                # For created outputs or backup copies, move to Recycle Bin
                if dst_path.exists():
                    send2trash.send2trash(str(dst_path))
                    item_success = True
                    success_count += 1
                else:
                    # Target already gone: count as recovered
                    item_success = True
                    success_count += 1
            else:
                fail_count += 1
                errors.append(f"Unsupported action: '{entry.action}'")

        except Exception as err:
            fail_count += 1
            errors.append(f"Failed to revert {entry.dst}: {err}")

        if item_success:
            # Remove reverted entry from remaining
            if entry in remaining_entries:
                remaining_entries.remove(entry)

        callback(int(((idx + 1) / total) * 100))

    # Persist remaining entries so partial recovery is retained
    batch.entries = remaining_entries
    if remaining_entries:
        batch.status = "partial_reverted"
        save_journal(batch, w_canon)
    else:
        save_journal(None, w_canon)

    if fail_count == 0:
        return {
            "success": True,
            "message": f"Successfully reverted {success_count} changes.",
            "reverted": success_count,
            "failed": 0,
        }
    else:
        return {
            "success": success_count > 0,
            "message": f"Partially reverted {success_count} changes. {fail_count} failed.",
            "reverted": success_count,
            "failed": fail_count,
            "errors": errors,
        }
