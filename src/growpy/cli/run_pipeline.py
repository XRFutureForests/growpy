#!/usr/bin/env python3
"""
Complete GrowPy Pipeline Runner

This script runs the complete GrowPy pipeline from start to finish:
1. Prepare assets from The Grove 2.2
2. Export twigs to FBX
3. Create growth models
4. Generate forest from CSV (optional)
5. Export individual tree species (optional)

Usage:
    # Run full pipeline
    python run_pipeline.py

    # Run specific steps
    python run_pipeline.py --steps prepare,twigs,models

    # Skip steps
    python run_pipeline.py --skip-prepare

    # Generate forest from CSV
    python run_pipeline.py --forest-csv forest_data.csv
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


class PipelineRunner:
    """Manages the execution of the GrowPy pipeline."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.cli_dir = base_dir / "src" / "growpy" / "cli"
        self.assets_dir = base_dir / "data" / "assets"
        self.results = {}

    def run_command(self, script_name: str, args: List[str] = None) -> bool:
        """Run a CLI script and return success status."""
        script_path = self.cli_dir / script_name
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)

        print(f"\n{'=' * 60}")
        print(f"Running: {script_name}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'=' * 60}\n")

        try:
            result = subprocess.run(cmd, cwd=str(self.base_dir), check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to run {script_name}: {e}")
            return False
        except Exception as e:
            print(f"❌ Error running {script_name}: {e}")
            return False

    def step_prepare(self) -> bool:
        """Step 1: Prepare assets from The Grove 2.2."""
        print("\n🔹 Step 1: Prepare Assets")
        return self.run_command("prepare_assets.py")

    def step_export_twigs(self) -> bool:
        """Step 2: Export twigs to FBX."""
        print("\n🔹 Step 2: Export Twigs to FBX")
        twigs_dir = self.assets_dir / "twigs"
        if not twigs_dir.exists():
            print(f"⚠️ Twigs directory not found: {twigs_dir}")
            print("   Skipping twig export")
            return True
        return self.run_command("export_twigs.py", [str(twigs_dir)])

    def step_create_models(self, cycles: int = 125, seeds: int = 1,
                          height_threshold: float = 0.05,
                          max_cycles_without_growth: int = 3,
                          timeout: int = 300) -> bool:
        """Step 3: Create growth models."""
        print("\n🔹 Step 3: Create Growth Models")
        args = [
            "--cycles", str(cycles),
            "--seeds", str(seeds),
            "--height-threshold", str(height_threshold),
            "--max-cycles-without-growth", str(max_cycles_without_growth),
            "--timeout", str(timeout),
        ]
        return self.run_command("create_growth_models.py", args)

    def step_generate_forest(self, csv_file: Path = None, output_dir: Path = None) -> bool:
        """Step 4: Generate forest from CSV."""
        print("\n🔹 Step 4: Generate Forest from CSV")
        if csv_file is None:
            print("   No CSV file specified, skipping forest generation")
            return True

        args = [str(csv_file)]
        if output_dir:
            args.extend(["--output-dir", str(output_dir)])

        return self.run_command("generate_forest.py", args)

    def step_export_trees(self, cycles: int = 10, output_dir: Path = None) -> bool:
        """Step 5: Export individual tree species."""
        print("\n🔹 Step 5: Export Individual Trees")
        args = ["--cycles", str(cycles)]
        if output_dir:
            args.extend(["--output-dir", str(output_dir)])

        return self.run_command("export_trees.py", args)

    def run_pipeline(self, steps: List[str], forest_csv: Path = None,
                    model_cycles: int = 125, model_seeds: int = 1,
                    height_threshold: float = 0.05,
                    max_cycles_without_growth: int = 3,
                    timeout: int = 300,
                    tree_cycles: int = 10) -> bool:
        """Run the complete pipeline with specified steps."""
        print("\n" + "=" * 60)
        print("🌲 GrowPy Pipeline Runner")
        print("=" * 60)
        print(f"Base directory: {self.base_dir}")
        print(f"Steps to run: {', '.join(steps)}")
        print("=" * 60)

        step_functions = {
            "prepare": lambda: self.step_prepare(),
            "twigs": lambda: self.step_export_twigs(),
            "models": lambda: self.step_create_models(
                model_cycles, model_seeds, height_threshold,
                max_cycles_without_growth, timeout
            ),
            "forest": lambda: self.step_generate_forest(forest_csv),
            "trees": lambda: self.step_export_trees(tree_cycles),
        }

        for step in steps:
            if step not in step_functions:
                print(f"⚠️ Unknown step: {step}")
                continue

            success = step_functions[step]()
            self.results[step] = success

            if not success:
                print(f"\n❌ Step '{step}' failed!")
                print("Pipeline stopped.")
                return False

        print("\n" + "=" * 60)
        print("✅ Pipeline completed successfully!")
        print("=" * 60)
        print("\nResults:")
        for step, success in self.results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {step}")
        print("=" * 60)

        return True


def main():
    """Main pipeline runner."""
    parser = argparse.ArgumentParser(
        description="Run the complete GrowPy pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Steps:
    prepare - Copy assets from The Grove 2.2
    twigs   - Export twigs to FBX with materials
    models  - Create growth models for all species
    forest  - Generate forest from CSV data
    trees   - Export individual tree species

Examples:
    # Run full pipeline (prepare, twigs, models only)
    python run_pipeline.py

    # Run specific steps
    python run_pipeline.py --steps prepare,twigs,models

    # Skip preparation step
    python run_pipeline.py --skip-prepare

    # Run with forest generation
    python run_pipeline.py --forest-csv data/forest.csv

    # Customize growth model parameters
    python run_pipeline.py --model-cycles 150 --model-seeds 3 --height-threshold 0.03

Note: Growth models now automatically stop iteration when consecutive cycles
      don't increase tree height (controlled by --height-threshold and
      --max-cycles-without-growth parameters).
        """
    )

    # Step selection
    parser.add_argument(
        "--steps",
        type=str,
        default="prepare,twigs,models",
        help="Comma-separated list of steps to run (default: prepare,twigs,models)"
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Skip asset preparation step"
    )
    parser.add_argument(
        "--skip-twigs",
        action="store_true",
        help="Skip twig export step"
    )
    parser.add_argument(
        "--skip-models",
        action="store_true",
        help="Skip growth model creation step"
    )

    # Forest generation
    parser.add_argument(
        "--forest-csv",
        type=Path,
        default=None,
        help="CSV file for forest generation (enables forest step)"
    )
    parser.add_argument(
        "--export-trees",
        action="store_true",
        help="Enable individual tree export step"
    )

    # Growth model parameters
    parser.add_argument(
        "--model-cycles",
        type=int,
        default=125,
        help="Maximum growth cycles for model creation (default: 125)"
    )
    parser.add_argument(
        "--model-seeds",
        type=int,
        default=1,
        help="Number of random seeds for growth models (default: 1)"
    )
    parser.add_argument(
        "--height-threshold",
        type=float,
        default=0.05,
        help="Minimum height increase to consider as growth (default: 0.05)"
    )
    parser.add_argument(
        "--max-cycles-without-growth",
        type=int,
        default=3,
        help="Stop after N cycles without growth (default: 3)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds per seed (default: 300)"
    )

    # Tree export parameters
    parser.add_argument(
        "--tree-cycles",
        type=int,
        default=10,
        help="Growth cycles for individual tree export (default: 10)"
    )

    args = parser.parse_args()

    # Determine steps to run
    steps = [s.strip() for s in args.steps.split(",")]

    # Apply skip flags
    if args.skip_prepare and "prepare" in steps:
        steps.remove("prepare")
    if args.skip_twigs and "twigs" in steps:
        steps.remove("twigs")
    if args.skip_models and "models" in steps:
        steps.remove("models")

    # Add optional steps
    if args.forest_csv and "forest" not in steps:
        steps.append("forest")
    if args.export_trees and "trees" not in steps:
        steps.append("trees")

    if not steps:
        print("❌ No steps selected to run")
        return 1

    # Get base directory
    base_dir = Path(__file__).parent.parent.parent.parent

    # Create and run pipeline
    runner = PipelineRunner(base_dir)
    success = runner.run_pipeline(
        steps=steps,
        forest_csv=args.forest_csv,
        model_cycles=args.model_cycles,
        model_seeds=args.model_seeds,
        height_threshold=args.height_threshold,
        max_cycles_without_growth=args.max_cycles_without_growth,
        timeout=args.timeout,
        tree_cycles=args.tree_cycles,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())