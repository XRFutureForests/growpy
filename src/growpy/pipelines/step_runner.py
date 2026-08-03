"""Step subprocess runner for the dataset pipeline.

Handles subprocess invocation for all four pipeline steps:
- Steps 1-3: single call per step. Config-driven by default (--dataset, no
  CSV); an explicit --csv overrides that.
- Step 4: one subprocess per species, selected by --species. The child
  rebuilds its own job rows from config (see dataset_csv_planner), so no
  CSV is passed across the process boundary. Optional parallel execution
  via ProcessPoolExecutor.

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


def _build_step123_command(
    step: int,
    dataset_mode: bool,
    csv_path: Path | None = None,
    extra_args: list | None = None,
    verbose: bool = False,
) -> list:
    """Build the command for step 1, 2, or 3.

    dataset_mode selects config-driven species (--dataset flag, no CSV file
    crosses the process boundary); otherwise csv_path is passed via --csv.
    """
    script = STEP_SCRIPTS[step]
    cmd = [sys.executable, str(script)]
    if dataset_mode:
        cmd.append("--dataset")
    else:
        cmd.extend(["--csv", str(csv_path)])
    if verbose:
        cmd.append("--verbose")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def run_step123(
    step: int,
    csv_path: Path | None = None,
    dataset_mode: bool = False,
    dry_run: bool = False,
    extra_args: list | None = None,
    verbose: bool = False,
) -> bool:
    """Run a single step (1, 2, or 3) as a subprocess.

    dataset_mode=True runs config-driven species selection (--dataset, no CSV);
    otherwise csv_path is required and passed via --csv.

    Returns True on success (or dry_run).
    """
    from pathlib import Path as PathlibPath

    script = STEP_SCRIPTS[step]
    cmd = _build_step123_command(step, dataset_mode, csv_path, extra_args, verbose)
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
    species_name: str,
    max_height: float = 0,
    skip_unreal_scripts: bool = False,
    verbose: bool = False,
    pve: bool | None = None,
    wind: bool | None = None,
    previews: bool | None = None,
    icons: bool | None = None,
) -> list:
    """Build the generate_forest.py command for one dataset species.

    Passes only what the child cannot derive. The child builds every job row
    for the species itself from config, so there is no CSV to hand over and
    no --export-trees filter to compute: it exports all the rows it built.

    pve/wind/previews/icons are tri-state (None = use TOML default) and are
    only appended when explicitly set, mirroring resolve()'s CLI-over-TOML
    semantics.
    """
    cmd = [sys.executable, str(STEP_SCRIPTS[4]), "--species", species_name]
    if max_height > 0:
        cmd.extend(["--max-height", str(max_height)])
    if skip_unreal_scripts:
        cmd.append("--no-unreal-scripts")
    if verbose:
        cmd.append("--verbose")
    if pve is not None:
        cmd.append("--pve" if pve else "--no-pve")
    if wind is not None:
        cmd.append("--wind" if wind else "--no-wind")
    if previews is not None:
        cmd.append("--previews" if previews else "--no-previews")
    if icons is not None:
        cmd.append("--icons" if icons else "--no-icons")
    return cmd


def run_species_step4(
    species_name: str,
    dry_run: bool = False,
    max_height: float = 0,
    skip_unreal_scripts: bool = False,
    verbose: bool = False,
    pve: bool | None = None,
    wind: bool | None = None,
    previews: bool | None = None,
    icons: bool | None = None,
) -> bool:
    """Run generate_forest.py for one dataset species.

    Returns True on success (or dry_run).
    """
    from pathlib import Path as PathlibPath

    cmd = _build_step4_command(
        species_name,
        max_height,
        skip_unreal_scripts,
        verbose,
        pve,
        wind,
        previews,
        icons,
    )

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
    species_name, max_height, verbose, pve, wind, previews, icons = args
    t0 = time.monotonic()
    ok = run_species_step4(
        species_name,
        max_height=max_height,
        skip_unreal_scripts=True,
        verbose=verbose,
        pve=pve,
        wind=wind,
        previews=previews,
        icons=icons,
    )
    elapsed = time.monotonic() - t0
    return species_name, ok, elapsed


def run_parallel_step4(
    species_list: list,
    workers: int,
    max_height: float,
    verbose: bool = False,
    pve: bool | None = None,
    wind: bool | None = None,
    previews: bool | None = None,
    icons: bool | None = None,
) -> tuple[list, dict]:
    """Run step 4 for multiple species in parallel.

    Returns (failed species names, elapsed seconds per species).
    """
    failed = []
    elapsed_by_species: dict = {}

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _run_species_worker,
                (species, max_height, verbose, pve, wind, previews, icons),
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
