"""Tests for services.journal_service."""

import json
import tempfile
import unittest
from pathlib import Path

from services.journal_service import (
    HISTORY_FILENAME,
    JOURNAL_SCHEMA_VERSION,
    JournalAction,
    JournalBatch,
    JournalEntry,
    TransactionJournal,
    load_and_validate_journal,
    revert_journal,
    save_journal,
)


class TestJournalService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix="fop-test-journal-")
        self.workspace = Path(self.temp_dir.name).resolve()
        (self.workspace / "original.txt").write_text("content", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_untrusted_legacy_history_quarantined(self):
        """FOP-AUD-001: Legacy list history must be quarantined without executing."""
        history_file = self.workspace / HISTORY_FILENAME
        history_file.write_text(
            json.dumps([{"action": "create", "src": "a", "dst": "b"}]),
            encoding="utf-8"
        )

        batch, error = load_and_validate_journal(self.workspace)
        self.assertIsNone(batch)
        self.assertIn("quarantined", error.lower())
        self.assertFalse(history_file.exists())  # Must have been renamed

        quarantined = list(self.workspace.glob(".organizer_history.quarantined_*.json"))
        self.assertEqual(len(quarantined), 1)

    def test_escaping_destination_quarantined(self):
        """FOP-AUD-001: History targeting paths outside the workspace must be rejected and quarantined."""
        outside_victim = self.workspace.parent / "victim"
        history_file = self.workspace / HISTORY_FILENAME
        crafted_data = {
            "version": JOURNAL_SCHEMA_VERSION,
            "operation_id": "test_op",
            "operation_name": "test",
            "workspace": str(self.workspace),
            "entries": [
                {
                    "action": "create",
                    "src": str(self.workspace / "dummy.zip"),
                    "dst": str(outside_victim),
                }
            ],
        }
        history_file.write_text(json.dumps(crafted_data), encoding="utf-8")

        batch, error = load_and_validate_journal(self.workspace)
        self.assertIsNone(batch)
        self.assertIn("escapes workspace", error)
        self.assertFalse(history_file.exists())

    def test_revert_move_operation(self):
        """Reverting a move must restore the file to its original location."""
        src_file = self.workspace / "moved_orig.txt"
        dst_file = self.workspace / "sub" / "moved_dest.txt"
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_text("payload", encoding="utf-8")

        batch = JournalBatch(
            version=JOURNAL_SCHEMA_VERSION,
            operation_id="move_test",
            operation_name="test_move",
            workspace=str(self.workspace),
            entries=[
                JournalEntry(
                    action=JournalAction.MOVE.value,
                    src=str(src_file),
                    dst=str(dst_file),
                )
            ],
        )
        save_journal(batch, self.workspace)

        res = revert_journal(self.workspace)
        self.assertTrue(res["success"])
        self.assertTrue(src_file.exists())
        self.assertFalse(dst_file.exists())
        self.assertEqual(src_file.read_text(encoding="utf-8"), "payload")

        # History should be cleared after full success
        self.assertFalse((self.workspace / HISTORY_FILENAME).exists())

    def test_revert_create_uses_recycle_bin(self):
        """Reverting a created file sends it to Recycle Bin, not permanent deletion."""
        created_file = self.workspace / "created_output.txt"
        created_file.write_text("output data", encoding="utf-8")

        batch = JournalBatch(
            version=JOURNAL_SCHEMA_VERSION,
            operation_id="create_test",
            operation_name="test_create",
            workspace=str(self.workspace),
            entries=[
                JournalEntry(
                    action=JournalAction.CREATE.value,
                    src=str(self.workspace / "source.zip"),
                    dst=str(created_file),
                )
            ],
        )
        save_journal(batch, self.workspace)

        res = revert_journal(self.workspace)
        self.assertTrue(res["success"])
        self.assertFalse(created_file.exists())

    def test_partial_failure_preserves_remaining_entries(self):
        """FOP-AUD-004: If an undo entry fails, remaining entries must be preserved in history."""
        existing_dst = self.workspace / "exists.txt"
        existing_src = self.workspace / "restored_exists.txt"
        existing_dst.write_text("exists", encoding="utf-8")

        missing_dst = self.workspace / "missing.txt"
        missing_src = self.workspace / "restored_missing.txt"

        batch = JournalBatch(
            version=JOURNAL_SCHEMA_VERSION,
            operation_id="partial_test",
            operation_name="test_partial",
            workspace=str(self.workspace),
            entries=[
                JournalEntry(
                    action=JournalAction.MOVE.value,
                    src=str(missing_src),
                    dst=str(missing_dst),
                ),
                JournalEntry(
                    action=JournalAction.MOVE.value,
                    src=str(existing_src),
                    dst=str(existing_dst),
                ),
            ],
        )
        save_journal(batch, self.workspace)

        res = revert_journal(self.workspace)
        self.assertEqual(res["reverted"], 1)
        self.assertEqual(res["failed"], 1)
        self.assertTrue(existing_src.exists())

        # The missing entry must still be in the history file
        retained_batch, _ = load_and_validate_journal(self.workspace)
        self.assertIsNotNone(retained_batch)
        self.assertEqual(len(retained_batch.entries), 1)
        self.assertEqual(retained_batch.entries[0].dst, str(missing_dst))

    def test_transaction_journal_incremental_saves(self):
        """FOP-AUD-004: Steps recorded via TransactionJournal must be saved incrementally."""
        tx = TransactionJournal(self.workspace, "batch_test")
        file_a = self.workspace / "a.txt"
        file_b = self.workspace / "b.txt"

        tx.record_step(JournalAction.MOVE, file_a, file_b)

        # Confirm saved on disk immediately
        loaded, _ = load_and_validate_journal(self.workspace)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.entries), 1)
        self.assertEqual(loaded.entries[0].src, str(file_a))

        tx.commit()
        loaded_after, _ = load_and_validate_journal(self.workspace)
        self.assertEqual(loaded_after.status, "completed")


if __name__ == '__main__':
    unittest.main()
