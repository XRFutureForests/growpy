"""Step subprocess runner for the dataset pipeline.

Handles subprocess invocation for all four pipeline steps:
- Steps 1-3: single call per step, forwarding --csv to the step script.
- Step 4: one subprocess per species using the merged CSV, with optional
  parallel execution via ProcessPoolExecutor.

The bpy constraint (generate_forest.py imports bpy at module level) means
step 4 must always be run via subprocess; steps 1-3 use subprocess for
consistency so the pipeline process never imports bpy.
"""

import logging
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from growpy.pipelines.dataset_job_planner import find_species_csv

logger = logging.getLogger(__name__)


def _resolve_conda() -> str | None:
    """Resolve the conda executable path without relying on a shell.

    Prefers CONDA_EXE (a real executable) so callers can avoid shell=True, which
    would otherwise interpret shell metacharacters in interpolated CSV/species
    paths passed on the command line. Returns None when conda cannot be found.
    """
    import os
    import shutil

    return os.environ.get("CONDA_EXE") or shutil.which("conda")


def _wrap_in_env(cmd: list) -> list:
    """Wrap a command to execute inside the growpy conda environment.

    When conda is resolvable, prefix with ``conda run -n growpy`` so the
    subprocess uses the growpy env regardless of the parent's environment.
    When conda is not on PATH (e.g. the pipeline was launched directly with the
    growpy env's interpreter), run the command as-is: cmd[0] is already
    ``sys.executable`` from the active environment.
    """
    conda = _resolve_conda()
    if conda:
        return [conda, "run", "--no-capture-output", "-n", "growpy"] + cmd
    return cmd


STEP_SCRIPTS: dict[int, Path] = {
    1: Path("src/growpy/cli/prepare_assets.py"),
    2: Path("src/growpy/cli/convert_twigs.py"),
    3: Path("src/growpy/cli/create_growth_models.py"),
    4: Path("src/growpy/cli/generate_forest.py"),
}


def check_environment() -> bool:
    """Verify that bpy is importable in the current Python environment."""
    result = subprocess.run(
        [sys.executable, "-c", "import bpy"],
        capture_output=True,
    )
    if result.returncode != 0:
        logger.error(
            "bpy module not available in %s. "
            "Activate the growpy conda environment first: conda activate growpy",
            sys.executable,
        )
        return False
    return True


def run_step123(
    step: int,
    csv_path: Path,
    dry_run: bool = False,
    extra_args: list | None = None,
    verbose: bool = False,
) -> bool:
    """Run a single step (1, 2, or 3) as a subprocess with --csv.

    Returns True on success (or dry_run).
    """
    from pathlib import Path as PathlibPath

    script = STEP_SCRIPTS[step]
    cmd = [sys.executable, str(script), "--csv", str(csv_path)]
    if verbose:
        cmd.append("--verbose")
    if extra_args:
        cmd.extend(extra_args)

    if dry_run:
        logger.info("[DRY RUN] step %d: %s", step, " ".join(str(c) for c in cmd))
        return True

    logger.info("Step %d: %s", step, script.name)

    # Run in the growpy env (via conda run when available, else directly).
    # --no-capture-output lets subprocess stdout/stderr stream through in real-time
    run_cmd = _wrap_in_env(cmd)

    # Get project root for working directory
    project_root = PathlibPath(__file__).parent.parent.parent.parent

    # run_cmd[0] is an absolute executable path, so no shell is needed.
    result = subprocess.run(run_cmd, check=False, cwd=str(project_root))
    if result.returncode != 0:
        logger.error("Step %d FAILED (exit code %d)", step, result.returncode)
        return False

    logger.info("Step %d: OK", step)
    return True


def _build_step4_command(
    csv_path: Path,
    max_height: float = 0,
    skip_unreal_scripts: bool = False,
    verbose: bool = False,
) -> list:
    """Build the generate_forest.py command for a merged species CSV."""
    cmd = [sys.executable, str(STEP_SCRIPTS[4]), str(csv_path)]
    if max_height > 0:
        cmd.extend(["--max-height", str(max_height)])
    cmd.extend(["--export-trees", "1,2"])
    if skip_unreal_scripts:
        cmd.append("--no-unreal-scripts")
    if verbose:
        cmd.append("--verbose")
    return cmd


def run_species_step4(
    species_name: str,
    dataset_dir: Path,
    dry_run: bool = False,
    max_height: float = 0,
    skip_unreal_scripts: bool = False,
    verbose: bool = False,
) -> bool:
    """Run generate_forest.py for one species using its merged CSV.

    Returns True on success (or dry_run).
    """
    from pathlib import Path as PathlibPath

    csv_path = find_species_csv(species_name, dataset_dir)
    if not csv_path:
        logger.error("No merged CSV found for species: %s", species_name)
        return False

    cmd = _build_step4_command(csv_path, max_height, skip_unreal_scripts, verbose)

    if dry_run:
        logger.info(
            "[DRY RUN] step 4 [%s]: %s", species_name, " ".join(str(c) for c in cmd)
        )
        return True

    logger.info("Step 4 [%s]: running", species_name)

    # Run in the growpy env (via conda run when available, else directly).
    # --no-capture-output lets subprocess stdout/stderr stream through in real-time
    run_cmd = _wrap_in_env(cmd)

    # Get project root for working directory
    project_root = PathlibPath(__file__).parent.parent.parent.parent

    # run_cmd[0] is an absolute executable path, so no shell is needed.
    result = subprocess.run(run_cmd, check=False, cwd=str(project_root))
    if result.returncode != 0:
        logger.error(
            "Step 4 [%s]: FAILED (exit code %d)", species_name, result.returncode
        )
        return False

    logger.info("Step 4 [%s]: OK", species_name)
    return True


