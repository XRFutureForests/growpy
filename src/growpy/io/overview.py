"""Generate a markdown overview of all exported tree icon previews.

Scans the forest output directory for icon.png files and arranges them
into a species x height-interval table with separate rows for competition
and open-grown variants. Columns are determined by the configured
height_interval from growpy.toml.
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
    dicts of height_meters (int) -> relative icon path.
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
        height_m = int(re.findall(r"\d+", height_label)[0])
        entries.setdefault(key, {})[height_m] = str(rel_path).replace("\\", "/")
    return entries


def _snap_to_interval(height_m: int, interval: int) -> int:
    """Snap a height value to the nearest interval multiple."""
    if interval <= 0:
        return height_m
    return round(height_m / interval) * interval


def _build_interval_columns(entries: dict, interval: int) -> list:
    """Build sorted list of interval-aligned column heights from icon data."""
    snapped = set()
    for height_map in entries.values():
        for h in height_map:
            snapped.add(_snap_to_interval(h, interval))
    return sorted(snapped)


def _height_label(meters: int) -> str:
    """Format height as label like h05m, h10m."""
    return f"h{meters:02d}m"


def generate_overview_markdown(
    forest_dir: Path, height_interval: float = 5.0
) -> Path:
    """Generate dataset_overview.md in the forest output directory.

    Args:
        forest_dir: Path to the forest output directory.
        height_interval: Height interval in meters from growpy.toml config.

    Returns the path to the generated markdown file.
    """
    entries = _parse_icon_files(forest_dir)
    if not entries:
        logger.warning("No icon files found in %s", forest_dir)
        return forest_dir / "dataset_overview.md"

    interval = max(1, int(height_interval))
    columns = _build_interval_columns(entries, interval)
    if not columns:
        logger.warning("No height columns after interval alignment")
        return forest_dir / "dataset_overview.md"

    # Build lookup: (species, context) -> {snapped_height -> icon_path}
    snapped_entries = {}
    for key, height_map in entries.items():
        snapped = {}
        for h, path in height_map.items():
            col = _snap_to_interval(h, interval)
            snapped[col] = path
        snapped_entries[key] = snapped

    all_species = sorted(set(sp for sp, _ in entries.keys()))

    lines = []
    lines.append("# Dataset Overview")
    lines.append("")
    lines.append(
        f"Tree preview icons by species, growth context, "
        f"and height interval ({interval}m steps)."
    )
    lines.append("")

    col_headers = " | ".join(_height_label(c) for c in columns)
    lines.append(f"| Species | Context | {col_headers} |")
    separator = " | ".join(["---"] * (2 + len(columns)))
    lines.append(f"| {separator} |")

    for species in all_species:
        species_display = species.replace("_", " ").title()
        for context in ("competition", "open_grown"):
            ctx_short = "comp" if context == "competition" else "open"
            ctx_display = "Competition" if context == "competition" else "Open Grown"
            key = (species, ctx_short)
            height_map = snapped_entries.get(key, {})

            cells = []
            for col in columns:
                if col in height_map:
                    img_path = height_map[col]
                    cells.append(f"![{_height_label(col)}]({img_path})")
                else:
                    cells.append("")
            row = " | ".join(cells)
            lines.append(f"| {species_display} | {ctx_display} | {row} |")

    lines.append("")

    output_path = forest_dir / "dataset_overview.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Dataset overview written to %s", output_path)
    return output_path
