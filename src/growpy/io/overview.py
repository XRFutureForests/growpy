"""Generate dataset overview combining icon previews, preset data, and growth models.

Produces:
- dataset_overview.md: Markdown with icon table and key parameters
- dataset_overview.csv: Full pandas DataFrame for ML consumption
- dataset_overview_icons.png: Visual grid of all icon previews
"""

import json
import logging
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.image import imread

logger = logging.getLogger(__name__)

_ICON_PATTERN = re.compile(
    r"^(.+?)_(comp|open)_(h\d+m)_(d\d+cm)_(.+?)_icon\.png$", re.IGNORECASE
)

PRESET_COLUMNS = [
    "grow_length",
    "grow_nodes",
    "add_chance",
    "add_chance_reduce",
    "add_side_branches",
    "add_angle",
    "add_horizontal",
    "add_up",
    "add_fork",
    "add_bud_life",
    "add_regenerate",
    "add_only_on_end",
    "add_twist",
    "shade_area",
    "shade_area_depth",
    "shade_area_reduce",
    "shade_avoidance",
    "shade_alongside",
    "shade_alongside_diameter",
    "twig_density",
    "twig_longevity",
    "favor_bright",
    "favor_end",
    "favor_end_reduce",
    "favor_rising",
    "turn_random",
    "turn_to_horizon",
    "turn_to_light",
    "turn_up",
    "turn_up_in_shade",
    "bend_mass",
    "bend_reaction",
    "bend_twig_mass",
    "bend_twig_mass_solidify",
    "drop_decay",
    "drop_obsolete",
    "drop_shaded",
    "drop_weak",
    "thicken_tips",
    "thicken_tips_reduce",
    "thicken_join",
    "thicken_base_buttress",
    "thicken_base_scale",
    "thicken_base_shape",
    "thicken_deadwood",
    "auto_prune_enabled",
    "auto_prune_low",
    "auto_prune_keep_thick",
    "auto_prune_dangling",
    "surround_enabled",
    "surround_density",
    "surround_distance",
    "surround_height",
    "surround_grow",
    "simulation_scale",
]

GROWTH_MODEL_COLUMNS = [
    "gm_max_height",
    "gm_final_dbh",
    "gm_growth_rate",
    "gm_dbh_growth_rate",
    "gm_planned_cycles",
    "gm_actual_max_cycles",
    "gm_num_seeds",
    "gm_avg_simulation_time",
    "gm_cr_A",
    "gm_cr_k",
    "gm_cr_p",
    "gm_cr_r_squared",
]

DISPLAY_PRESET_COLUMNS = [
    "grow_length",
    "grow_nodes",
    "add_chance",
    "add_side_branches",
    "shade_area",
    "twig_density",
    "simulation_scale",
]

DISPLAY_GROWTH_COLUMNS = [
    "gm_max_height",
    "gm_final_dbh",
    "gm_growth_rate",
    "gm_cr_r_squared",
]


def _parse_icon_files(forest_dir: Path) -> dict:
    """Scan forest output and return structured icon data.

    Returns dict keyed by (species_clean, context) with values being
    dicts of {height_meters (int): (relative_path, absolute_path)}.
    """
    entries = {}
    for png in sorted(forest_dir.rglob("*_icon.png")):
        m = _ICON_PATTERN.match(png.name)
        if not m:
            continue
        species_title = m.group(1)
        context = m.group(2)
        height_label = m.group(3)
        rel_path = str(png.relative_to(forest_dir)).replace("\\", "/")
        species_clean = species_title.replace("_", " ").lower().replace(" ", "_")
        key = (species_clean, context)
        height_m = int(re.findall(r"\d+", height_label)[0])
        entries.setdefault(key, {})[height_m] = (rel_path, str(png))
    return entries


def _snap_to_interval(height_m: int, interval: int) -> int:
    if interval <= 0:
        return height_m
    return round(height_m / interval) * interval


def _build_interval_columns(entries: dict, interval: int) -> list:
    snapped = set()
    for height_map in entries.values():
        for h in height_map:
            snapped.add(_snap_to_interval(h, interval))
    return sorted(snapped)


def _height_label(meters: int) -> str:
    return f"h{meters:02d}m"


def _read_preset(preset_dir: Path, species: str) -> dict:
    """Read seed.json preset for a species, return flat dict."""
    preset_file = preset_dir / f"{species}.seed.json"
    if not preset_file.exists():
        return {}
    with open(preset_file, encoding="utf-8") as f:
        return json.load(f)


