"""Scan Grove preset .seed.json files and catalog parameter ranges.

Scans all preset directories, extracts scalar numeric parameters (float/int),
computes min/max/range/mean/std and percentile bounds per parameter, and saves
the ranked catalog as CSV.

Usage:
    python -m growpy.tools.param_catalog
    python -m growpy.tools.param_catalog --output data/output/sensitivity/param_catalog.csv
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.config.paths import get_assets_directory, get_project_root

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("_",)
_SKIP_TYPES = (bool, dict, list)

# Competition/environment geometry params — not tree morphology
_SKIP_PARAMS = frozenset({
    "shade_area",
    "shade_alongside",
    "shade_distance",
    "shade_height",
    "surround_distance",
    "surround_height",
    "surround_count",
    "surround_randomness",
})

DEFAULT_PRESET_DIRS = [
    get_project_root() / "src" / "the_grove_23" / "presets",
    get_assets_directory() / "presets",
]


def scan_presets_per_file(preset_dirs: list[Path]) -> dict[Path, dict[str, float]]:
    """Collect scalar parameter values per .seed.json file.

    Returns:
        Dict mapping preset file path to {parameter name: float value}.
    """
    per_file: dict[Path, dict[str, float]] = {}

    for preset_dir in preset_dirs:
        if not preset_dir.exists():
            logger.warning("Preset dir not found: %s", preset_dir)
            continue
        files = sorted(preset_dir.glob("*.seed.json"))
        if not files:
            logger.debug("No .seed.json files in %s", preset_dir)
            continue
        logger.debug("Scanning %d files in %s", len(files), preset_dir)

        for seed_file in files:
            try:
                with open(seed_file) as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", seed_file.name, e)
                continue

            params: dict[str, float] = {}
            for key, val in data.items():
                if any(key.startswith(p) for p in _SKIP_PREFIXES):
                    continue
                if key in _SKIP_PARAMS:
                    continue
                if isinstance(val, _SKIP_TYPES):
                    continue
                if not isinstance(val, (int, float)):
                    continue
                params[key] = float(val)
            per_file[seed_file] = params

    return per_file


def scan_presets(preset_dirs: list[Path]) -> dict[str, list[float]]:
    """Collect scalar parameter values across all .seed.json files.

    Returns:
        Dict mapping parameter name to list of observed float values.
    """
    param_values: dict[str, list[float]] = {}
    for params in scan_presets_per_file(preset_dirs).values():
        for key, val in params.items():
            param_values.setdefault(key, []).append(val)
    return param_values


def find_central_preset(preset_dirs: list[Path] | None = None) -> Path:
    """Find the preset whose parameters are closest to the cross-preset mean.

    Z-score normalizes each scalar parameter across all presets, then returns
    the preset with the smallest RMS z-distance from the mean — the most
    "representative" / central config. Used as the default sensitivity base
    preset so swept trees are anchored on an average tree rather than an
    arbitrary species.
    """
    if preset_dirs is None:
        preset_dirs = DEFAULT_PRESET_DIRS

    per_file = scan_presets_per_file(preset_dirs)
    if not per_file:
        raise RuntimeError(
            "No presets found to compute central preset. Check that preset dirs exist."
        )

    values: dict[str, list[float]] = {}
    for params in per_file.values():
        for key, val in params.items():
            values.setdefault(key, []).append(val)
    stats = {k: (float(np.mean(v)), float(np.std(v))) for k, v in values.items()}

    best_path: Path | None = None
    best_score = float("inf")
    for path, params in per_file.items():
        zs = [
            ((val - stats[key][0]) / stats[key][1]) ** 2
            for key, val in params.items()
            if stats[key][1] > 0
        ]
        if not zs:
            continue
        score = float(np.sqrt(np.mean(zs)))
        if score < best_score:
            best_score = score
            best_path = path

    if best_path is None:
        raise RuntimeError("Could not determine central preset.")

    logger.info("Central preset: %s (rms z=%.4f)", best_path.stem, best_score)
    return best_path


def _is_integer_param(key: str, observed: list[float], template: dict) -> bool:
    """Whether a param is integer-typed (per template type, else integral values)."""
    tv = template.get(key)
    if isinstance(tv, bool):
        return False
    if isinstance(tv, int):
        return True
    if tv is None:
        return all(float(x).is_integer() for x in observed)
    return False


def build_average_preset(
    preset_dirs: list[Path] | None = None,
    statistic: str = "mean",
    template_path: Path | None = None,
) -> dict:
    """Synthesize a preset with every scalar param set to its cross-preset average.

    This provides a neutral, artificial baseline (rather than an arbitrary real
    species) from which swept parameters move up/down. Non-scalar fields
    (booleans, strings, competition geometry) are taken from a template preset —
    the central preset by default — so the result is a complete, simulatable seed.

    Args:
        preset_dirs: Directories of .seed.json presets to average over.
        statistic: "mean" or "median" for the per-parameter central value.
        template_path: Preset supplying non-scalar structure (default: central preset).
    """
    if preset_dirs is None:
        preset_dirs = DEFAULT_PRESET_DIRS
    if statistic not in ("mean", "median"):
        raise ValueError(f"statistic must be 'mean' or 'median', got: {statistic}")

    per_file = scan_presets_per_file(preset_dirs)
    if not per_file:
        raise RuntimeError("No presets found to build an average preset.")

    values: dict[str, list[float]] = {}
    for params in per_file.values():
        for key, val in params.items():
            values.setdefault(key, []).append(val)

    if template_path is None:
        template_path = find_central_preset(preset_dirs)
    with open(template_path) as f:
        preset = json.load(f)

    # Grove has integer-typed (usize) fields that reject floats; round the
    # average to int for params the template stores as int (or that are integral
    # in every preset) so the synthesized seed deserializes.
    reducer = np.mean if statistic == "mean" else np.median
    averages: dict[str, float] = {}
    for key, vals in values.items():
        avg = float(reducer(vals))
        if _is_integer_param(key, vals, preset):
            avg = int(round(avg))
        averages[key] = avg

    preset.update(averages)
    logger.info(
        "Average preset: %d scalar params set to %s (template: %s)",
        len(averages),
        statistic,
        template_path.stem,
    )
    return preset


def build_catalog(param_values: dict[str, list[float]]) -> pd.DataFrame:
    """Compute per-parameter stats ranked by interpercentile spread (p90-p10).

    Ranking on p90-p10 rather than full range avoids single-outlier presets
    dominating the selection and guarantees the lo/mid/hi sweep levels (p10/p50/p90)
    are distinct.
    """
    rows = []
    for param, vals in param_values.items():
        arr = np.array(vals)
        p10 = float(np.percentile(arr, 10))
        p50 = float(np.percentile(arr, 50))
        p90 = float(np.percentile(arr, 90))
        rows.append(
            {
                "parameter": param,
                "count": len(arr),
                "min": float(arr.min()),
                "max": float(arr.max()),
                "range": float(arr.max() - arr.min()),
                "ip_range": p90 - p10,
                "mean": float(arr.mean()),
                "std": float(arr.std()),
                "p10": p10,
                "p50": p50,
                "p90": p90,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("ip_range", ascending=False).reset_index(drop=True)


def run_param_catalog(
    preset_dirs: list[Path] | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Scan presets, build catalog, optionally save CSV, return DataFrame."""
    if preset_dirs is None:
        preset_dirs = DEFAULT_PRESET_DIRS

    param_values = scan_presets(preset_dirs)
    if not param_values:
        raise RuntimeError(
            "No scalar parameters found. Check that preset dirs exist and contain .seed.json files."
        )

    df = build_catalog(param_values)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info("Param catalog: %d parameters → %s", len(df), output_path)

    return df


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan Grove preset files and produce a parameter range catalog.",
    )
    parser.add_argument(
        "--preset-dirs",
        nargs="+",
        type=Path,
        default=None,
        help="Preset directories to scan (default: src/the_grove_23/presets + data/assets/presets)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/sensitivity/param_catalog.csv"),
        help="Output CSV path (default: data/output/sensitivity/param_catalog.csv)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top parameters to display (default: 20)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    preset_dirs = args.preset_dirs or DEFAULT_PRESET_DIRS
    df = run_param_catalog(preset_dirs, args.output)

    print(f"\nParam catalog ({len(df)} parameters total), top {args.top} by range:\n")
    pd.set_option("display.float_format", "{:.4f}".format)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(df.head(args.top).to_string(index=False))
    print(f"\nSaved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
