"""Sensitivity analysis pipeline for Grove seed parameters.

Sweeps the top-N parameters by observed range across all preset files,
simulates tree growth for each parameter combination at specified cycle
counts, and produces icons + aggregate CSV/MD reports.

Architecture:
    1. run_param_catalog()       → param_catalog.csv  (from tools/param_catalog)
    2. build_sweep_design()      → combo list (lo/hi × top-N params, i.e. 2^N)
    3. run_grove_simulation()    → per-combo grove + skeleton + tree objects
    4. measure_metrics()         → height, DBH, crown stats, branch counts
    5. generate images           → 3 icons + 2×2 preview per combo×cycles
    6. save_results()            → sensitivity_overview.csv + .md
"""

import itertools
import json
import logging
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from growpy.constants import BREAST_HEIGHT_METERS
from growpy.io.usd.preview import generate_icon_image, generate_sensitivity_preview
from growpy.tools.param_catalog import DEFAULT_PRESET_DIRS, run_param_catalog

logger = logging.getLogger(__name__)


class _NullTimer:
    """Stub timer compatible with ProfileTimer.track() interface."""

    @contextmanager
    def track(self, name: str):
        yield


def load_base_preset(preset_path: Path) -> dict:
    """Load preset JSON and strip calibration/curve data.

    Also applies longevity overrides to prevent premature tree death during
    parameter exploration.
    """
    with open(preset_path) as f:
        data = json.load(f)

    data.pop("_yield_table_calibration", None)
    for k in [k for k in data if k.endswith("_curve")]:
        del data[k]

    # Prevent tree death so parameter effects are visible at all cycle counts
    data.update(
        {
            "drop_decay": 0.1,
            "drop_weak": 0.1,
            "drop_shaded": 0.0,
            "drop_obsolete": 0.0,
        }
    )
    return data


def _merge_combo(base_preset: dict, combo_params: dict) -> dict:
    """Merge swept overrides onto the base, coercing to each base param's type.

    Swept levels are floats (p10/p50/p90), but integer-typed (usize) Grove fields
    reject floats. Cast each override to int when the base value is an int.
    """
    merged = dict(base_preset)
    for key, val in combo_params.items():
        base_val = base_preset.get(key)
        if isinstance(base_val, int) and not isinstance(base_val, bool):
            merged[key] = int(round(val))
        else:
            merged[key] = val
    return merged


def run_grove_simulation(
    preset_data: dict,
    cycles: int,
    seed: int = 42,
) -> tuple:
    """Run a Grove simulation and return (skeleton, tree).

    Args:
        preset_data: Merged preset dict (base + param overrides).
        cycles: Number of growth cycles to simulate.
        seed: RNG seed for reproducibility.

    Returns:
        (skeleton, tree) — either may be None if grove produces no trees.
    """
    import the_grove_23_core as gc

    grove = gc.Grove()
    grove.clear_trees()
    grove.set_random_seed(seed)

    properties = gc.io.properties_from_json_string(json.dumps(preset_data))
    grove.set_properties(properties)

    grove.clear_trees()
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    grove.simulate(cycles)

    tree = grove.trees[0] if grove.trees else None
    skeletons = grove.build_skeletons(True)
    skeleton = skeletons[0] if skeletons else None

    return skeleton, tree


def _measure_dbh(tree, target_height: float = BREAST_HEIGHT_METERS) -> float:
    """Measure diameter at breast height via trunk node interpolation."""
    if not hasattr(tree, "nodes") or not tree.nodes:
        return 0.0

    trunk_nodes = []
    for node in tree.nodes:
        if hasattr(node, "pos") and hasattr(node, "radius"):
            trunk_nodes.append({"height": node.pos.z, "radius": node.radius})

    if not trunk_nodes:
        return 0.0

    trunk_nodes.sort(key=lambda x: x["height"])

    if trunk_nodes[-1]["height"] < target_height:
        return 0.0

    node_below = node_above = None
    for tn in trunk_nodes:
        if tn["height"] <= target_height:
            node_below = tn
        elif node_above is None:
            node_above = tn
            break

    if node_below and node_below["height"] == target_height:
        return node_below["radius"] * 2.0
    if node_below is None:
        return 0.0
    if node_above is None:
        return node_below["radius"] * 2.0

    ratio = (target_height - node_below["height"]) / (
        node_above["height"] - node_below["height"]
    )
    r = node_below["radius"] + ratio * (node_above["radius"] - node_below["radius"])
    return r * 2.0


