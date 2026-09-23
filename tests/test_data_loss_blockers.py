import unittest
import shutil
import json
from pathlib import Path
from PIL import Image

from services import organizer_service, media_service, journal_service, path_guard
from services.path_guard import PathSecurityError
from services.file_service import DestinationAllocator, allocate_unique_destination


class TestDataLossBlockers(unittest.TestCase):
    def setUp(self):
        # Anchor test workspace inside the test directory so it avoids AppData/system-critical blocklists
        self.test_root = Path(__file__).parent / "tmp_m2_test_workspace"
        if self.test_root.exists():
            shutil.rmtree(self.test_root, ignore_errors=True)
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root, ignore_errors=True)

    def test_flatten_multiple_collision_chains_preserves_all_files(self):
        """FOP-AUD-003: Flattening must never overwrite pre-existing files,
        even when collision names (file_1.txt, file_2.txt) already exist."""
        # Setup: root has doc.txt and doc_1.txt
        root_doc = self.test_root / "doc.txt"
        root_doc.write_text("root-doc-original", encoding="utf-8")
        root_doc_1 = self.test_root / "doc_1.txt"
        root_doc_1.write_text("root-doc-1-preexisting", encoding="utf-8")

        # Subfolders each have a doc.txt
        sub1 = self.test_root / "sub1"
        sub1.mkdir()
        (sub1 / "doc.txt").write_text("sub1-doc-content", encoding="utf-8")

        sub2 = self.test_root / "sub2"
        sub2.mkdir()
        (sub2 / "doc.txt").write_text("sub2-doc-content", encoding="utf-8")

        # Live run
        history, count = organizer_service.flatten_workspace(
            str(self.test_root), dry_run=False, progress_callback=lambda x: None
        )

        self.assertEqual(count, 2)
        # Preexisting files must be untouched
        self.assertEqual(root_doc.read_text(encoding="utf-8"), "root-doc-original")
        self.assertEqual(root_doc_1.read_text(encoding="utf-8"), "root-doc-1-preexisting")

        # Subfolder files must have landed at doc_2.txt and doc_3.txt (order may vary)
        doc_2 = self.test_root / "doc_2.txt"
        doc_3 = self.test_root / "doc_3.txt"
        self.assertTrue(doc_2.exists())
        self.assertTrue(doc_3.exists())

        all_contents = {doc_2.read_text(encoding="utf-8"), doc_3.read_text(encoding="utf-8")}
        self.assertEqual(all_contents, {"sub1-doc-content", "sub2-doc-content"})

    def test_flatten_dry_run_allocates_non_colliding_previews(self):
        """FOP-AUD-003: Dry run preview must accurately simulate non-colliding
        destinations without creating files or overwriting."""
        (self.test_root / "item.txt").write_text("existing", encoding="utf-8")
        sub1 = self.test_root / "a"
        sub1.mkdir()
        (sub1 / "item.txt").write_text("from-a", encoding="utf-8")
        sub2 = self.test_root / "b"
        sub2.mkdir()
        (sub2 / "item.txt").write_text("from-b", encoding="utf-8")

        preview, count = organizer_service.flatten_workspace(
            str(self.test_root), dry_run=True, progress_callback=lambda x: None
        )

        self.assertEqual(count, 2)
        dst_paths = [Path(h["dst"]).name for h in preview]
        # Must allocate item_1.txt and item_2.txt
        self.assertEqual(sorted(dst_paths), ["item_1.txt", "item_2.txt"])

        # No files should have actually moved or been created
        self.assertFalse((self.test_root / "item_1.txt").exists())
        self.assertFalse((self.test_root / "item_2.txt").exists())
        self.assertTrue((sub1 / "item.txt").exists())
        self.assertTrue((sub2 / "item.txt").exists())

    def test_custom_rule_workspace_escape_rejected(self):
        """FOP-AUD-002: Custom rules with traversal or absolute paths must fail closed."""
        victim = self.test_root / "escape_victim.txt"
        victim.write_text("secret", encoding="utf-8")

        malicious_folders = [
            "../escaped",
            "..\\escaped",
            "/escaped",
            "C:/escaped",
            "sub/../../escaped",
            "NUL",
            "COM1",
            "bad:name",
        ]

        for bad_folder in malicious_folders:
            with self.subTest(folder=bad_folder):
                with self.assertRaises(PathSecurityError):
                    organizer_service.smart_categorize(
                        str(self.test_root),
                        dry_run=False,
                        custom_rules=[{"folder": bad_folder, "extensions": [".txt"], "keywords": []}],
                        progress_callback=lambda x: None,
                    )
                # Ensure victim file remains in place and intact
                self.assertTrue(victim.exists())
                self.assertEqual(victim.read_text(encoding="utf-8"), "secret")

    def test_media_fallback_overwrite_prevention(self):
        """FOP-AUD-005: When target output file already exists, allocate unique
        filename and do not destroy existing file."""
        src_img = self.test_root / "photo.png"
        img = Image.new("RGB", (20, 20), color="blue")
        img.save(src_img)

        # Pre-existing optimized target
        existing_opt = self.test_root / "photo_optimized.png"
        existing_opt.write_text("must-survive-existing-content", encoding="utf-8")

        # Optimize image
        res_dest, err = media_service.optimize_image(str(src_img), quality=80, progress_callback=lambda x: None)

        self.assertIsNone(err)
        self.assertIsNotNone(res_dest)
        # Returned destination should be unique (photo_optimized_1.png)
        self.assertTrue(Path(res_dest).exists())
        self.assertNotEqual(Path(res_dest).resolve(), existing_opt.resolve())
        self.assertEqual(Path(res_dest).name, "photo_optimized_1.png")
        # The pre-existing file must remain intact
        self.assertEqual(existing_opt.read_text(encoding="utf-8"), "must-survive-existing-content")

    def test_untrusted_history_quarantined_on_load(self):
        """FOP-AUD-001: History entries pointing outside workspace or missing
        required fields must be quarantined and never executed."""
        # Create external victim outside workspace
        external_dir = self.test_root.parent / "tmp_m2_external_victim_dir"
        external_dir.mkdir(parents=True, exist_ok=True)
        external_victim = external_dir / "external_victim.txt"
        external_victim.write_text("do-not-delete-me", encoding="utf-8")

        history_file = self.test_root / ".organizer_history.json"
        malicious_payload = {
            "version": "2.0",
            "operation_id": "malicious_op",
            "operation_name": "organize",
            "workspace": str(self.test_root),
            "entries": [
                {
                    "action": "move",
                    "src": str(self.test_root / "file.txt"),
                    "dst": str(external_victim),  # Malicious: points outside workspace!
                }
            ]
        }
        history_file.write_text(json.dumps(malicious_payload), encoding="utf-8")

        # Load history via journal_service
        batch, err = journal_service.load_and_validate_journal(self.test_root)

        self.assertIsNone(batch)
        self.assertIsNotNone(err)
        self.assertIn("quarantined", err.lower())

        # Verify history file was quarantined on disk
        quarantined = list(self.test_root.glob(".organizer_history.quarantined_*.json"))
        self.assertEqual(len(quarantined), 1)

        # Attempt revert - should do nothing to external file
        res = journal_service.revert_journal(self.test_root)
        self.assertFalse(res["success"])
        self.assertTrue(external_victim.exists())
        self.assertEqual(external_victim.read_text(encoding="utf-8"), "do-not-delete-me")

        # Cleanup external dir
        shutil.rmtree(external_dir, ignore_errors=True)

    def test_transaction_journal_durability_on_partial_failure(self):
        """FOP-AUD-004: If an operation fails midway through a batch, all operations
        executed prior to failure must remain persisted in journal."""
        f1 = self.test_root / "a.old"
        f1.write_text("file-a", encoding="utf-8")
        f2 = self.test_root / "b.old"
        f2.write_text("file-b", encoding="utf-8")

        journal = journal_service.TransactionJournal(self.test_root, operation_name="rename_batch")

        # First operation succeeds
        f1_new = self.test_root / "a.new"
        f1.rename(f1_new)
        journal.record_step(action="move", src=str(f1), dst=str(f1_new))

        # Simulate unexpected crash/failure before second operation
        del journal  # Flush & close

        # Verify history file on disk contains the first operation
        batch, err = journal_service.load_and_validate_journal(self.test_root)
        self.assertIsNone(err)
        self.assertIsNotNone(batch)
        self.assertEqual(len(batch.entries), 1)
        self.assertEqual(batch.entries[0].src, str(f1))
        self.assertEqual(batch.entries[0].dst, str(f1_new))

        # Now revert the partial history
        res = journal_service.revert_journal(self.test_root)
        self.assertTrue(res["success"])
        self.assertEqual(res["reverted"], 1)
        self.assertEqual(res["failed"], 0)
        self.assertTrue(f1.exists())
        self.assertFalse(f1_new.exists())


if __name__ == "__main__":
    unittest.main()
