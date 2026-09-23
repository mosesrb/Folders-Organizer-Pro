# Copyright (c) 2026 mosesrb (Moses Bharshankar). Licensed under GNU GPL-v3.
"""
tests/test_quota_and_hardening.py
Milestone 4 test suite: Quota & Dependency Hardening
Covers findings:
- FOP-AUD-008: Pillow Vulnerabilities & Image Decompression Bomb Protection
- FOP-AUD-012: Archive Extraction Quotas & Link Protection
- FOP-AUD-015: Duplicate Deletion Provenance & Immediate Re-Validation
"""

import io
import os
import shutil
import tarfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import PIL
from PIL import Image

from organizer import OrganizerAPI
from services import automation_service, duplicate_service, media_service


class TestPillowAndMediaHardening(unittest.TestCase):
    """FOP-AUD-008: Dependency pinning, resource caps, and format whitelisting."""

    def setUp(self):
        self.workspace = Path(__file__).parent / "tmp_m4_media"
        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)

    def test_pillow_pinned_version_and_requirements(self):
        """Pillow is >= 12.3.0 and requirements.txt does not cap below 12."""
        self.assertGreaterEqual(PIL.__version__, "12.3.0")
        req_file = Path(__file__).parent.parent / "requirements.txt"
        self.assertTrue(req_file.exists())
        content = req_file.read_text(encoding="utf-8")
        self.assertIn("Pillow>=12.3.0", content)
        self.assertNotIn("<12.0", content)

    def test_optimize_image_supported_formats_matrix(self):
        """Supported formats (PNG, JPEG, WebP, BMP) optimize cleanly."""
        formats = [
            ("photo.png", "PNG", (20, 20), (100, 150, 200)),
            ("photo.jpg", "JPEG", (20, 20), (200, 100, 50)),
            ("photo.webp", "WEBP", (20, 20), (50, 200, 100)),
            ("photo.bmp", "BMP", (20, 20), (120, 120, 120)),
        ]
        for filename, fmt, size, color in formats:
            src = self.workspace / filename
            img = Image.new("RGB", size, color)
            img.save(src, fmt)

            dst, err = media_service.optimize_image(str(src), quality=80, progress_callback=lambda _: None)
            self.assertIsNone(err, f"Optimization failed for {fmt}: {err}")
            self.assertIsNotNone(dst)
            self.assertTrue(Path(dst).exists())

    def test_optimize_image_rejects_disguised_or_unallowed_format(self):
        """Disguised or unwhitelisted formats fail safely without lingering temp files."""
        bad_file = self.workspace / "fake_photo.png"
        bad_file.write_bytes(b"NOT_A_REAL_IMAGE_HEADER_BYTES_12345")

        dst, err = media_service.optimize_image(str(bad_file), quality=80, progress_callback=lambda _: None)
        self.assertIsNone(dst)
        self.assertIsNotNone(err)
        self.assertIn("fake_photo.png", err)

        # Confirm no temporary files were left in workspace
        tmp_files = list(self.workspace.glob(".tmp_*"))
        self.assertEqual(len(tmp_files), 0)

    def test_optimize_image_rejects_oversized_dimension(self):
        """Images exceeding MAX_IMAGE_DIMENSION (16384) are rejected before processing."""
        oversized_file = self.workspace / "huge_dimension.png"
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        img.save(oversized_file, "PNG")

        original_open = Image.open

        def mock_open(*args, **kwargs):
            opened = original_open(*args, **kwargs)
            opened._size = (20000, 20000)
            return opened

        with patch("PIL.Image.open", side_effect=mock_open):
            dst, err = media_service.optimize_image(str(oversized_file), quality=80, progress_callback=lambda _: None)
            self.assertIsNone(dst)
            self.assertIsNotNone(err)
            self.assertIn("exceed maximum allowed dimension", err)

        self.assertEqual(len(list(self.workspace.glob(".tmp_*"))), 0)

    def test_automation_convert_image_formats_matrix(self):
        """convert_image_formats successfully converts supported formats."""
        src_png = self.workspace / "graphic.png"
        Image.new("RGB", (30, 30), (10, 50, 90)).save(src_png, "PNG")

        history, total = automation_service.convert_image_formats(
            str(self.workspace),
            source_exts=[".png"],
            target_ext=".webp",
            dry_run=False,
            progress_callback=lambda _: None,
        )
        self.assertEqual(total, 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "create")
        dst_path = Path(history[0]["dst"])
        self.assertTrue(dst_path.exists())
        self.assertEqual(dst_path.suffix, ".webp")

    def test_automation_convert_image_formats_rejects_unsupported_target(self):
        """convert_image_formats rejects unwhitelisted target extensions."""
        with self.assertRaises(ValueError) as ctx:
            automation_service.convert_image_formats(
                str(self.workspace),
                source_exts=[".png"],
                target_ext=".exe",
                dry_run=False,
                progress_callback=lambda _: None,
            )
        self.assertIn("Unsupported target image format", str(ctx.exception))

    def test_automation_convert_image_formats_accepts_comma_separated_string(self):
        """convert_image_formats handles comma-separated string of extensions from frontend."""
        src_png = self.workspace / "diagram.png"
        Image.new("RGB", (25, 25), (40, 60, 80)).save(src_png, "PNG")

        history, total = automation_service.convert_image_formats(
            str(self.workspace),
            source_exts=".png, .bmp",
            target_ext=".webp",
            dry_run=False,
            progress_callback=lambda _: None,
        )
        self.assertEqual(total, 1)
        self.assertEqual(len(history), 1)
        self.assertTrue(Path(history[0]["dst"]).exists())

    def test_organizer_api_convert_image_formats_enforces_workspace_validation(self):
        """OrganizerAPI.convert_image_formats rejects system-critical directories."""
        api = OrganizerAPI()
        res = api.convert_image_formats(
            r"\\?\C:\Windows",
            source_exts=[".png"],
            target_ext=".webp",
        )
        self.assertFalse(res.get("success"))
        self.assertIn("system-critical", res.get("error", "").lower())