def measure_metrics(skeleton, tree) -> dict:
    """Compute tree morphology metrics from skeleton and tree objects."""
    metrics = {
        "height_m": 0.0,
        "dbh_m": 0.0,
        "crown_width_m": 0.0,
        "crown_radius_m": 0.0,
        "crown_area_m2": 0.0,
        "branch_count": 0,
        "segment_count": 0,
    }

    if skeleton is None:
        return metrics

    try:
        pts_raw = list(skeleton.points)
        if not pts_raw:
            return metrics
        first = pts_raw[0]
        if hasattr(first, "x"):
            points = np.array([(v.x, v.y, v.z) for v in pts_raw], dtype=float)
        elif isinstance(first, (list, tuple)):
            points = np.array(pts_raw, dtype=float)
        else:
            points = np.array([float(v) for v in pts_raw], dtype=float).reshape(-1, 3)
    except Exception:
        return metrics

    if len(points) == 0:
        return metrics

    max_z = float(points[:, 2].max())
    metrics["height_m"] = max_z

    upper_mask = points[:, 2] > 0.5 * max_z
    upper_pts = points[upper_mask]
    if len(upper_pts) >= 2:
        x_span = float(upper_pts[:, 0].max() - upper_pts[:, 0].min())
        y_span = float(upper_pts[:, 1].max() - upper_pts[:, 1].min())
        metrics["crown_width_m"] = max(x_span, y_span)

        upper_xy = upper_pts[:, :2]
        centroid = upper_xy.mean(axis=0)
        radii = np.linalg.norm(upper_xy - centroid, axis=1)
        metrics["crown_radius_m"] = float(radii.mean())

        if len(upper_xy) >= 3:
            try:
                from scipy.spatial import ConvexHull

                metrics["crown_area_m2"] = float(ConvexHull(upper_xy).volume)
            except Exception:
                pass

    poly_lines = list(skeleton.poly_lines)
    metrics["branch_count"] = len(poly_lines)
    metrics["segment_count"] = sum(max(0, len(pl) - 1) for pl in poly_lines)

    if tree is not None:
        metrics["dbh_m"] = _measure_dbh(tree)

    return metrics


def build_sweep_design(
    catalog: pd.DataFrame,
    n_params: int,
) -> tuple[list[str], list[dict], dict]:
    """Select top-N parameters and generate all lo/hi combinations.

    Uses min/max values from the catalog (skipping mean/median to reduce
    combinatorial explosion: 2^N vs 3^N combos).

    Args:
        catalog: Parameter catalog DataFrame sorted by range descending.
        n_params: Number of top parameters to sweep.

    Returns:
        (selected_params, combos, param_levels)
        - selected_params: list of parameter names
        - combos: list of dicts mapping param_name → float value
        - param_levels: dict mapping param_name → {"lo": float, "hi": float}
    """
    top = catalog.head(n_params)
    selected_params = top["parameter"].tolist()

    param_levels: dict[str, dict[str, float]] = {}
    for _, row in top.iterrows():
        param_levels[row["parameter"]] = {
            "lo": float(row["min"]),
            "hi": float(row["max"]),
        }

    level_lists = [
        [(name, lvl, val) for lvl, val in lvls.items()]
        for name, lvls in param_levels.items()
    ]

    combos = [
        {name: val for name, _, val in combo}
        for combo in itertools.product(*level_lists)
    ]

    return selected_params, combos, param_levels


