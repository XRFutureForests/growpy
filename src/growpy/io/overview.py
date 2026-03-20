"""Generate a markdown overview of all exported tree icon previews.

Scans the forest output directory for icon.png files and arranges them
into a species x height-interval table with separate rows for competition
and open-grown variants.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_ICON_PATTERN = re.compile(
    r"^(.+?)_(comp|open)_(h\d+m)_(d\d+cm)_(.+?)_icon\.png$", re.IGNORECASE
)


def _parse_icon_files(forest_dir: Path) -> dict:
    """Scan forest output and return structured icon data.

    Returns dict keyed by (species_clean, context) with values being
    dicts of height_label -> relative icon path.
    """
    entries = {}
    for png in sorted(forest_dir.rglob("*_icon.png")):
        m = _ICON_PATTERN.match(png.name)
        if not m:
            continue
        species_title = m.group(1)
        context = m.group(2)  # comp or open
        height_label = m.group(3)  # e.g. h05m
        rel_path = png.relative_to(forest_dir)
        species_clean = species_title.replace("_", " ").lower().replace(" ", "_")
        key = (species_clean, context)
        entries.setdefault(key, {})[height_label] = str(rel_path).replace("\\", "/")
    return entries


def _height_sort_key(label: str) -> int:
    """Extract numeric value from height label like h05m -> 5."""
    nums = re.findall(r"\d+", label)
    return int(nums[0]) if nums else 0


def generate_overview_markdown(forest_dir: Path) -> Path:
    """Generate dataset_overview.md in the forest output directory.

    Returns the path to the generated markdown file.
    """
    entries = _parse_icon_files(forest_dir)
    if not entries:
        logger.warning("No icon files found in %s", forest_dir)
        return forest_dir / "dataset_overview.md"

    all_heights = set()
    for height_map in entries.values():
        all_heights.update(height_map.keys())
    sorted_heights = sorted(all_heights, key=_height_sort_key)

    all_species = sorted(set(sp for sp, _ in entries.keys()))

    lines = []
    lines.append("# Dataset Overview")
    lines.append("")
    lines.append("Tree preview icons by species, growth context, and height interval.")
    lines.append("")

    height_headers = " | ".join(sorted_heights)
    lines.append(f"| Species | Context | {height_headers} |")
    separator = " | ".join(["---"] * (2 + len(sorted_heights)))
    lines.append(f"| {separator} |")

    for species in all_species:
        species_display = species.replace("_", " ").title()
        for context in ("competition", "open_grown"):
            ctx_short = "comp" if context == "competition" else "open"
            ctx_display = "Competition" if context == "competition" else "Open Grown"
            key = (species, ctx_short)
            height_map = entries.get(key, {})

            cells = []
            for h in sorted_heights:
                if h in height_map:
                    img_path = height_map[h]
                    cells.append(f"![{h}]({img_path})")
                else:
                    cells.append("")
            row = " | ".join(cells)
            lines.append(f"| {species_display} | {ctx_display} | {row} |")

    lines.append("")

    output_path = forest_dir / "dataset_overview.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Dataset overview written to %s", output_path)
    return output_path