def _read_growth_model(models_dir: Path, species: str) -> dict:
    """Read growth model metadata and params, return prefixed dict."""
    species_dir = models_dir / species
    result = {}

    meta_file = species_dir / "metadata.json"
    if meta_file.exists():
        with open(meta_file, encoding="utf-8") as f:
            meta = json.load(f)
        result["gm_max_height"] = meta.get("max_height")
        result["gm_final_dbh"] = meta.get("final_dbh")
        result["gm_growth_rate"] = meta.get("growth_rate")
        result["gm_dbh_growth_rate"] = meta.get("dbh_growth_rate")
        result["gm_planned_cycles"] = meta.get("planned_cycles")
        result["gm_actual_max_cycles"] = meta.get("actual_max_cycles")
        result["gm_num_seeds"] = meta.get("num_seeds")
        result["gm_avg_simulation_time"] = meta.get("avg_simulation_time")

    params_file = species_dir / "growth_model_params.json"
    if params_file.exists():
        with open(params_file, encoding="utf-8") as f:
            params = json.load(f)
        result["gm_cr_A"] = params.get("A")
        result["gm_cr_k"] = params.get("k")
        result["gm_cr_p"] = params.get("p")
        result["gm_cr_r_squared"] = params.get("r_squared")

    return result


def build_dataset_dataframe(
    forest_dir: Path,
    preset_dir: Path,
    models_dir: Path,
    height_interval: float = 5.0,
) -> pd.DataFrame:
    """Build comprehensive DataFrame combining icons, presets, and growth models."""
    entries = _parse_icon_files(forest_dir)
    if not entries:
        return pd.DataFrame()

    interval = max(1, int(height_interval))
    columns = _build_interval_columns(entries, interval)

    rows = []
    all_species = sorted(set(sp for sp, _ in entries.keys()))

    for species in all_species:
        preset = _read_preset(preset_dir, species)
        growth = _read_growth_model(models_dir, species)

        for ctx_short, ctx_display in [("comp", "competition"), ("open", "open_grown")]:
            key = (species, ctx_short)
            height_map = entries.get(key, {})

            snapped = {}
            for h, paths in height_map.items():
                col = _snap_to_interval(h, interval)
                snapped[col] = paths

            row = {"species": species, "context": ctx_display}

            for col in columns:
                label = _height_label(col)
                if col in snapped:
                    row[f"icon_{label}"] = snapped[col][0]
                    row[f"icon_{label}_abs"] = snapped[col][1]
                else:
                    row[f"icon_{label}"] = ""
                    row[f"icon_{label}_abs"] = ""

            for param in PRESET_COLUMNS:
                row[param] = preset.get(param)

            row.update(growth)

            rows.append(row)

    return pd.DataFrame(rows)


def generate_icon_grid(
    df: pd.DataFrame, forest_dir: Path, height_interval: float = 5.0
) -> Path:
    """Export a PNG grid of all icon previews."""
    interval = max(1, int(height_interval))
    icon_cols = [c for c in df.columns if c.startswith("icon_h") and not c.endswith("_abs")]
    abs_cols = [c + "_abs" for c in icon_cols]

    all_species = df["species"].unique()
    contexts = df["context"].unique()
    n_rows = len(all_species) * len(contexts)
    n_cols = len(icon_cols)

    if n_rows == 0 or n_cols == 0:
        logger.warning("No data for icon grid")
        return forest_dir / "dataset_overview_icons.png"

    cell_size = 2.0
    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(n_cols * cell_size, n_rows * cell_size),
        squeeze=False,
    )

    for ax_row in axes:
        for ax in ax_row:
            ax.axis("off")

    row_idx = 0
    for species in all_species:
        for context in contexts:
            mask = (df["species"] == species) & (df["context"] == context)
            sub = df[mask]
            if sub.empty:
                row_idx += 1
                continue
            record = sub.iloc[0]

            for col_idx, (icon_col, abs_col) in enumerate(zip(icon_cols, abs_cols)):
                abs_path = record.get(abs_col, "")
                if abs_path and Path(abs_path).exists():
                    try:
                        img = imread(abs_path)
                        axes[row_idx][col_idx].imshow(img)
                    except Exception:
                        pass

                if col_idx == 0:
                    ctx_label = "C" if context == "competition" else "O"
                    label = f"{species.replace('_', ' ').title()} ({ctx_label})"
                    axes[row_idx][col_idx].set_ylabel(
                        label, fontsize=7, rotation=0, labelpad=120, va="center"
                    )

            row_idx += 1

    for col_idx, icon_col in enumerate(icon_cols):
        label = icon_col.replace("icon_", "")
        axes[0][col_idx].set_title(label, fontsize=8)

    plt.tight_layout()
    output_path = forest_dir / "dataset_overview_icons.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Icon grid written to %s", output_path)
    return output_path