def run_sensitivity_sweep(
    base_preset_path: Path,
    output_dir: Path,
    preset_dirs: list[Path] | None = None,
    n_params: int = 6,
    cycle_counts: list[int] | None = None,
    seed: int = 42,
    dry_run: bool = False,
) -> Path:
    """Run the full sensitivity sweep and return path to overview CSV.

    Args:
        base_preset_path: Path to the .seed.json used as the base preset.
        output_dir: Root output directory for all generated files.
        preset_dirs: Directories to scan for parameter catalog.
        n_params: Top-N parameters by range to sweep.
        cycle_counts: Growth cycle counts to test (default: [10, 20, 30]).
        seed: RNG seed for all simulations.
        dry_run: Print plan without running simulations.

    Returns:
        Path to sensitivity_overview.csv (or param_catalog.csv in dry-run).
    """
    if cycle_counts is None:
        cycle_counts = [10, 20, 30]
    if preset_dirs is None:
        preset_dirs = DEFAULT_PRESET_DIRS

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "param_catalog.csv"
    catalog = run_param_catalog(preset_dirs, catalog_path)

    selected_params, combos, param_levels = build_sweep_design(catalog, n_params)
    total = len(combos) * len(cycle_counts)

    print("Sensitivity sweep plan:")
    print(f"  Base preset: {base_preset_path.name}")
    print(f"  Parameters ({n_params}): {', '.join(selected_params)}")
    print(f"  Combos: {len(combos)}  (2^{n_params} = {2**n_params})")
    print(f"  Cycle counts: {cycle_counts}")
    print(f"  Total simulations: {total}")
    print()

    if dry_run:
        print("Top parameters by range (min/max):")
        sub = catalog.head(n_params)[["parameter", "range", "min", "max"]]
        print(sub.to_string(index=False))
        print()
        for param, levels in param_levels.items():
            print(
                f"  {param:<35} lo={levels['lo']:.4g}  hi={levels['hi']:.4g}"
            )
        return catalog_path

    base_preset = load_base_preset(base_preset_path)
    timer = _NullTimer()
    rows = []

    run_iter = tqdm(
        [(cid, cp, cyc) for cid, cp in enumerate(combos) for cyc in cycle_counts],
        desc="Sensitivity sweep",
        unit="sim",
    )

    for combo_id, combo_params, cycles in run_iter:
        prefix = f"{combo_id:04d}_c{cycles:02d}"
        preset_data = _merge_combo(base_preset, combo_params)

        try:
            skeleton, tree = run_grove_simulation(preset_data, cycles, seed)
        except Exception as e:
            logger.warning("Simulation failed combo=%d cycles=%d: %s", combo_id, cycles, e)
            skeleton, tree = None, None

        metrics = measure_metrics(skeleton, tree)

        for view in ("front", "side", "top"):
            generate_icon_image(output_dir, prefix, skeleton, timer, view=view)

        generate_sensitivity_preview(
            output_dir, prefix, skeleton, timer,
            metrics=metrics, param_labels=combo_params,
        )

        row: dict = {
            "combo_id": combo_id,
            "cycles": cycles,
            **combo_params,
            **metrics,
            "icon_front": f"{prefix}_icon_front.png",
            "icon_side": f"{prefix}_icon_side.png",
            "icon_top": f"{prefix}_icon_top.png",
            "preview": f"{prefix}_preview.png",
        }
        rows.append(row)

    csv_path = output_dir / "sensitivity_overview.csv"
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    logger.info("Saved: %s (%d rows)", csv_path, len(df))

    _write_overview_md(
        output_dir / "sensitivity_overview.md",
        catalog.head(n_params),
        param_levels,
        selected_params,
        cycle_counts,
        df,
    )

    print(f"\nDone. Results in: {output_dir}")
    print(f"  {csv_path.name} — {len(df)} rows")
    print("  sensitivity_overview.md — icon grid")

    return csv_path


def _write_overview_md(
    md_path: Path,
    catalog_top: pd.DataFrame,
    param_levels: dict,
    selected_params: list[str],
    cycle_counts: list[int],
    df: pd.DataFrame,
) -> None:
    """Write overview markdown with param catalog table and per-param icon grids."""
    lines = ["# Sensitivity Analysis Overview", ""]

    # Param catalog table
    lines.append("## Parameter Catalog (top-N by range)")
    lines.append("")
    lines.append("| Parameter | Range | lo (min) | hi (max) |")
    lines.append("|---|---|---|---|")
    for _, row in catalog_top.iterrows():
        levels = param_levels.get(row["parameter"], {})
        lines.append(
            f"| `{row['parameter']}` "
            f"| {row['range']:.4g} "
            f"| {levels.get('lo', 0):.4g} "
            f"| {levels.get('hi', 0):.4g} |"
        )
    lines.append("")

    # Per-parameter icon grids (hold all other params at lo)
    lo_vals = {p: param_levels[p]["lo"] for p in selected_params}

    lines.append("## Per-Parameter Icon Grids")
    lines.append("")
    lines.append("Rows: lo / hi.  Columns: cycle counts.  Other params held at lo (default).")
    lines.append("")

    for param_name in selected_params:
        lines.append(f"### `{param_name}`")
        lines.append("")

        header = "| Level |" + "".join(f" {c} cycles |" for c in cycle_counts)
        separator = "|---|" + "---|" * len(cycle_counts)
        lines.append(header)
        lines.append(separator)

        for level_name in ("lo", "hi"):
            level_val = param_levels[param_name][level_name]
            row_cells = [f"**{level_name}** ({level_val:.4g})"]

            for cycles in cycle_counts:
                mask = df["cycles"] == cycles
                for other_p in selected_params:
                    if other_p != param_name:
                        mask = mask & (df[other_p] == lo_vals[other_p])
                mask = mask & (df[param_name] == level_val)
                matching = df[mask]

                if len(matching) > 0:
                    icon = matching.iloc[0]["icon_side"]
                    row_cells.append(f"![{level_name} {cycles}c]({icon})")
                else:
                    row_cells.append("—")

            lines.append("| " + " | ".join(row_cells) + " |")

        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved: %s", md_path)
