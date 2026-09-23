"""Tests for services.path_guard."""

import os
import tempfile
import unittest
from pathlib import Path

from services.path_guard import (
    PathSecurityError,
    canonicalize_path,
    is_bare_root,
    is_safe_relative_subpath,
    is_system_critical,
    sanitize_folder_name,
    validate_destination,
    validate_source,
    validate_workspace,
)


class TestPathGuard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix="fop-test-guard-")
        self.workspace = Path(self.temp_dir.name).resolve()
        (self.workspace / "file1.txt").write_text("hello", encoding="utf-8")
        self.sub_dir = self.workspace / "sub"
        self.sub_dir.mkdir()
        (self.sub_dir / "nested.txt").write_text("world", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_system_critical_extended_roots(self):
        """FOP-AUD-007: Extended Windows drive roots and device paths must be blocked."""
        self.assertTrue(is_system_critical("\\\\?\\C:\\"))
        self.assertTrue(is_system_critical("\\\\.\\C:\\"))
        self.assertTrue(is_system_critical("\\\\?\\C:"))
        self.assertTrue(is_system_critical("\\\\.\\C:"))
        self.assertTrue(is_system_critical("C:\\"))
        self.assertTrue(is_system_critical("C:"))
        self.assertTrue(is_system_critical("D:\\"))
        self.assertTrue(is_system_critical("\\\\server\\share"))
        self.assertTrue(is_system_critical("\\\\server\\share\\"))
        self.assertTrue(is_system_critical("\\\\?\\UNC\\server\\share"))
        self.assertTrue(is_system_critical("\\\\?\\UNC\\server\\share\\"))

    def test_is_system_critical_known_directories(self):
        """Standard Windows critical directories must be recognized and blocked."""
        self.assertTrue(is_system_critical(r"C:\Windows"))
        self.assertTrue(is_system_critical(r"C:\Windows\System32"))
        self.assertTrue(is_system_critical(r"C:\Program Files"))
        self.assertTrue(is_system_critical(r"C:\Program Files (x86)"))
        self.assertTrue(is_system_critical(r"C:\ProgramData"))
        self.assertTrue(is_system_critical(r"C:\Users\test\AppData\Local"))
        self.assertTrue(is_system_critical(r"C:\System Volume Information"))
        self.assertTrue(is_system_critical(r"C:\$Recycle.Bin"))
        self.assertTrue(is_system_critical(r"\\?\C:\Windows"))

    def test_is_system_critical_safe_workspace(self):
        """A normal user workspace folder must not be reported as critical."""
        self.assertFalse(is_system_critical(self.workspace))
        self.assertFalse(is_system_critical(self.sub_dir))

    def test_canonicalize_path_prohibits_dangerous_tokens(self):
        with self.assertRaises(PathSecurityError):
            canonicalize_path(None)
        with self.assertRaises(PathSecurityError):
            canonicalize_path("")
        with self.assertRaises(PathSecurityError):
            canonicalize_path("C:\\foo\0bar")
        with self.assertRaises(PathSecurityError):
            canonicalize_path(r"\\.\PhysicalDrive0")
        with self.assertRaises(PathSecurityError):
            canonicalize_path("C:\\foo\\bar.txt:hidden_stream")

    def test_validate_workspace(self):
        canon = validate_workspace(self.workspace)
        self.assertEqual(canon, self.workspace)

        # File instead of directory
        with self.assertRaises(PathSecurityError):
            validate_workspace(self.workspace / "file1.txt")

        # Nonexistent path
        with self.assertRaises(PathSecurityError):
            validate_workspace(self.workspace / "does_not_exist")

        # Bare root
        with self.assertRaises(PathSecurityError):
            validate_workspace("C:\\")
        with self.assertRaises(PathSecurityError):
            validate_workspace("\\\\?\\C:\\")

    def test_validate_source(self):
        src = validate_source(self.workspace / "file1.txt", self.workspace)
        self.assertEqual(src, self.workspace / "file1.txt")

        nested = validate_source(self.sub_dir / "nested.txt", self.workspace)
        self.assertEqual(nested, self.sub_dir / "nested.txt")

        # Workspace itself cannot be a source file
        with self.assertRaises(PathSecurityError):
            validate_source(self.workspace, self.workspace)

        # Outside victim
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as other_dir:
            other_file = Path(other_dir) / "other.txt"
            other_file.write_text("external", encoding="utf-8")
            with self.assertRaises(PathSecurityError):
                validate_source(other_file, self.workspace)

    def test_validate_destination_containment(self):
        # Normal relative destination
        dest = validate_destination("output.txt", self.workspace)
        self.assertEqual(dest, self.workspace / "output.txt")

        # Nested relative destination
        dest_nested = validate_destination("sub/output.txt", self.workspace)
        self.assertEqual(dest_nested, self.workspace / "sub" / "output.txt")

        # FOP-AUD-002: Traversal attempts
        with self.assertRaises(PathSecurityError):
            validate_destination("../escaped.txt", self.workspace)
        with self.assertRaises(PathSecurityError):
            validate_destination("sub/../../escaped.txt", self.workspace)

        # Absolute destination outside workspace
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as other_dir:
            with self.assertRaises(PathSecurityError):
                validate_destination(Path(other_dir) / "victim.txt", self.workspace)

        # Reserved Windows device names
        with self.assertRaises(PathSecurityError):
            validate_destination("CON.txt", self.workspace)
        with self.assertRaises(PathSecurityError):
            validate_destination("sub/NUL.png", self.workspace)

        # Illegal characters
        with self.assertRaises(PathSecurityError):
            validate_destination("invalid<name>.txt", self.workspace)

    def test_validate_destination_allow_sibling(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as parent_tmp:
            w = Path(parent_tmp) / "source_workspace"
            w.mkdir()
            (w / "dummy.txt").write_text("x")
            sibling = Path(parent_tmp) / "backup_dest"

            # Sibling allowed for backup
            dest = validate_destination(sibling, w, allow_sibling=True)
            self.assertEqual(dest, sibling.resolve())

            # Destination inside workspace forbidden even with allow_sibling
            inside = w / "internal_backup"
            with self.assertRaises(PathSecurityError):
                validate_destination(inside, w, allow_sibling=True)

    def test_sanitize_folder_name(self):
        self.assertEqual(sanitize_folder_name("Documents"), "Documents")
        self.assertEqual(sanitize_folder_name("Work/Projects"), "Work/Projects")
        self.assertEqual(sanitize_folder_name(r"Work\Projects"), "Work/Projects")

        # FOP-AUD-002: Traversal rejection
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name("../escaped")
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name(r"..\escaped")
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name("/absolute/path")
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name(r"C:\absolute")
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name("CON")
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name("bad:name")
        with self.assertRaises(PathSecurityError):
            sanitize_folder_name("trailing_dot.")

        self.assertTrue(is_safe_relative_subpath("Invoices/2026"))
        self.assertFalse(is_safe_relative_subpath("../escaped"))


if __name__ == '__main__':
    unittest.main()
