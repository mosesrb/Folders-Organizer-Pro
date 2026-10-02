import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

import organizer


class TestM5ReliabilityAndAccessibility(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(__file__).parent / "tmp_m5_test_workspace"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.api = organizer.OrganizerAPI()

    def tearDown(self):
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root, ignore_errors=True)

    # -------------------------------------------------------------------------
    # FOP-AUD-014: Recycle Bin & Deletion Error Guarantees
    # -------------------------------------------------------------------------

    def test_single_mp3_conversion_recycle_failure_does_not_fail_job(self):
        """When send2trash fails, the newly converted destination file is preserved,
        and the result returns success with a clear Recycle Bin warning."""
        mp3_path = self.test_root / "sample.mp3"
        mp3_path.write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 100)  # fake mp3 header

        with patch("services.media_service.convert_mp3_to_wav") as mock_convert, \
             patch("send2trash.send2trash", side_effect=OSError("Access is denied to Recycle Bin")):
            wav_path = str(self.test_root / "sample.wav")
            mock_convert.return_value = (wav_path, None)

            res = self.api.convert_mp3_to_wav(str(mp3_path), remove_original=True)

            self.assertTrue(res["success"])
            self.assertIn("warning", res)
            self.assertIn("Recycle Bin error", res["warning"])
            self.assertEqual(res["dst"], wav_path)
            self.assertTrue(mp3_path.exists())

    def test_batch_mp3_conversion_tracks_recycled_count_accurately(self):
        """Batch MP3 conversion tracks recycled vs recycle_failures accurately."""
        mp3_1 = self.test_root / "song1.mp3"
        mp3_2 = self.test_root / "song2.mp3"
        mp3_1.write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 50)
        mp3_2.write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 50)

        # Mock send2trash to succeed on first, fail on second
        side_effects = [None, OSError("Recycle Bin busy")]

        with patch("services.media_service.convert_mp3_to_wav") as mock_convert, \
             patch("send2trash.send2trash", side_effect=side_effects):
            mock_convert.side_effect = lambda path, cb: (path.replace(".mp3", ".wav"), None)

            res = self.api.batch_convert_mp3_to_wav(str(self.test_root), remove_original=True)

            self.assertTrue(res["success"])
            self.assertIn("1 moved to Recycle Bin; 1 could not be recycled", res["message"])
            self.assertEqual(len(res["errors"]), 1)

    def test_single_pdf_compression_recycle_failure_preserves_dst(self):
        """When PDF compression succeeds but send2trash fails, return success with warning."""
        pdf_path = self.test_root / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%EOF\n")

        with patch("services.media_service.compress_pdf") as mock_compress, \
             patch("send2trash.send2trash", side_effect=PermissionError("Locked")):
            compressed_path = str(self.test_root / "test_compressed.pdf")
            mock_compress.return_value = (compressed_path, None)

            res = self.api.compress_pdf(str(pdf_path), remove_original=True)

            self.assertTrue(res["success"])
            self.assertIn("warning", res)
            self.assertIn("Recycle Bin error", res["warning"])
            self.assertEqual(res["dst"], compressed_path)
            self.assertTrue(pdf_path.exists())

    def test_batch_pdf_compression_tracks_recycle_failures(self):
        """Batch PDF compression accurately reports recycled count and failures."""
        pdf_1 = self.test_root / "doc1.pdf"
        pdf_2 = self.test_root / "doc2.pdf"
        pdf_1.write_bytes(b"%PDF-1.4\n1\n%EOF\n")
        pdf_2.write_bytes(b"%PDF-1.4\n2\n%EOF\n")

        with patch("services.media_service.compress_pdf") as mock_compress, \
             patch("send2trash.send2trash", side_effect=OSError("Recycle disk full")):
            mock_compress.side_effect = lambda path, cb: (path.replace(".pdf", "_comp.pdf"), None)

            res = self.api.batch_compress_pdf(str(self.test_root), remove_original=True)

            self.assertTrue(res["success"])
            self.assertIn("Warning: 2 original(s) could not be moved to Recycle Bin", res["message"])
            self.assertEqual(len(res["errors"]), 2)

    def test_single_image_optimization_recycle_failure_returns_warning(self):
        """Image optimization preserves optimized image and reports warning when recycle fails."""
        img_path = self.test_root / "pic.png"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path)

        with patch("services.media_service.optimize_image") as mock_opt, \
             patch("send2trash.send2trash", side_effect=Exception("Virtual drive cannot recycle")):
            opt_path = str(self.test_root / "pic_optimized.png")
            mock_opt.return_value = (opt_path, None)

            res = self.api.optimize_image(str(img_path), quality=80, remove_original=True)

            self.assertTrue(res["success"])
            self.assertIn("warning", res)
            self.assertIn("Recycle Bin error", res["warning"])
            self.assertEqual(res["dst"], opt_path)
            self.assertTrue(img_path.exists())

    def test_batch_image_optimization_tracks_recycle_failures(self):
        """Batch image optimization reports recycle count and failures accurately."""
        img1 = self.test_root / "img1.png"
        img2 = self.test_root / "img2.png"
        Image.new("RGB", (50, 50), color="red").save(img1)
        Image.new("RGB", (50, 50), color="green").save(img2)

        side_effects = [None, OSError("Failed to trash")]
        with patch("services.media_service.optimize_image") as mock_opt, \
             patch("send2trash.send2trash", side_effect=side_effects):
            mock_opt.side_effect = lambda path, q, cb: (path.replace(".png", "_opt.png"), None)

            res = self.api.optimize_images(str(self.test_root), quality=80, remove_original=True)

            self.assertTrue(res["success"])
            self.assertIn("1 moved to Recycle Bin; 1 could not be recycled", res["message"])
            self.assertEqual(len(res["errors"]), 1)

    # -------------------------------------------------------------------------
    # FOP-AUD-018: Accessibility & Dialog Focus Trapping in App.jsx
    # -------------------------------------------------------------------------

    def test_app_jsx_accessibility_structures(self):
        """Verify FOP-AUD-018 accessibility constructs are implemented in ui/src/App.jsx."""
        app_jsx_path = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"
        self.assertTrue(app_jsx_path.exists(), "ui/src/App.jsx must exist")

        content = app_jsx_path.read_text(encoding="utf-8")

        # 1. Focus trap and Escape key dismissal hook
        self.assertIn("useModalA11y", content, "useModalA11y hook must be defined")
        self.assertIn("e.key === 'Escape'", content, "Escape key listener must be present")
        self.assertIn("e.key === 'Tab'", content, "Tab key focus trap must be present")
        self.assertIn("previousActiveElement.current.focus()", content, "Focus restoration must be present")

        # 2. Modal root refs and accessibility attributes
        self.assertIn("systemWarningRef", content, "systemWarningRef must be defined")
        self.assertIn("previewDialogRef", content, "previewDialogRef must be defined")
        self.assertIn("confirmDialogRef", content, "confirmDialogRef must be defined")
        self.assertIn("termsModalRef", content, "termsModalRef must be defined")

        self.assertIn('role="alertdialog"', content, "role=alertdialog must be present for critical shields")
        self.assertIn('aria-modal="true"', content, "aria-modal=true must be declared on dialogs")

        # 3. Main content isolation (inert and aria-hidden)
        self.assertIn('aria-hidden={isAnyModalOpen ? "true" : undefined}', content,
                      "Background container must declare aria-hidden when modal is open")
        self.assertIn('inert={isAnyModalOpen ? "" : undefined}', content,
                      "Background container must declare inert attribute when modal is open")

        # 4. Form control explicit IDs and programmatic labeling
        expected_ids = [
            "renamer-prefix-input",
            "renamer-filter-input",
            "source-extension-input",
            "target-extension-input",
            "extensions-recursive-toggle",
            "media-remove-original-mp3",
            "media-remove-original-pdf",
            "media-remove-original-image",
            "image-quality-slider",
            "advanced-recursive-toggle",
            "zip-target-ext-input",
            "zip-delete-originals-toggle",
            "advanced-regex-pattern",
            "advanced-regex-replacement",
            "automation-days-input",
            "large-file-threshold-input",
            "batch-convert-source-exts",
            "batch-convert-target-ext",
            "new-rule-folder-input",
            "new-rule-exts-input",
            "new-rule-keywords-input",
        ]

        for elem_id in expected_ids:
            self.assertIn(f'id="{elem_id}"', content, f"Form control element with id='{elem_id}' must be present")


if __name__ == "__main__":
    unittest.main()