class TestArchiveQuotasAndLinkProtection(unittest.TestCase):
    """FOP-AUD-012: Archive member, ratio, size, depth, and link protection."""

    def setUp(self):
        self.workspace = Path(__file__).parent / "tmp_m4_archive"
        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.out_dir = self.workspace / "extracted"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)

    def test_zip_member_count_quota(self):
        """Archives with member count exceeding MAX_ARCHIVE_MEMBERS are rejected."""
        zip_path = self.workspace / "many_members.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(10):
                zf.writestr(f"file_{i}.txt", b"x")

        with patch.object(automation_service, "MAX_ARCHIVE_MEMBERS", 5):
            with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
                automation_service._safe_extract_zip(str(zip_path), self.out_dir)
            self.assertIn("member count", str(ctx.exception))

    def test_zip_declared_size_quota(self):
        """Archives with declared uncompressed size exceeding MAX_EXPANDED_BYTES are rejected."""
        zip_path = self.workspace / "declared_bomb.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test_file.txt", b"0123456789ABCDEF")  # 16 bytes

        with patch.object(automation_service, "MAX_EXPANDED_BYTES", 10):
            with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
                automation_service._safe_extract_zip(str(zip_path), self.out_dir)
            self.assertIn("exceeds limit", str(ctx.exception))

    def test_zip_streaming_compression_ratio_quota(self):
        """Streaming decompressor aborts when compression ratio exceeds limit."""
        tracker = automation_service.ArchiveQuotaTracker(
            archive_size=1000,
            max_bytes=100_000_000,
            max_ratio=100
        )
        with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
            tracker.add_bytes(1_500_000)
        self.assertIn("compression ratio", str(ctx.exception))

    def test_zip_symlink_entry_rejected(self):
        """Zip archive containing a symlink entry is blocked."""
        zip_path = self.workspace / "symlink.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zinfo = zipfile.ZipInfo("link_entry")
            zinfo.external_attr = 0o120777 << 16
            zf.writestr(zinfo, b"/etc/passwd")

        with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
            automation_service._safe_extract_zip(str(zip_path), self.out_dir)
        self.assertIn("Symlinks are not allowed", str(ctx.exception))

    def test_tar_member_count_quota(self):
        """Tar archive with member count exceeding quota is blocked."""
        tar_path = self.workspace / "many_members.tar"
        with tarfile.open(tar_path, "w") as tf:
            for i in range(10):
                ti = tarfile.TarInfo(name=f"file_{i}.txt")
                ti.size = 1
                tf.addfile(ti, io.BytesIO(b"a"))

        with patch.object(automation_service, "MAX_ARCHIVE_MEMBERS", 5):
            with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
                automation_service._safe_extract_tar(str(tar_path), self.out_dir)
            self.assertIn("member count", str(ctx.exception))

    def test_tar_special_device_node_rejected(self):
        """Tar archive containing a FIFO or character device node is rejected."""
        tar_path = self.workspace / "fifo.tar"
        with tarfile.open(tar_path, "w") as tf:
            ti = tarfile.TarInfo(name="my_fifo")
            ti.type = tarfile.FIFOTYPE
            tf.addfile(ti)

        with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
            automation_service._safe_extract_tar(str(tar_path), self.out_dir)
        self.assertIn("Special device nodes are not permitted", str(ctx.exception))

    def test_archive_directory_depth_quota(self):
        """Archive entry exceeding maximum nesting depth (20) is rejected."""
        deep_name = "/".join([f"sub_{i}" for i in range(25)]) + "/leaf.txt"
        with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
            automation_service._assert_member_is_safe(deep_name, self.out_dir)
        self.assertIn("nesting depth", str(ctx.exception))

    def test_archive_reserved_device_name_rejected(self):
        """Archive entry containing Windows reserved device names is rejected."""
        reserved_names = ["aux.txt", "con.dat", "sub/prn.log", "com1.bin", "nul"]
        for name in reserved_names:
            with self.assertRaises(automation_service.ArchiveSecurityError) as ctx:
                automation_service._assert_member_is_safe(name, self.out_dir)
            self.assertIn("reserved device name", str(ctx.exception))

    def test_batch_unzip_cleans_up_on_failure(self):
        """batch_unzip removes partial destination folder when extraction is aborted."""
        bad_zip = self.workspace / "poison.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("con.txt", b"payload")

        history, count, errors = automation_service.batch_unzip(
            str(self.workspace),
            dry_run=False,
            progress_callback=lambda _: None,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("poison.zip", errors[0])
        extracted_dir = self.workspace / "poison"
        self.assertFalse(extracted_dir.exists())


class TestDuplicateDeletionProvenanceAndRevalidation(unittest.TestCase):
    """FOP-AUD-015: Immediate re-validation, SHA-256 byte verification, scope checking."""

    def setUp(self):
        self.workspace = Path(__file__).parent / "tmp_m4_dupes"
        self.outside_dir = Path(__file__).parent / "tmp_m4_outside"

        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
        if self.outside_dir.exists():
            shutil.rmtree(self.outside_dir, ignore_errors=True)

        self.workspace.mkdir(parents=True, exist_ok=True)
        self.outside_dir.mkdir(parents=True, exist_ok=True)

        # Create test duplicates in workspace
        self.orig = self.workspace / "original.txt"
        self.copy1 = self.workspace / "copy1.txt"
        self.copy2 = self.workspace / "copy2.txt"

        self.orig.write_text("identical content for testing", encoding="utf-8")
        self.copy1.write_text("identical content for testing", encoding="utf-8")
        self.copy2.write_text("identical content for testing", encoding="utf-8")

        # Set distinct mtimes on files: original is oldest
        old_time = 1000000000.0
        os.utime(self.orig, (old_time, old_time))
        os.utime(self.copy1, (old_time + 100, old_time + 100))
        os.utime(self.copy2, (old_time + 200, old_time + 200))

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
        if self.outside_dir.exists():
            shutil.rmtree(self.outside_dir, ignore_errors=True)

    def test_find_and_delete_nominal(self):
        """find_duplicates uses SHA-256 and delete_duplicates trashes non-kept copies."""
        dupes = duplicate_service.find_duplicates(str(self.workspace), keep_by="oldest")
        self.assertEqual(len(dupes), 1)
        self.assertEqual(len(dupes[0]), 3)
        self.assertEqual(Path(dupes[0][0]).name, "original.txt")

        count, errors = duplicate_service.delete_duplicates(
            dupes,
            workspace=str(self.workspace),
            keep_by="oldest",
            return_details=True,
        )
        self.assertEqual(count, 2)
        self.assertEqual(len(errors), 0)
        self.assertTrue(self.orig.exists())
        self.assertFalse(self.copy1.exists())
        self.assertFalse(self.copy2.exists())

    def test_deletion_rejects_modified_candidate(self):
        """Candidate modified between scan and delete is NOT deleted."""
        dupes = duplicate_service.find_duplicates(str(self.workspace), keep_by="oldest")
        self.assertEqual(len(dupes), 1)

        # Modify copy1 after scan (different size and hash)
        self.copy1.write_text("tampered content that differs significantly", encoding="utf-8")

        count, errors = duplicate_service.delete_duplicates(
            dupes,
            workspace=str(self.workspace),
            keep_by="oldest",
            return_details=True,
        )
        # copy1 was skipped, copy2 was deleted
        self.assertEqual(count, 1)
        self.assertTrue(self.orig.exists())
        self.assertTrue(self.copy1.exists(), "Modified candidate must not be deleted!")
        self.assertFalse(self.copy2.exists())
        self.assertTrue(any("modified after scan" in e or "byte comparison failed" in e for e in errors))

    def test_deletion_rejects_missing_kept_file(self):
        """If the kept file is deleted after scan, candidate deletion is aborted."""
        dupes = duplicate_service.find_duplicates(str(self.workspace), keep_by="oldest")
        self.assertEqual(len(dupes), 1)

        # Remove the kept file (original.txt)
        self.orig.unlink()

        count, errors = duplicate_service.delete_duplicates(
            dupes,
            workspace=str(self.workspace),
            keep_by="oldest",
            return_details=True,
        )
        self.assertEqual(count, 0)
        # Both copies must survive to avoid total data loss
        self.assertTrue(self.copy1.exists())
        self.assertTrue(self.copy2.exists())
        self.assertTrue(any("does not exist" in e or "no longer exists" in e for e in errors))

    def test_deletion_rejects_outside_workspace_path(self):
        """Crafted duplicate group containing paths outside workspace is blocked."""
        outside_victim = self.outside_dir / "victim.txt"
        outside_victim.write_text("identical content for testing", encoding="utf-8")

        forged_group = [[str(self.orig), str(outside_victim)]]
        count, errors = duplicate_service.delete_duplicates(
            forged_group,
            workspace=str(self.workspace),
            keep_by="oldest",
            return_details=True,
        )
        self.assertEqual(count, 0)
        self.assertTrue(outside_victim.exists(), "Outside victim must not be deleted!")
        self.assertTrue(any("outside workspace" in e for e in errors))

    def test_files_are_identical_byte_verification(self):
        """files_are_identical detects exact content differences even with equal lengths."""
        f1 = self.workspace / "f1.bin"
        f2 = self.workspace / "f2.bin"
        f3 = self.workspace / "f3.bin"

        f1.write_bytes(b"A" * 1024)
        f2.write_bytes(b"A" * 1024)
        f3.write_bytes(b"A" * 1023 + b"B")

        self.assertTrue(duplicate_service.files_are_identical(f1, f2))
        self.assertFalse(duplicate_service.files_are_identical(f1, f3))


if __name__ == "__main__":
    unittest.main()
