"""Tests for collision-safe destination allocator (FOP-AUD-003, FOP-AUD-005)."""

import tempfile
import unittest
from pathlib import Path

from services.file_service import DestinationAllocator, allocate_unique_destination, safe_dest


class TestCollisionAllocator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix="fop-test-allocator-")
        self.workspace = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_multi_level_collision_avoids_overwriting(self):
        """FOP-AUD-003: Both file.txt and file_1.txt exist; allocator must pick file_2.txt."""
        (self.workspace / "beta.txt").write_text("orig", encoding="utf-8")
        (self.workspace / "beta_1.txt").write_text("sentinel", encoding="utf-8")

        allocator = DestinationAllocator(self.workspace)
        chosen = allocator.allocate("beta.txt")
        self.assertEqual(chosen.name, "beta_2.txt")
        self.assertFalse(chosen.exists())
        self.assertEqual((self.workspace / "beta_1.txt").read_text(encoding="utf-8"), "sentinel")

    def test_batch_reservation_in_memory(self):
        """Two files with the same name in a single batch must get distinct allocated names."""
        allocator = DestinationAllocator(self.workspace)
        first = allocator.allocate("report.pdf")
        second = allocator.allocate("report.pdf")

        self.assertEqual(first.name, "report.pdf")
        self.assertEqual(second.name, "report_1.pdf")
        self.assertNotEqual(first, second)

    def test_allocate_unique_destination_with_existing_output(self):
        """FOP-AUD-005: Existing primary and fallback names must not be overwritten."""
        primary = self.workspace / "photo_optimized.png"
        primary.write_text("existing-primary", encoding="utf-8")
        fallback = self.workspace / "photo_optimized_1.png"
        fallback.write_text("existing-fallback", encoding="utf-8")

        chosen = allocate_unique_destination(primary)
        self.assertEqual(chosen.name, "photo_optimized_2.png")
        self.assertFalse(chosen.exists())
        self.assertEqual(fallback.read_text(encoding="utf-8"), "existing-fallback")

    def test_safe_dest_wrapper(self):
        (self.workspace / "doc.txt").write_text("content", encoding="utf-8")
        dest = safe_dest(self.workspace, "doc.txt")
        self.assertEqual(dest.name, "doc_1.txt")


if __name__ == '__main__':
    unittest.main()
