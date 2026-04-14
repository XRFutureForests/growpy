"""Scaffold a project-level ``config/`` directory from packaged templates.

Copies every file in ``growpy/config/templates/`` into the target directory
(default: ``./config``). Existing files are skipped unless ``--force`` is
passed.
"""

import argparse
import shutil
import sys
from importlib import resources
from pathlib import Path


def _iter_template_files() -> list[tuple[str, Path]]:
    root = resources.files("growpy.config.templates")
    return sorted(
        (entry.name, Path(str(entry)))
        for entry in root.iterdir()
        if entry.is_file() and entry.name != "__init__.py"
    )


def _copy_templates(target: Path, force: bool) -> tuple[int, int]:
    target.mkdir(parents=True, exist_ok=True)
    copied, skipped = 0, 0
    for name, src in _iter_template_files():
        dst = target / name
        if dst.exists() and not force:
            print(f"  skip   {dst} (exists; use --force to overwrite)")
            skipped += 1
            continue
        shutil.copy2(src, dst)
        print(f"  write  {dst}")
        copied += 1
    return copied, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="growpy-init-config",
        description=(
            "Seed a project-level config/ directory with starter TOML files "
            "and the species lookup CSV."
        ),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("config"),
        help="Destination directory (default: ./config)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files instead of skipping them",
    )
    args = parser.parse_args()

    target = args.target.resolve()
    print(f"Writing templates to {target}")
    copied, skipped = _copy_templates(target, args.force)
    print(f"\nDone. {copied} written, {skipped} skipped.")
    if skipped and not args.force:
        print("Re-run with --force to overwrite existing files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
