"""Central registry for Folders Organizer Pro operation capabilities.

Defines mutating, destructive, dry-run, confirmation, undo, and recursive
behaviors in one single backend source of truth for both Python and UI layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class OperationSpec:
    name: str
    display_name: str
    is_mutating: bool
    is_destructive: bool
    supports_dry_run: bool
    supports_undo: bool
    supports_recursive: bool
    requires_confirmation: bool
    description: str = ""


_OPERATIONS: List[OperationSpec] = [
    # Core organizer operations
    OperationSpec(
        name="sequential_rename",
        display_name="Sequential Rename",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Renames files or folders sequentially with a custom prefix."
    ),
    OperationSpec(
        name="sort_by_date",
        display_name="Sort By Date",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Organizes files into date-based subfolders."
    ),
    OperationSpec(
        name="smart_categorize",
        display_name="Smart Categorize",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Sorts files into categories based on extensions, keywords, and custom rules."
    ),
    OperationSpec(
        name="change_extensions",
        display_name="Change Extensions",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=True,
        requires_confirmation=True,
        description="Batch alters file extensions across the workspace."
    ),
    OperationSpec(
        name="flatten_workspace",
        display_name="Flatten Workspace",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Moves all nested files to workspace root and removes empty directories."
    ),
    OperationSpec(
        name="delete_duplicates",
        display_name="Delete Duplicates",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=True,
        description="Sends detected duplicate files to the Recycle Bin."
    ),

    # Advanced automation operations
    OperationSpec(
        name="advanced_regex_rename",
        display_name="Advanced Regex Rename",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=True,
        requires_confirmation=True,
        description="Renames files using regular expression search and replace patterns."
    ),
    OperationSpec(
        name="cleanup_old_files",
        display_name="Cleanup Old Files",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=True,
        requires_confirmation=True,
        description="Archives files older than a specified number of days."
    ),
    OperationSpec(
        name="archive_large_files",
        display_name="Archive Large Files",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=True,
        requires_confirmation=True,
        description="Archives files exceeding a specified size threshold."
    ),
    OperationSpec(
        name="delete_empty_folders",
        display_name="Delete Empty Folders",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=True,
        description="Recursively scans and removes all empty folders."
    ),
    OperationSpec(
        name="additive_backup",
        display_name="Additive Backup",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Mirrors new or updated files to an external backup destination."
    ),
    OperationSpec(
        name="batch_unzip",
        display_name="Batch Unzip",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=True,
        requires_confirmation=True,
        description="Safely extracts compressed archives into dedicated folders."
    ),
    OperationSpec(
        name="batch_zip_folders",
        display_name="Batch Zip Folders",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Compresses selected top-level folders into individual archives."
    ),
    OperationSpec(
        name="convert_image_formats",
        display_name="Convert Image Formats",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=True,
        requires_confirmation=True,
        description="Converts images across PNG, JPG, and WebP formats."
    ),

    # Media operations
    OperationSpec(
        name="convert_mp3_to_wav",
        display_name="Convert MP3 to WAV",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=False,
        description="Converts a single MP3 audio file into uncompressed WAV."
    ),
    OperationSpec(
        name="batch_convert_mp3_to_wav",
        display_name="Batch Convert MP3 to WAV",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Batch converts MP3 audio files in the workspace into WAV."
    ),
    OperationSpec(
        name="compress_pdf",
        display_name="Compress PDF",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=False,
        description="Losslessly compresses a single PDF document."
    ),
    OperationSpec(
        name="batch_compress_pdf",
        display_name="Batch Compress PDF",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Batch compresses PDF documents in the workspace."
    ),
    OperationSpec(
        name="optimize_image",
        display_name="Optimize Image",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=False,
        description="Compresses and optimizes a single image."
    ),
    OperationSpec(
        name="batch_optimize_images",
        display_name="Batch Optimize Images",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=True,
        supports_undo=True,
        supports_recursive=False,
        requires_confirmation=True,
        description="Batch optimizes image files in the workspace."
    ),

    # Reversal & recovery
    OperationSpec(
        name="undo_last_operation",
        display_name="Undo Last Operation",
        is_mutating=True,
        is_destructive=True,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=True,
        description="Reverts filesystem modifications performed in the previous operation."
    ),

    # Read-only and configuration operations
    OperationSpec(
        name="scan_analyze",
        display_name="Scan & Analyze",
        is_mutating=False,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=False,
        description="Scans workspace and calculates category distributions."
    ),
    OperationSpec(
        name="find_duplicates",
        display_name="Find Duplicates",
        is_mutating=False,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=False,
        description="Identifies duplicate files by size and hash."
    ),
    OperationSpec(
        name="load_rules",
        display_name="Load Rules",
        is_mutating=False,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=False,
        description="Loads custom sorting rules for the workspace."
    ),
    OperationSpec(
        name="save_rules",
        display_name="Save Rules",
        is_mutating=True,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=False,
        description="Saves custom sorting rules to the workspace configuration."
    ),
    OperationSpec(
        name="list_folders",
        display_name="List Folders",
        is_mutating=False,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=False,
        description="Lists immediate subfolders in the workspace."
    ),
    OperationSpec(
        name="list_media_files",
        display_name="List Media Files",
        is_mutating=False,
        is_destructive=False,
        supports_dry_run=False,
        supports_undo=False,
        supports_recursive=False,
        requires_confirmation=False,
        description="Lists audio, PDF, and image media in the workspace."
    ),
]

OPERATION_REGISTRY: Dict[str, OperationSpec] = {op.name: op for op in _OPERATIONS}


def get_spec(op_name: str) -> Optional[OperationSpec]:
    """Retrieves the specification for a registered operation."""
    return OPERATION_REGISTRY.get(op_name)


def is_mutating(op_name: str) -> bool:
    """Returns True if the operation alters files or folders on disk."""
    spec = get_spec(op_name)
    return spec.is_mutating if spec else False


def is_destructive(op_name: str) -> bool:
    """Returns True if the operation permanently alters or deletes files."""
    spec = get_spec(op_name)
    return spec.is_destructive if spec else False


def supports_undo(op_name: str) -> bool:
    """Returns True if the operation records a reversible journal."""
    spec = get_spec(op_name)
    return spec.supports_undo if spec else False


def supports_dry_run(op_name: str) -> bool:
    """Returns True if the operation can produce a simulation preview without mutating files."""
    spec = get_spec(op_name)
    return spec.supports_dry_run if spec else False


def supports_recursive(op_name: str) -> bool:
    """Returns True if the operation accepts a recursive processing flag."""
    spec = get_spec(op_name)
    return spec.supports_recursive if spec else False


def requires_confirmation(op_name: str) -> bool:
    """Returns True if the operation requires a confirmation prompt when Simulation is off."""
    spec = get_spec(op_name)
    return spec.requires_confirmation if spec else False


def get_frontend_manifest() -> dict:
    """Exports a capability summary for the frontend to eliminate duplicated lists."""
    return {
        "operations": {name: asdict(spec) for name, spec in OPERATION_REGISTRY.items()},
        "undoable_ops": [op.name for op in _OPERATIONS if op.supports_undo],
        "destructive_ops": [op.name for op in _OPERATIONS if op.is_destructive],
        "recursive_capable_ops": [op.name for op in _OPERATIONS if op.supports_recursive],
        "confirmation_required_ops": [op.name for op in _OPERATIONS if op.requires_confirmation],
        "dry_run_capable_ops": [op.name for op in _OPERATIONS if op.supports_dry_run],
    }
