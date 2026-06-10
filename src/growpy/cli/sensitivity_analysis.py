"""CLI entry point for the Grove parameter sensitivity analysis pipeline.

Sweeps top-N Grove seed parameters (by observed range across all presets),
simulates tree growth at each parameter combination, and produces icon images
plus an aggregate CSV and Markdown overview.

Usage:
    growpy-sensitivity-analysis --dry-run
    growpy-sensitivity-analysis --n-params 4 --cycles 10,20 --base-preset "Fagaceae - Beech"
    growpy-sensitivity-analysis --n-params 6 --output-dir data/output/sensitivity/run01
"""

import argparse
import logging
import sys
from pathlib import Path

from growpy.config.paths import get_assets_directory, get_project_root
from growpy.pipelines.sensitivity_pipeline import run_sensitivity_sweep
from growpy.tools.param_catalog import DEFAULT_PRESET_DIRS

logger = logging.getLogger(__name__)

_DEFAULT_BASE_PRESET = "Fagaceae - Beech"
_DEFAULT_OUTPUT_DIR = Path("data/output/sensitivity")


def _resolve_base_preset(stem: str) -> Path:
    """Find the base preset file by stem name across known preset dirs."""
    search_dirs = [
        get_project_root() / "src" / "the_grove_23" / "presets",
        get_assets_directory() / "presets",
    ]
    for d in search_dirs:
        candidate = d / f"{stem}.seed.json"
        if candidate.exists():
            return candidate

    candidates = []
    for d in search_dirs:
        if d.exists():
            candidates.extend(d.glob("*.seed.json"))
    names = sorted(c.stem for c in candidates)
    raise FileNotFoundError(
        f"Base preset not found: '{stem}'\nAvailable: {names}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grove parameter sensitivity analysis — sweep top-N params across presets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Print sweep plan only, no simulations:
  growpy-sensitivity-analysis --dry-run

  # Sweep top 4 params, two cycle counts, custom base preset:
  growpy-sensitivity-analysis --n-params 4 --cycles 10,20 --base-preset "Coniferae - Norway Spruce"

  # Full default sweep (3^6 = 729 combos × 3 cycle counts = 2187 sims):
  growpy-sensitivity-analysis --n-params 6 --cycles 10,20,30

Output files in --output-dir:
  param_catalog.csv          Parameter ranges across all scanned presets
  sensitivity_overview.csv   One row per combo × cycles (metrics + image paths)
  sensitivity_overview.md    Per-parameter icon grid for visual browsing
  {combo_id}_c{cycles}_icon_{front,side,top}.png
  {combo_id}_c{cycles}_preview.png
""",
    )
    parser.add_argument(
        "--preset-dirs",
        nargs="+",
        type=Path,
        default=None,
        help="Preset directories to scan for parameter catalog "
        "(default: src/the_grove_23/presets + data/assets/presets)",
    )
    parser.add_argument(
        "--base-preset",
        type=str,
        default=_DEFAULT_BASE_PRESET,
        help=f"Base preset stem to build combos on (default: '{_DEFAULT_BASE_PRESET}')",
    )
    parser.add_argument(
        "--n-params",
        type=int,
        default=6,
        help="Top-N parameters by range to sweep (default: 6, giving 3^N combos)",
    )
    parser.add_argument(
        "--cycles",
        type=str,
        default="10,20,30",
        help="Comma-separated growth cycle counts (default: 10,20,30)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Output root directory (default: {_DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for all simulations (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print sweep plan (combo count, param table) without running simulations",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        cycle_counts = [int(x.strip()) for x in args.cycles.split(",") if x.strip()]
    except ValueError:
        print(f"ERROR: --cycles must be comma-separated integers, got: {args.cycles}")
        return 1

    if args.n_params < 1:
        print("ERROR: --n-params must be at least 1")
        return 1

    try:
        base_preset_path = _resolve_base_preset(args.base_preset)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    preset_dirs = args.preset_dirs or DEFAULT_PRESET_DIRS

    total_combos = 3 ** args.n_params
    total_sims = total_combos * len(cycle_counts)
    if not args.dry_run:
        print(f"Starting sensitivity sweep: {total_sims} simulations")
        print("  (This may take a long time for large sweeps. Use --dry-run to preview.)")
        print()

    run_sensitivity_sweep(
        base_preset_path=base_preset_path,
        output_dir=args.output_dir,
        preset_dirs=preset_dirs,
        n_params=args.n_params,
        cycle_counts=cycle_counts,
        seed=args.seed,
        dry_run=args.dry_run,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
