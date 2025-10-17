"""Path utility functions for GrowPy."""

from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating if needed.

    Args:
        path: Directory path to ensure exists

    Returns:
        The directory path
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent_dir(file_path: Path) -> Path:
    """Ensure parent directory of file exists.

    Args:
        file_path: File path whose parent should exist

    Returns:
        The file path
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path
