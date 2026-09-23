import unittest
import shutil
import json
import os
from pathlib import Path
from unittest.mock import patch

from organizer import OrganizerAPI, start_app
from services import operation_registry, path_guard, journal_service


class TestContractAndIsolation(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(__file__).parent / "tmp_m3_test_workspace"
        if self.test_root.exists():
            shutil.rmtree(self.test_root, ignore_errors=True)
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.api = OrganizerAPI()

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root, ignore_errors=True)

    def test_sequential_rename_folders_mode_renames_only_folders(self):
        """FOP-AUD-006: sequential_rename with mode='folders' must rename only directories,
        leaving files untouched, and generate durable undo history."""
        # Setup: 2 files and 2 folders
        file1 = self.test_root / "document_alpha.txt"
        file2 = self.test_root / "document_beta.txt"
        file1.write_text("file1-content", encoding="utf-8")
        file2.write_text("file2-content", encoding="utf-8")

        folder1 = self.test_root / "Folder_Old_1"
        folder2 = self.test_root / "Folder_Old_2"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "subfile.txt").write_text("sub-content", encoding="utf-8")

        # Execute folders rename
        res = self.api.sequential_rename(
            str(self.test_root),
            prefix="ProjectFolder_",
            mode="folders",
            sort_mode="name",
            dry_run=False,
        )

        self.assertTrue(res.get("success"), f"Operation failed: {res}")

        # Folders must be renamed
        renamed_dirs = [p.name for p in self.test_root.iterdir() if p.is_dir()]
        self.assertEqual(len(renamed_dirs), 2)
        self.assertTrue(all(d.startswith("ProjectFolder_") for d in renamed_dirs))

        # Files must NOT be renamed
        self.assertTrue(file1.exists(), "File 1 was unexpectedly renamed or deleted")
        self.assertTrue(file2.exists(), "File 2 was unexpectedly renamed or deleted")
        self.assertEqual(file1.read_text(encoding="utf-8"), "file1-content")

        # History exists and can be queried
        hist = self.api.check_history(str(self.test_root))
        self.assertTrue(hist["has_history"])

        # Undo must restore original folder names
        undo_res = self.api.undo_last_operation()
        self.assertTrue(undo_res.get("success"), f"Undo failed: {undo_res}")
        self.assertTrue(folder1.exists(), "Folder 1 was not restored by undo")
        self.assertTrue(folder2.exists(), "Folder 2 was not restored by undo")
        self.assertTrue((folder1 / "subfile.txt").exists(), "Subfile inside restored folder is missing")

    def test_sequential_rename_files_mode_renames_only_files(self):
        """sequential_rename with mode='files' must rename only files, leaving directories untouched."""
        file1 = self.test_root / "notes_alpha.txt"
        file2 = self.test_root / "notes_beta.txt"
        file1.write_text("alpha", encoding="utf-8")
        file2.write_text("beta", encoding="utf-8")

        folder1 = self.test_root / "KeepFolder"
        folder1.mkdir()

        res = self.api.sequential_rename(
            str(self.test_root),
            prefix="ArchiveItem_",
            mode="files",
            sort_mode="name",
            dry_run=False,
        )

        self.assertTrue(res.get("success"), f"Operation failed: {res}")
        self.assertTrue(folder1.exists(), "Folder was unexpectedly modified during file rename")

        renamed_files = [p.name for p in self.test_root.iterdir() if p.is_file() and p.name != ".organizer_history.json"]
        self.assertEqual(len(renamed_files), 2)
        self.assertTrue(all(f.startswith("ArchiveItem_") for f in renamed_files))

    def test_sequential_rename_dry_run_preview_does_not_mutate(self):
        """Dry-run preview returns planned rename items without touching files or creating history."""
        file1 = self.test_root / "test1.txt"
        file1.write_text("test", encoding="utf-8")

        res = self.api.sequential_rename(
            str(self.test_root),
            prefix="Preview_",
            mode="files",
            dry_run=True,
        )

        self.assertTrue(res.get("success"))
        self.assertIn("Simulation:", res.get("message", ""))
        self.assertEqual(len(res.get("items", [])), 1)
        self.assertTrue(file1.exists(), "File was renamed during dry run")
        self.assertFalse((self.test_root / "Preview_1.txt").exists())

        # No history on disk
        hist = self.api.check_history(str(self.test_root))
        self.assertFalse(hist["has_history"])

    def test_workspace_rules_isolation_no_leakage(self):
        """FOP-AUD-016: Switching from workspace with custom rules to one without rules
        must never preserve or leak rules from the previous workspace."""
        ws_a = self.test_root / "workspace_a"
        ws_b = self.test_root / "workspace_b"
        ws_a.mkdir()
        ws_b.mkdir()

        rules_a = [
            {"folder": "Documents", "extensions": [".pdf", ".docx"], "keywords": ["invoice"]},
            {"folder": "Photos", "extensions": [".jpg", ".png"], "keywords": ["vacation"]},
        ]

        save_res = self.api.save_rules(str(ws_a), rules_a)
        self.assertTrue(save_res.get("success"))

        # Workspace A returns the saved rules
        load_a = self.api.load_rules(str(ws_a))
        self.assertTrue(load_a.get("success"))
        self.assertEqual(len(load_a.get("rules", [])), 2)

        # Workspace B (no rules file) must strictly return an empty list
        load_b = self.api.load_rules(str(ws_b))
        self.assertTrue(load_b.get("success"))
        self.assertEqual(load_b.get("rules"), [])

    def test_check_history_reflects_authoritative_disk_state(self):
        """check_history must return True only when a valid journal exists on disk,
        and False after undo or when clean."""
        # Clean workspace
        res = self.api.check_history(str(self.test_root))
        self.assertFalse(res["has_history"])

        # Perform a rename operation
        f = self.test_root / "item.txt"
        f.write_text("hello", encoding="utf-8")
        self.api.sequential_rename(str(self.test_root), "Doc_")

        res_after_op = self.api.check_history(str(self.test_root))
        self.assertTrue(res_after_op["has_history"])

        # After undo
        self.api.undo_last_operation()
        res_after_undo = self.api.check_history(str(self.test_root))
        self.assertFalse(res_after_undo["has_history"])

    def test_get_operation_registry_manifest(self):
        """FOP-AUD-009: Manifest returns complete capability lists matching operation specs."""
        res = self.api.get_operation_registry()
        self.assertTrue(res.get("success"))
        registry = res.get("registry", {})

        self.assertIn("operations", registry)
        self.assertIn("undoable_ops", registry)
        self.assertIn("destructive_ops", registry)
        self.assertIn("confirmation_required_ops", registry)
        self.assertIn("recursive_capable_ops", registry)
        self.assertIn("dry_run_capable_ops", registry)

        # 27 registered operations
        self.assertEqual(len(registry["operations"]), 27)

        # Destructive ops must require confirmation
        for op in registry["destructive_ops"]:
            self.assertIn(op, registry["confirmation_required_ops"])

        # Media batch operations must require confirmation and support dry-run
        media_batch_ops = ["batch_convert_mp3_to_wav", "batch_compress_pdf", "batch_optimize_images"]
        for op in media_batch_ops:
            self.assertIn(op, registry["confirmation_required_ops"])
            self.assertIn(op, registry["dry_run_capable_ops"])
            self.assertIn(op, registry["undoable_ops"])

    def test_start_app_fails_closed_when_bundle_missing(self):
        """FOP-AUD-011: start_app must fail closed with FileNotFoundError if dist/index.html
        is missing, unless FOP_DEV_SERVER=1 is explicitly set."""
        with patch("organizer.get_base_dir", return_value=self.test_root):
            # Ensure env var is absent
            env_clean = os.environ.copy()
            env_clean.pop("FOP_DEV_SERVER", None)

            with patch.dict(os.environ, env_clean, clear=True):
                with self.assertRaises(FileNotFoundError) as ctx:
                    start_app()
                self.assertIn("Production UI bundle not found", str(ctx.exception))
                self.assertIn("FOP_DEV_SERVER=1", str(ctx.exception))

            # When FOP_DEV_SERVER=1 is explicitly enabled
            with patch.dict(os.environ, {"FOP_DEV_SERVER": "1"}):
                with patch("organizer.webview.create_window") as mock_create_window, \
                     patch("organizer.webview.start") as mock_start:
                    start_app()
                    mock_create_window.assert_called_once()
                    args, kwargs = mock_create_window.call_args
                    self.assertEqual(args[1], "http://localhost:5173")

    def test_ui_html_strict_csp_and_no_remote_dependencies(self):
        """FOP-AUD-010: Both source index.html and dist/index.html must have strict CSP
        and zero external font / script links."""
        base_dir = Path(__file__).parent.parent
        src_html = (base_dir / "ui" / "index.html").read_text(encoding="utf-8")
        dist_html = (base_dir / "ui" / "dist" / "index.html").read_text(encoding="utf-8")

        for html, name in [(src_html, "ui/index.html"), (dist_html, "ui/dist/index.html")]:
            # No Google Fonts
            self.assertNotIn("fonts.googleapis.com", html, f"{name} contains Google Fonts link")
            self.assertNotIn("fonts.gstatic.com", html, f"{name} contains Google Fonts preconnect")

            # No http or https links
            self.assertNotIn("http://", html, f"{name} contains remote http URL")
            self.assertNotIn("https://", html, f"{name} contains remote https URL")

            # Must have strict Content-Security-Policy
            self.assertIn("Content-Security-Policy", html, f"{name} is missing CSP meta tag")
            self.assertIn("default-src 'self'", html, f"{name} CSP does not restrict default-src")
            self.assertIn("connect-src 'self'", html, f"{name} CSP does not restrict connect-src")

    def test_all_mutating_operations_have_callable_api_bridge_methods(self):
        """FOP-AUD-009: Every mutating operation in the registry has a corresponding
        callable method on the OrganizerAPI instance."""
        manifest = operation_registry.get_frontend_manifest()
        api = OrganizerAPI()

        for op_name in manifest["confirmation_required_ops"]:
            # Check direct method or known bridge alias
            has_method = hasattr(api, op_name) or (op_name == "batch_optimize_images" and hasattr(api, "optimize_images"))
            self.assertTrue(has_method, f"OrganizerAPI lacks bridge method for operation: {op_name}")
            method = getattr(api, op_name, None) or getattr(api, "optimize_images", None)
            self.assertTrue(callable(method), f"OrganizerAPI.{op_name} is not callable")


if __name__ == "__main__":
    unittest.main()
