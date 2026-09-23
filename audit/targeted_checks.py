"""Disposable reproductions for safety findings found during the v5.0.4 audit.

Every filesystem mutation is confined to a TemporaryDirectory created by this
process. The checks report observed behavior; they intentionally do not modify
application source code.
"""

from __future__ import annotations

import json
import tempfile
import threading
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image

from organizer import OrganizerAPI, is_system_critical_dir
from services import media_service


def check_double_lock_deadlock() -> dict:
    with tempfile.TemporaryDirectory(prefix="fop-audit-deadlock-", dir=Path(__file__).parent) as tmp:
        api = OrganizerAPI()
        result = []
        worker = threading.Thread(
            target=lambda: result.append(api.delete_empty_folders(tmp, True)),
            daemon=True,
        )
        worker.start()
        worker.join(1.0)
        return {
            "completed_within_1s": not worker.is_alive(),
            "result": result,
        }


def check_untrusted_history_can_delete_outside_workspace() -> dict:
    with tempfile.TemporaryDirectory(prefix="fop-audit-history-", dir=Path(__file__).parent) as tmp:
        root = Path(tmp).resolve()
        workspace = root / "workspace"
        outside_victim = root / "outside-victim"
        workspace.mkdir()
        outside_victim.mkdir()
        (outside_victim / "sentinel.txt").write_text("do not delete", encoding="utf-8")

        history = [
            {
                "action": "create",
                "src": str(workspace / "claimed-source.zip"),
                "dst": str(outside_victim),
            }
        ]
        (workspace / ".organizer_history.json").write_text(
            json.dumps(history), encoding="utf-8"
        )

        api = OrganizerAPI()
        api._current_workspace = str(workspace)
        api._load_history(str(workspace))
        result = api.undo_last_operation()

        return {
            "victim_was_inside_temp_root": outside_victim.is_relative_to(root),
            "victim_was_outside_workspace": not outside_victim.is_relative_to(workspace),
            "victim_exists_after_undo": outside_victim.exists(),
            "api_result": result,
        }


def check_custom_rule_can_escape_workspace() -> dict:
    with tempfile.TemporaryDirectory(prefix="fop-audit-rule-", dir=Path(__file__).parent) as tmp:
        root = Path(tmp).resolve()
        workspace = root / "workspace"
        escaped = root / "escaped"
        workspace.mkdir()
        source = workspace / "secret-report.txt"
        source.write_text("fixture", encoding="utf-8")

        api = OrganizerAPI()
        api._current_workspace = str(workspace)
        result = api.smart_categorize(
            str(workspace),
            False,
            [{"folder": "../escaped", "extensions": [], "keywords": ["secret"]}],
        )

        escaped_file = escaped / source.name
        return {
            "escaped_target_is_outside_workspace": not escaped.is_relative_to(workspace),
            "source_still_exists": source.exists(),
            "escaped_file_exists": escaped_file.exists(),
            "api_result": result,
        }


def check_flatten_can_overwrite_second_collision() -> dict:
    with tempfile.TemporaryDirectory(prefix="fop-audit-flatten-", dir=Path(__file__).parent) as tmp:
        workspace = Path(tmp).resolve()
        nested = workspace / "nested"
        nested.mkdir()

        (workspace / "alpha.txt").write_text("top-alpha", encoding="utf-8")
        (workspace / "beta.txt").write_text("top-beta", encoding="utf-8")
        collision = workspace / "beta_1.txt"
        collision.write_text("sentinel-must-survive", encoding="utf-8")
        (nested / "alpha.txt").write_text("nested-alpha", encoding="utf-8")
        (nested / "beta.txt").write_text("nested-beta", encoding="utf-8")

        api = OrganizerAPI()
        api._current_workspace = str(workspace)
        result = api.flatten_workspace(str(workspace), False)

        return {
            "api_result": result,
            "collision_content_after": collision.read_text(encoding="utf-8"),
            "nested_beta_exists_after": (nested / "beta.txt").exists(),
        }


def check_media_fallback_name_can_be_overwritten() -> dict:
    with tempfile.TemporaryDirectory(prefix="fop-audit-media-", dir=Path(__file__).parent) as tmp:
        workspace = Path(tmp).resolve()
        source = workspace / "photo.png"
        Image.new("RGB", (4, 4), (100, 50, 20)).save(source)

        primary_output = workspace / "photo_optimized.png"
        primary_output.write_bytes(b"existing-primary-output")
        fallback_output = workspace / f"photo_optimized_{int(source.stat().st_mtime)}.png"
        fallback_output.write_bytes(b"sentinel-must-survive")

        destination, error = media_service.optimize_image(source, 85, lambda _: None)
        return {
            "returned_destination": destination,
            "error": error,
            "fallback_was_preexisting": True,
            "fallback_content_was_overwritten": fallback_output.read_bytes()
            != b"sentinel-must-survive",
        }


def check_extension_failure_loses_partial_history() -> dict:
    with tempfile.TemporaryDirectory(prefix="fop-audit-extension-", dir=Path(__file__).parent) as tmp:
        workspace = Path(tmp).resolve()
        (workspace / "a.old").write_text("first", encoding="utf-8")
        (workspace / "b.old").write_text("second", encoding="utf-8")
        (workspace / "b.new").write_text("preexisting", encoding="utf-8")

        api = OrganizerAPI()
        api._current_workspace = str(workspace)
        result = api.change_extensions(str(workspace), ".old", ".new", False)
        return {
            "api_result": result,
            "first_source_exists": (workspace / "a.old").exists(),
            "first_destination_exists": (workspace / "a.new").exists(),
            "history_entries_retained": len(api._history),
            "history_file_exists": (workspace / ".organizer_history.json").exists(),
        }


def check_extended_drive_root_guard() -> dict:
    candidates = ["\\\\?\\C:\\", "\\\\.\\C:\\"]
    return {candidate: is_system_critical_dir(candidate) for candidate in candidates}


def main() -> None:
    results = {
        "double_lock_deadlock": check_double_lock_deadlock(),
        "untrusted_history_external_delete": check_untrusted_history_can_delete_outside_workspace(),
        "custom_rule_workspace_escape": check_custom_rule_can_escape_workspace(),
        "flatten_collision_overwrite": check_flatten_can_overwrite_second_collision(),
        "media_fallback_overwrite": check_media_fallback_name_can_be_overwritten(),
        "extension_partial_failure_history": check_extension_failure_loses_partial_history(),
        "extended_drive_root_guard": check_extended_drive_root_guard(),
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
