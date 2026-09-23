"""Tests for services.operation_registry."""

import unittest
from services.operation_registry import (
    OPERATION_REGISTRY,
    get_frontend_manifest,
    get_spec,
    is_destructive,
    is_mutating,
    requires_confirmation,
    supports_dry_run,
    supports_recursive,
    supports_undo,
)


class TestOperationRegistry(unittest.TestCase):
    def test_all_expected_operations_registered(self):
        expected_ops = [
            "sequential_rename", "sort_by_date", "smart_categorize",
            "change_extensions", "flatten_workspace", "delete_duplicates",
            "advanced_regex_rename", "cleanup_old_files", "archive_large_files",
            "delete_empty_folders", "additive_backup", "batch_unzip",
            "batch_zip_folders", "convert_image_formats", "convert_mp3_to_wav",
            "batch_convert_mp3_to_wav", "compress_pdf", "batch_compress_pdf",
            "optimize_image", "batch_optimize_images", "undo_last_operation",
            "scan_analyze", "find_duplicates", "load_rules", "save_rules",
            "list_folders", "list_media_files"
        ]
        for op in expected_ops:
            self.assertIn(op, OPERATION_REGISTRY, f"Operation {op} must be registered.")
            spec = get_spec(op)
            self.assertIsNotNone(spec)
            self.assertEqual(spec.name, op)
            self.assertTrue(len(spec.display_name) > 0)

    def test_mutating_and_destructive_classifications(self):
        # Read-only ops
        self.assertFalse(is_mutating("scan_analyze"))
        self.assertFalse(is_mutating("find_duplicates"))
        self.assertFalse(is_mutating("list_folders"))
        self.assertFalse(is_destructive("scan_analyze"))

        # Destructive ops
        self.assertTrue(is_destructive("delete_duplicates"))
        self.assertTrue(is_destructive("delete_empty_folders"))
        self.assertTrue(is_destructive("flatten_workspace"))
        self.assertTrue(is_destructive("change_extensions"))
        self.assertTrue(is_destructive("sequential_rename"))

        # Confirmation requirements
        self.assertTrue(requires_confirmation("delete_duplicates"))
        self.assertTrue(requires_confirmation("delete_empty_folders"))
        self.assertTrue(requires_confirmation("flatten_workspace"))

    def test_undo_and_dry_run_capabilities(self):
        self.assertTrue(supports_undo("flatten_workspace"))
        self.assertTrue(supports_undo("change_extensions"))
        self.assertTrue(supports_undo("smart_categorize"))
        self.assertTrue(supports_undo("batch_unzip"))
        self.assertTrue(supports_undo("additive_backup"))

        # delete_duplicates does not support undo (goes directly to Recycle Bin)
        self.assertFalse(supports_undo("delete_duplicates"))

        # Dry run support
        self.assertTrue(supports_dry_run("change_extensions"))
        self.assertTrue(supports_dry_run("batch_zip_folders"))
        self.assertFalse(supports_dry_run("undo_last_operation"))

        # Recursive support
        self.assertTrue(supports_recursive("change_extensions"))
        self.assertTrue(supports_recursive("batch_unzip"))
        self.assertFalse(supports_recursive("sequential_rename"))

    def test_frontend_manifest_generation(self):
        manifest = get_frontend_manifest()
        self.assertIn("operations", manifest)
        self.assertIn("undoable_ops", manifest)
        self.assertIn("destructive_ops", manifest)
        self.assertIn("recursive_capable_ops", manifest)
        self.assertIn("confirmation_required_ops", manifest)
        self.assertIn("dry_run_capable_ops", manifest)

        self.assertIn("change_extensions", manifest["undoable_ops"])
        self.assertIn("delete_duplicates", manifest["destructive_ops"])
        self.assertIn("batch_unzip", manifest["recursive_capable_ops"])


if __name__ == '__main__':
    unittest.main()
