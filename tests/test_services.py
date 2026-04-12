import unittest
import os
import shutil
from pathlib import Path
from services import file_service, organizer_service

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

    def test_flatten_workspace(self):
        history, count = organizer_service.flatten_workspace(str(self.test_dir), False, lambda x: None)
        self.assertEqual(count, 1) # only nested.txt should be moved
        self.assertTrue((self.test_dir / "nested.txt").exists())
        self.assertFalse((self.test_dir / "subdir").exists())

    def test_sequential_rename(self):
        history, count = organizer_service.sequential_rename(str(self.test_dir), "new_", "files", "name", False, "", False, lambda x: None)
        self.assertEqual(count, 2)
        self.assertTrue((self.test_dir / "new_01.txt").exists())
        self.assertTrue((self.test_dir / "new_02.txt").exists())

if __name__ == '__main__':
    unittest.main()
