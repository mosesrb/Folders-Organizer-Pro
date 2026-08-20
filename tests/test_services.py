import unittest
import os
import shutil
import time
import zipfile
from pathlib import Path
from services import file_service, organizer_service, duplicate_service, automation_service

class TestOrganizerServices(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace")
        self.test_dir.mkdir(exist_ok=True)
        (self.test_dir / "file1.txt").write_text("content1")
        (self.test_dir / "file2.txt").write_text("content2")
        (self.test_dir / "subdir").mkdir()
        (self.test_dir / "subdir" / "nested.txt").write_text("nested")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_analyze_workspace(self):
        category_map = {'Documents': ['.txt']}
        stats = file_service.scan_analyze(str(self.test_dir), category_map)
        self.assertEqual(len(stats["top_files"]), 3)
        self.assertEqual(stats["categories"]["Documents"],
                         (self.test_dir / "file1.txt").stat().st_size +
                         (self.test_dir / "file2.txt").stat().st_size +
                         (self.test_dir / "subdir" / "nested.txt").stat().st_size)

    def test_delete_empty_folders_cascades_nested_chain_in_one_pass(self):
        """A/B/C all empty must fully collapse in a single run, not require
        one run per nesting level."""
        (self.test_dir / "A" / "B" / "C").mkdir(parents=True)
        removed, total = automation_service.delete_empty_folders(str(self.test_dir), False, lambda x: None)
        self.assertFalse((self.test_dir / "A").exists())
        self.assertEqual(total, 3)
        # Non-empty subdir from setUp must survive untouched.
        self.assertTrue((self.test_dir / "subdir" / "nested.txt").exists())

    def test_flatten_workspace(self):
        history, count = organizer_service.flatten_workspace(str(self.test_dir), False, lambda x: None)
        self.assertEqual(count, 1) # only nested.txt should be moved
        self.assertTrue((self.test_dir / "nested.txt").exists())
        self.assertFalse((self.test_dir / "subdir").exists())

    def test_custom_rule_keyword_overrides_builtin(self):
        """A custom rule using a keyword that a built-in category also uses
        (e.g. 'invoice', which the built-in 'Work' category claims) must win
        — otherwise a user's custom rule silently does nothing whenever it
        overlaps a default."""
        (self.test_dir / "invoice_2024.pdf").write_text("x")
        history, count = organizer_service.smart_categorize(
            str(self.test_dir), False,
            [{"folder": "Client Docs", "extensions": [], "keywords": ["invoice"]}],
            lambda x: None
        )
        self.assertTrue((self.test_dir / "Client Docs" / "invoice_2024.pdf").exists())
        self.assertFalse((self.test_dir / "Work").exists())

    def test_regex_rename_empty_replacement_strips_match(self):
        """Empty replacement is a valid regex substitution ('delete this
        match'). It must not be silently reinterpreted as 'regex mode is
        off' just because the string is falsy."""
        (self.test_dir / "IMG_1234_raw.jpg").write_text("x")
        history, count = organizer_service.sequential_rename(
            str(self.test_dir), prefix="", mode="files", sort_mode="name",
            dry_run=True, filter_str="_raw", use_regex=True, progress_callback=lambda x: None
        )
        dsts = [h["dst"] for h in history]
        self.assertTrue(any(d.endswith("IMG_1234.jpg") for d in dsts))

    def test_regex_rename_without_pattern_raises_clear_error(self):
        """Regex Mode with an empty search pattern must not silently run —
        re.sub('', ...) matches between every character and mangles names."""
        (self.test_dir / "photo1.jpg").write_text("x")
        with self.assertRaises(ValueError):
            organizer_service.sequential_rename(
                str(self.test_dir), prefix="X", mode="files", sort_mode="name",
                dry_run=True, filter_str="", use_regex=True, progress_callback=lambda x: None
            )

    def test_sequential_rename(self):
        history, count = organizer_service.sequential_rename(str(self.test_dir), "new_", "files", "name", False, "", False, lambda x: None)
        self.assertEqual(count, 2)
        self.assertTrue((self.test_dir / "new_01.txt").exists())
        self.assertTrue((self.test_dir / "new_02.txt").exists())

    def test_sequential_rename_dry_run_does_not_move_and_returns_items(self):
        preview, count = organizer_service.sequential_rename(str(self.test_dir), "new_", "files", "name", True, "", False, lambda x: None)
        self.assertEqual(count, 2)
        self.assertEqual(len(preview), 2)
        self.assertTrue((self.test_dir / "file1.txt").exists())  # nothing actually moved
        self.assertTrue(all("src" in item and "dst" in item for item in preview))

    def test_flatten_workspace_dry_run_returns_items(self):
        preview, count = organizer_service.flatten_workspace(str(self.test_dir), True, lambda x: None)
        self.assertEqual(count, 1)
        self.assertEqual(preview, [{"action": "move", "src": str(self.test_dir / "subdir" / "nested.txt"), "dst": str(self.test_dir / "nested.txt")}])
        self.assertTrue((self.test_dir / "subdir").exists())  # nothing actually moved


class TestSystemCriticalDirGuard(unittest.TestCase):
    """Regression tests for is_system_critical_dir — the single function the
    entire app's file-safety story depends on. Previously had zero test
    coverage. Runs correctly on any host OS (not just Windows) because the
    function uses PureWindowsPath internally rather than platform-native
    path parsing.
    """

    def setUp(self):
        # organizer.py imports pywebview at module scope; importing it here
        # (rather than at file scope) keeps this test file usable even in
        # environments where pywebview's native deps aren't fully set up.
        import organizer
        self.is_system_critical_dir = organizer.is_system_critical_dir

    def test_blocks_windows_system_dirs(self):
        blocked = [
            r"C:\Windows\System32",
            r"C:\Windows\SysWOW64",
            r"C:\Program Files\SomeApp",
            r"C:\Program Files (x86)\SomeApp",
            r"C:\ProgramData\Config",
            r"C:\Users\bob\AppData\Roaming",
            r"C:\System Volume Information",
            r"C:\Recovery",
            r"C:\$Recycle.Bin",
            r"C:\Boot",
            r"C:\EFI",
        ]
        for path in blocked:
            with self.subTest(path=path):
                self.assertTrue(self.is_system_critical_dir(path), f"{path} should be blocked")

    def test_allows_ordinary_user_dirs(self):
        allowed = [
            r"C:\Users\bob\Documents",
            r"C:\Users\bob\Downloads",
            r"D:\Projects\my-app",
            r"E:\Photos\2024",
        ]
        for path in allowed:
            with self.subTest(path=path):
                self.assertFalse(self.is_system_critical_dir(path), f"{path} should NOT be blocked")

    def test_blocks_bare_drive_roots(self):
        for path in (r"C:\ ".strip(), "C:/", r"D:\ ".strip()):
            with self.subTest(path=path):
                self.assertTrue(self.is_system_critical_dir(path), f"{path} should be blocked as a drive root")

    def test_matches_regardless_of_slash_style(self):
        # Windows accepts both slash styles; the guard must catch both.
        self.assertTrue(self.is_system_critical_dir("C:/Windows/System32"))
        self.assertTrue(self.is_system_critical_dir(r"C:\Windows/System32"))

    def test_case_insensitive(self):
        self.assertTrue(self.is_system_critical_dir(r"c:\WINDOWS\system32"))


class TestDuplicateService(unittest.TestCase):
    """Coverage for duplicate detection/deletion — previously untested."""

    def setUp(self):
        self.test_dir = Path("test_dupes_workspace")
        self.test_dir.mkdir(exist_ok=True)
        (self.test_dir / "original.txt").write_text("same content")
        time.sleep(0.01)
        (self.test_dir / "copy.txt").write_text("same content")
        (self.test_dir / "unique.txt").write_text("different content")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_finds_duplicate_groups_by_content(self):
        groups = duplicate_service.find_duplicates(str(self.test_dir), lambda x: None)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_keep_by_oldest_is_deterministic(self):
        groups = duplicate_service.find_duplicates(str(self.test_dir), lambda x: None, keep_by="oldest")
        kept = Path(groups[0][0])
        self.assertEqual(kept.name, "original.txt")

    def test_keep_by_newest_is_deterministic(self):
        groups = duplicate_service.find_duplicates(str(self.test_dir), lambda x: None, keep_by="newest")
        kept = Path(groups[0][0])
        self.assertEqual(kept.name, "copy.txt")

    def test_delete_duplicates_keeps_index_zero(self):
        groups = duplicate_service.find_duplicates(str(self.test_dir), lambda x: None, keep_by="oldest")
        deleted_count = duplicate_service.delete_duplicates(groups, lambda x: None, keep_by="oldest")
        self.assertEqual(deleted_count, 1)
        self.assertTrue((self.test_dir / "original.txt").exists())
        self.assertFalse((self.test_dir / "copy.txt").exists())


class TestArchiveExtractionSafety(unittest.TestCase):
    """Regression tests for zip-slip / path-traversal protection on archive
    extraction — previously unguarded against malicious archive entries."""

    def setUp(self):
        self.out_dir = Path("test_extract_out")
        self.out_dir.mkdir(exist_ok=True)

    def tearDown(self):
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        parent_leak = Path("leaked.txt")
        if parent_leak.exists():
            parent_leak.unlink()

    def test_rejects_path_traversal_member(self):
        malicious_zip = Path("malicious.zip")
        with zipfile.ZipFile(malicious_zip, 'w') as zf:
            zf.writestr("../leaked.txt", "should never land outside out_dir")
        try:
            with self.assertRaises(automation_service.ArchiveSecurityError):
                automation_service._safe_extract_zip(str(malicious_zip), self.out_dir)
            self.assertFalse(Path("leaked.txt").exists())
        finally:
            malicious_zip.unlink(missing_ok=True)

    def test_allows_normal_zip(self):
        good_zip = Path("good.zip")
        with zipfile.ZipFile(good_zip, 'w') as zf:
            zf.writestr("hello.txt", "hello world")
        try:
            automation_service._safe_extract_zip(str(good_zip), self.out_dir)
            self.assertTrue((self.out_dir / "hello.txt").exists())
        finally:
            good_zip.unlink(missing_ok=True)

    def test_rejects_absolute_path_member(self):
        with self.assertRaises(automation_service.ArchiveSecurityError):
            automation_service._assert_member_is_safe("/etc/passwd", self.out_dir)
        with self.assertRaises(automation_service.ArchiveSecurityError):
            automation_service._assert_member_is_safe(r"C:\Windows\evil.dll", self.out_dir)

    def test_allows_root_directory_entries(self):
        """A bare '.' entry just means 'the extraction root itself' and is
        harmless — Python's tarfile strips the trailing slash from a
        directory entry, so the extremely standard `tar -C dir -cf out.tar .`
        produces a literal '.' member. This must not reject the whole
        archive (previously it did)."""
        for name in ('.', '', './'):
            target = automation_service._assert_member_is_safe(name, self.out_dir)
            self.assertEqual(target.resolve(), self.out_dir.resolve())

    def test_still_rejects_bare_parent_traversal(self):
        with self.assertRaises(automation_service.ArchiveSecurityError):
            automation_service._assert_member_is_safe("..", self.out_dir)

    def test_extracts_real_standard_tar_with_root_entry(self):
        """End-to-end: a tar built the standard way (tar -C dir -cf out.tar .)
        includes a '.' root entry and must extract successfully."""
        import tarfile
        staging = Path("test_tar_staging")
        staging.mkdir(exist_ok=True)
        try:
            (staging / "doc.txt").write_text("hello")
            tar_path = Path("standard_style.tar")
            with tarfile.open(tar_path, "w") as tf:
                tf.add(str(staging), arcname=".")
            try:
                automation_service._safe_extract_tar(str(tar_path), self.out_dir)
                self.assertTrue((self.out_dir / "doc.txt").exists())
            finally:
                tar_path.unlink(missing_ok=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)


class TestRecursiveToggle(unittest.TestCase):
    """Regression tests for the new 'include subfolders' option — previously
    cleanup_old_files, archive_large_files, advanced_regex_rename, and
    batch_unzip silently only ever processed the top level with no way to
    opt into recursive processing.
    """

    def setUp(self):
        self.test_dir = Path("test_recursive_workspace")
        self.test_dir.mkdir(exist_ok=True)
        (self.test_dir / "top.txt").write_text("top")
        sub = self.test_dir / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_regex_rename_top_level_only_by_default(self):
        history, count = automation_service.advanced_regex_rename(
            str(self.test_dir), r"(.+)\.txt", r"\1_renamed.txt", True, lambda x: None
        )
        self.assertEqual(count, 1)  # only top.txt

    def test_regex_rename_recursive_finds_nested(self):
        history, count = automation_service.advanced_regex_rename(
            str(self.test_dir), r"(.+)\.txt", r"\1_renamed.txt", True, lambda x: None, recursive=True
        )
        self.assertEqual(count, 2)  # top.txt + sub/nested.txt

    def test_archive_large_files_recursive_finds_nested(self):
        history, count = automation_service.archive_large_files(
            str(self.test_dir), 0.0000001, True, lambda x: None, recursive=True
        )
        self.assertEqual(count, 2)

    def test_archive_large_files_top_level_only_by_default(self):
        history, count = automation_service.archive_large_files(
            str(self.test_dir), 0.0000001, True, lambda x: None
        )
        self.assertEqual(count, 1)


class TestBatchZipFolders(unittest.TestCase):
    """Tests for the new Batch Folder Zipper (zip N folders at once,
    optionally with a custom extension, optionally deleting the source)."""

    def setUp(self):
        self.test_dir = Path("test_batchzip_workspace")
        self.test_dir.mkdir(exist_ok=True)
        for name, files in [("Comics", ["p1.jpg", "p2.jpg"]), ("Notes", ["a.txt"])]:
            folder = self.test_dir / name
            folder.mkdir()
            for f in files:
                (folder / f).write_text("x")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_additive_backup_rejects_dest_inside_src(self):
        """Destination inside source would nest a fresh copy of itself into
        itself on every re-run (verified live: 3 runs produced
        backup/backup/backup/... with no convergence) — must be blocked
        up front instead of silently ballooning disk usage."""
        src = self.test_dir / "project"
        src.mkdir()
        (src / "a.txt").write_text("x")
        dest = src / "backup"
        with self.assertRaises(ValueError):
            automation_service.additive_backup(str(src), str(dest), False, lambda x: None)
        # Legitimate sibling destination must still work.
        sibling_dest = self.test_dir / "external_backup"
        history, count = automation_service.additive_backup(str(src), str(sibling_dest), False, lambda x: None)
        self.assertEqual(count, 1)

    def test_zips_each_selected_folder_with_custom_extension(self):
        history, count, errors = automation_service.batch_zip_folders(
            str(self.test_dir), ["Comics", "Notes"], ".cbz", False, False, lambda x: None
        )
        self.assertEqual(errors, [])
        self.assertTrue((self.test_dir / "Comics.cbz").exists())
        self.assertTrue((self.test_dir / "Notes.cbz").exists())
        # Original folders survive when delete_originals is False.
        self.assertTrue((self.test_dir / "Comics").exists())
        with zipfile.ZipFile(self.test_dir / "Comics.cbz") as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith("Comics/") for n in names))

    def test_dry_run_touches_nothing(self):
        history, count, errors = automation_service.batch_zip_folders(
            str(self.test_dir), ["Comics"], ".zip", True, True, lambda x: None
        )
        self.assertFalse((self.test_dir / "Comics.zip").exists())
        self.assertTrue((self.test_dir / "Comics").exists())
        self.assertEqual(len(history), 2)  # create + delete entries, simulated

    def test_delete_originals_removes_source_after_success(self):
        automation_service.batch_zip_folders(
            str(self.test_dir), ["Notes"], ".zip", True, False, lambda x: None
        )
        self.assertTrue((self.test_dir / "Notes.zip").exists())
        self.assertFalse((self.test_dir / "Notes").exists())

    def test_skips_when_archive_name_collides(self):
        (self.test_dir / "Comics.zip").write_text("existing file")
        history, count, errors = automation_service.batch_zip_folders(
            str(self.test_dir), ["Comics"], ".zip", False, False, lambda x: None
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("already exists", errors[0])
        # The pre-existing file must not have been overwritten.
        self.assertEqual((self.test_dir / "Comics.zip").read_text(), "existing file")


if __name__ == '__main__':
    unittest.main()
