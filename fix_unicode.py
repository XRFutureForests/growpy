"""Fix Unicode checkmarks in Python files."""

import sys
from pathlib import Path


def fix_unicode_in_file(filepath):
    """Replace Unicode checkmarks with ASCII equivalents."""
    # Read the file with UTF-8 encoding
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace Unicode characters
    content = content.replace("✓", "[OK]")
    content = content.replace("✗", "[X]")

    # Write back with UTF-8 encoding
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Fixed Unicode characters in {filepath}")


if __name__ == "__main__":
    files = [
        "src/growpy/io/blender_export.py",
        "src/growpy/io/unreal_nanite_assembly.py",
    ]

    for file in files:
        fix_unicode_in_file(Path(file))

    print("Done!")
    print("Done!")