def generate_overview_markdown(
    forest_dir: Path,
    height_interval: float = 5.0,
    preset_dir: Path = None,
    models_dir: Path = None,
) -> Path:
    """Generate dataset_overview.md, .csv, and icon grid PNG.

    Args:
        forest_dir: Path to the forest output directory.
        height_interval: Height interval in meters from growpy.toml config.
        preset_dir: Path to preset seed.json directory.
        models_dir: Path to growth_models directory.

    Returns the path to the generated markdown file.
    """
    if preset_dir is None:
        preset_dir = Path("data/assets/presets")
    if models_dir is None:
        models_dir = Path("data/assets/growth_models")

    df = build_dataset_dataframe(forest_dir, preset_dir, models_dir, height_interval)
    if df.empty:
        logger.warning("No icon files found in %s", forest_dir)
        return forest_dir / "dataset_overview.md"

    interval = max(1, int(height_interval))
    icon_cols = [c for c in df.columns if c.startswith("icon_h") and not c.endswith("_abs")]

    # Export CSV with all data (for ML consumption)
    csv_cols = (
        ["species", "context"]
        + icon_cols
        + [c for c in PRESET_COLUMNS if c in df.columns]
        + [c for c in GROWTH_MODEL_COLUMNS if c in df.columns]
    )
    csv_path = forest_dir / "dataset_overview.csv"
    df[csv_cols].to_csv(csv_path, index=False)
    logger.info("Dataset CSV written to %s", csv_path)

    # Export icon grid PNG
    generate_icon_grid(df, forest_dir, height_interval)

    # Build markdown
    lines = []
    lines.append("# Dataset Overview")
    lines.append("")
    lines.append(
        f"Tree preview icons by species, growth context, "
        f"and height interval ({interval}m steps)."
    )
    lines.append("")

    # Icon table
    col_headers = " | ".join(c.replace("icon_", "") for c in icon_cols)
    lines.append(f"| Species | Context | {col_headers} |")
    separator = " | ".join(["---"] * (2 + len(icon_cols)))
    lines.append(f"| {separator} |")

    for _, row in df.iterrows():
        species_display = row["species"].replace("_", " ").title()
        ctx_display = "Competition" if row["context"] == "competition" else "Open Grown"
        cells = []
        for col in icon_cols:
            if row[col]:
                label = col.replace("icon_", "")
                cells.append(f"![{label}]({row[col]})")
            else:
                cells.append("")
        lines.append(f"| {species_display} | {ctx_display} | {' | '.join(cells)} |")

    lines.append("")

    # Preset parameters table
    lines.append("## Preset Parameters")
    lines.append("")
    preset_header = " | ".join(DISPLAY_PRESET_COLUMNS)
    lines.append(f"| Species | {preset_header} |")
    sep = " | ".join(["---"] * (1 + len(DISPLAY_PRESET_COLUMNS)))
    lines.append(f"| {sep} |")

    seen_species = set()
    for _, row in df.iterrows():
        sp = row["species"]
        if sp in seen_species:
            continue
        seen_species.add(sp)
        sp_display = sp.replace("_", " ").title()
        vals = []
        for col in DISPLAY_PRESET_COLUMNS:
            v = row.get(col)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                vals.append("-")
            elif isinstance(v, float):
                vals.append(f"{v:.3g}")
            else:
                vals.append(str(v))
        lines.append(f"| {sp_display} | {' | '.join(vals)} |")

    lines.append("")

    # Growth model table
    lines.append("## Growth Model Summary")
    lines.append("")
    gm_display = ["max_height (m)", "final_dbh (m)", "growth_rate (m/yr)", "R^2"]
    gm_header = " | ".join(gm_display)
    lines.append(f"| Species | {gm_header} |")
    sep = " | ".join(["---"] * (1 + len(gm_display)))
    lines.append(f"| {sep} |")

    seen_species = set()
    for _, row in df.iterrows():
        sp = row["species"]
        if sp in seen_species:
            continue
        seen_species.add(sp)
        sp_display = sp.replace("_", " ").title()
        vals = []
        for col in DISPLAY_GROWTH_COLUMNS:
            v = row.get(col)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                vals.append("-")
            elif isinstance(v, float):
                vals.append(f"{v:.3g}")
            else:
                vals.append(str(v))
        lines.append(f"| {sp_display} | {' | '.join(vals)} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "Full dataset with all preset and growth model parameters: "
        "[dataset_overview.csv](dataset_overview.csv)"
    )
    lines.append("")
    lines.append("Icon grid: [dataset_overview_icons.png](dataset_overview_icons.png)")
    lines.append("")

    output_path = forest_dir / "dataset_overview.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Dataset overview written to %s", output_path)
    return output_path
