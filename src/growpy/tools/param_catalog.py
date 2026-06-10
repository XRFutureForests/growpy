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


def scan_presets(preset_dirs: list[Path]) -> dict[str, list[float]]:
    """Collect scalar parameter values across all .seed.json files.

    Returns:
        Dict mapping parameter name to list of observed float values.
    """
    param_values: dict[str, list[float]] = {}

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
                for key, val in data.items():
                    if any(key.startswith(p) for p in _SKIP_PREFIXES):
                        continue
                    if key in _SKIP_PARAMS:
                        continue
                    if isinstance(val, _SKIP_TYPES):
                        continue
                    if not isinstance(val, (int, float)):
                        continue
                    param_values.setdefault(key, []).append(float(val))
            except Exception as e:
                logger.warning("Failed to parse %s: %s", seed_file.name, e)

    return param_values


def build_catalog(param_values: dict[str, list[float]]) -> pd.DataFrame:
    """Compute per-parameter stats ranked by observed range."""
    rows = []
    for param, vals in param_values.items():
        arr = np.array(vals)
        rows.append(
            {
                "parameter": param,
                "count": len(arr),
                "min": float(arr.min()),
                "max": float(arr.max()),
                "range": float(arr.max() - arr.min()),
                "mean": float(arr.mean()),
                "std": float(arr.std()),
                "p10": float(np.percentile(arr, 10)),
                "p50": float(np.percentile(arr, 50)),
                "p90": float(np.percentile(arr, 90)),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("range", ascending=False).reset_index(drop=True)


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