def _run_species_worker(args: tuple) -> tuple:
    """Top-level picklable worker for ProcessPoolExecutor."""
    species_name, dataset_dir, max_height, verbose = args
    t0 = time.monotonic()
    ok = run_species_step4(
        species_name,
        dataset_dir,
        max_height=max_height,
        skip_unreal_scripts=True,
        verbose=verbose,
    )
    elapsed = time.monotonic() - t0
    return species_name, ok, elapsed


def run_parallel_step4(
    species_list: list,
    workers: int,
    max_height: float,
    dataset_dir: Path,
    verbose: bool = False,
) -> tuple[list, dict]:
    """Run step 4 for multiple species in parallel.

    Returns (failed species names, elapsed seconds per species).
    """
    failed = []
    elapsed_by_species: dict = {}

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _run_species_worker, (species, dataset_dir, max_height, verbose)
            ): species
            for species in species_list
        }
        for future in as_completed(futures):
            species_name = futures[future]
            try:
                _, ok, elapsed = future.result()
                elapsed_by_species[species_name] = elapsed
                if not ok:
                    failed.append(species_name)
            except Exception:
                logger.exception("Worker crashed for %s", species_name)
                failed.append(species_name)

    return failed, elapsed_by_species


def generate_unreal_scripts(output_dir: Path, include_static: bool = False) -> None:
    """Generate Unreal import/cleanup scripts after all species have been exported.

    Called once after parallel step 4 workers finish, instead of per-species, to
    avoid race conditions from concurrent script deletion/regeneration.
    """
    from growpy.config.core import get_config
    from growpy.io.unreal.unreal_scripts import (
        generate_unreal_cleanup_script,
        generate_unreal_import_script,
    )
    from growpy.io.usd.assembly_export import create_combined_twig_usda

    config = get_config()

    instances_dir = output_dir / "Instances"
    if instances_dir.exists():
        combined = create_combined_twig_usda(
            instances_dir, include_static=include_static
        )
        if combined:
            logger.info("Created %d combined twig files for UE import", len(combined))

    nanite_cfg = {
        "voxelization": config.unreal_voxelization,
        "fallback_percent": config.unreal_nanite_fallback_percent,
        "fallback_target": config.unreal_nanite_fallback_target,
        "lerp_uvs": config.unreal_nanite_lerp_uvs,
    }

    import_script = generate_unreal_import_script(
        output_dir,
        config.unreal_project_path,
        include_static=include_static,
        voxelization=config.unreal_voxelization,
        nanite_cfg=nanite_cfg,
        db_path=config.unreal_db_path,
    )

    cleanup_script = generate_unreal_cleanup_script(
        output_dir,
        config.unreal_project_path,
        dry_run=True,
    )

    logger.info("Generated Unreal scripts: %s, %s", import_script, cleanup_script)

    # DynamicWind import script (runs before PVE to apply wind data first)
    if config.unreal_generate_wind_data:
        from growpy.io.unreal.wind_import_script import generate_wind_import_script

        wind_script = generate_wind_import_script(
            output_dir=output_dir / "unreal_scripts",
            forest_root=output_dir,
            import_base=config.unreal_pve_import_base,
        )
        logger.info("Generated DynamicWind import script: %s", wind_script)

    if config.unreal_generate_pve_presets:
        from growpy.io.unreal.pve_foliage_data import generate_all_foliage_data
        from growpy.io.unreal.pve_import_script import (
            build_species_twig_map,
            generate_pve_preset_import_script,
        )

        twig_map = build_species_twig_map()
        foliage_files = generate_all_foliage_data(
            output_dir,
            import_base=config.unreal_pve_import_base,
            species_twig_map=twig_map,
        )
        logger.info("Generated %d FoliageData.json files", len(foliage_files))
        pve_script = generate_pve_preset_import_script(
            output_dir=output_dir / "unreal_scripts",
            forest_root=output_dir,
            import_base=config.unreal_pve_import_base,
            species_twig_map=twig_map,
        )
        logger.info("Generated PVE preset import script: %s", pve_script)

        from growpy.io.unreal.pve_graph_script import generate_pve_graph_script

        pve_graph_script = generate_pve_graph_script(
            output_dir=output_dir / "unreal_scripts",
            forest_root=output_dir,
            import_base=config.unreal_pve_import_base,
            species_twig_map=twig_map,
        )
        logger.info("Generated PVE graph builder script: %s", pve_graph_script)

    # Nanite voxelize script (run after UE restart for best VRAM headroom)
    if config.unreal_import_to_unreal and config.unreal_voxelization:
        from growpy.io.unreal.nanite_voxelize_script import (
            generate_nanite_voxelize_script,
        )

        voxelize_script = generate_nanite_voxelize_script(
            output_dir=output_dir / "unreal_scripts",
            import_path=config.unreal_project_path,
        )
        logger.info("Generated Nanite voxelize script: %s", voxelize_script)
