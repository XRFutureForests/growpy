"""Regrow one species for structure scoring: several seeds, unthinned, optional preset knobs.

    growpy-structure-regrow "European Beech" --arm baseline --seeds 512,1,2,3,4
    growpy-structure-regrow "European Beech" --arm btm0.1 --set bend_twig_mass=0.1 \\
        --seeds 512,1,2 --max-height 20
    growpy-structure-regrow "European Beech" --arm baseline --score-only

One arm = one species, one set of preset knob values, N seeds. Each seed is a full step 4
run (``growpy-dataset-pipeline --steps 4``) with its own copied config dir
(``GROWPY_CONFIG``) that sets exactly:

* ``[general] random_seed`` = the seed; the per-species reseed table removed;
  ``output_dir`` = the seed's own folder (the shared ``data/output/forest`` is untouched);
* ``[export] mode = "growth_json_only"``: the PVE growth JSON is the only output;
* ``[unreal.growth_data_json]`` ``min_branch_radius_fraction`` and
  ``min_point_spacing`` 0, every per-species thinning table removed: the score must see
  the skeleton Grove grew, not the export cut (which biases lateral lengths up and
  conifer crown ratios down).

The radius set stays the production one unless ``--radii`` is given: Grove's RNG is
global, so another radius set changes every radius's draws (A28 in
``sweep_surround_density``).

Preset knobs (``--set key=value``, shallow, as ``config/preset_patches.json``) go into a
sandbox project root (``GROWPY_PROJECT_ROOT``): ``data/assets/presets`` is copied and
patched there, everything else under ``data/`` is a junction to the real folders. Step 4
reads the baked seed JSON, so this is the only way to vary a preset key without touching
the shared ``data/assets`` (A19).

Layout under ``data/output/regrow/<species>/<arm>/``: ``arm.json`` and
``seed<k>/{config,forest,run.log}``. Scoring lives in the tree-structure repo since
the split of 2026-10-28: run ``tree-structure-score-arm <arm dir>`` in its env, which
standardises the seeds, writes ``descriptors/`` and gates into ``gate/``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from growpy.tools.sweep_surround_density import _set_scalar, _strip_tables

REPO = Path(__file__).resolve().parents[3]
THINNING_TABLES = (
    "unreal.growth_data_json.min_branch_radius_fraction_per_species",
    "unreal.growth_data_json.min_point_spacing_per_species",
    "unreal.growth_data_json.crown_base_cut_margin_per_species",
)


def species_key(species: str) -> str:
    return species.lower().replace(" ", "_").replace("-", "_")


def _parse_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def build_seed_config(
    cfg: Path, seed: int, out_dir: Path, radii: list[float] | None
) -> None:
    if cfg.exists():
        shutil.rmtree(cfg)
    shutil.copytree(REPO / "config", cfg)

    general = cfg / "general.toml"
    text = _strip_tables(
        general.read_text(encoding="utf-8"), ("general.random_seed_per_species",)
    )
    text = _set_scalar(text, "random_seed", str(seed))
    text = _set_scalar(text, "output_dir", '"' + out_dir.as_posix() + '"')
    general.write_text(text, encoding="utf-8")

    forest = cfg / "forest.toml"
    text = _set_scalar(forest.read_text(encoding="utf-8"), "mode", '"growth_json_only"')
    forest.write_text(text, encoding="utf-8")

    unreal = cfg / "unreal.toml"
    text = _strip_tables(unreal.read_text(encoding="utf-8"), THINNING_TABLES)
    text = _set_scalar(text, "min_branch_radius_fraction", "0.0")
    text = _set_scalar(text, "min_point_spacing", "0.0")
    unreal.write_text(text, encoding="utf-8")

    if radii:
        surround = cfg / "surround.toml"
        text = _set_scalar(
            surround.read_text(encoding="utf-8"),
            "radii",
            "[" + ", ".join(f"{r:g}" for r in radii) + "]",
        )
        surround.write_text(text, encoding="utf-8")


def verify_seed_config(cfg: Path, seed: int, out_dir: Path, root: Path) -> dict:
    """Read the seed's config back through growpy itself and refuse to run if it is not
    what was meant (A35 in ``sweep_surround_density``: a sweep once edited the wrong
    table and produced plausible nonsense)."""
    script = (
        "import json\n"
        "from growpy.config import get_config\n"
        "from growpy.pipelines.forest_stages import _growth_data_json_settings\n"
        "c = get_config()\n"
        "s = _growth_data_json_settings()\n"
        "print(json.dumps({'seed': c.random_seed,\n"
        "  'per_species_seed': c.random_seed_per_species,\n"
        "  'mode': c.export_mode, 'output_dir': str(c.output_dir),\n"
        "  'radii': c.surround_radii,\n"
        "  'fraction': s.get('min_branch_radius_fraction'),\n"
        "  'spacing': s.get('min_point_spacing'),\n"
        "  'tables': [k for k in s if k.endswith('_per_species') and s[k]]}))\n"
    )
    env = dict(os.environ, GROWPY_CONFIG=str(cfg), GROWPY_PROJECT_ROOT=str(root))
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    if not lines:
        raise SystemExit(f"cannot read back {cfg}:\n{proc.stdout}\n{proc.stderr}")
    got = json.loads(lines[-1])
    problems = []
    if got["seed"] != seed or got["per_species_seed"]:
        problems.append(f"seed {got['seed']} / per species {got['per_species_seed']}")
    if got["mode"] != "growth_json_only":
        problems.append(f"export mode {got['mode']}")
    if Path(got["output_dir"]).resolve() != out_dir.resolve():
        problems.append(f"output_dir {got['output_dir']}")
    if got["fraction"] or got["spacing"] or got["tables"]:
        problems.append(
            f"thinning on: fraction {got['fraction']}, spacing {got['spacing']}, "
            f"tables {got['tables']}"
        )
    if problems:
        raise SystemExit(f"{cfg} is wrong:\n  " + "\n  ".join(problems))
    return got


def _link(target: Path, link: Path) -> None:
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def remove_sandbox(root: Path) -> None:
    """Unlink the junctions first (never their targets: ``data/input`` is tracked), then
    delete what is left, which is only the copied presets."""
    for parent in (root / "data", root / "data" / "assets"):
        if parent.is_dir():
            for entry in parent.iterdir():
                if entry.is_junction() or entry.is_symlink():
                    os.rmdir(entry) if os.name == "nt" else entry.unlink()
    if root.exists():
        shutil.rmtree(root)


def build_sandbox(root: Path, species: str, overrides: dict) -> dict:
    """A project root whose presets carry ``overrides``; returns before/after values."""
    remove_sandbox(root)
    data = REPO / "data"
    (root / "data" / "assets").mkdir(parents=True)
    for entry in data.iterdir():
        if entry.is_dir() and entry.name not in ("assets", "output", "tmp"):
            _link(entry, root / "data" / entry.name)
    for entry in (data / "assets").iterdir():
        if entry.is_dir() and entry.name != "presets":
            _link(entry, root / "data" / "assets" / entry.name)
    presets = root / "data" / "assets" / "presets"
    shutil.copytree(data / "assets" / "presets", presets)
    path = presets / f"{species_key(species)}.seed.json"
    preset = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in overrides if k not in preset]
    if missing:
        raise SystemExit(
            f"{path.name} has no key(s) {missing}: refusing to add new ones"
        )
    before = {k: preset[k] for k in overrides}
    preset.update(overrides)
    path.write_text(json.dumps(preset, indent=2), encoding="utf-8")
    return {"before": before, "after": overrides}


def run_seed(species: str, cfg: Path, root: Path, log: Path, max_height: float | None):
    env = dict(os.environ, GROWPY_CONFIG=str(cfg), GROWPY_PROJECT_ROOT=str(root))
    cmd = [
        sys.executable, "-m", "growpy.cli.dataset_pipeline",
        "--species", species, "--steps", "4", "--workers", "1",
        "--no-icons", "--no-previews", "--no-export-control", "--no-pve", "--no-wind",
        "-v",
        *(["--max-height", f"{max_height:g}"] if max_height else []),
    ]  # fmt: skip
    started = time.time()
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO, env=env
        )
    return proc.returncode, time.time() - started


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("species", help='common name, e.g. "European Beech"')
    parser.add_argument("--arm", required=True, help="arm name (folder)")
    parser.add_argument("--seeds", default="512,1,2,3,4")
    parser.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", help="preset knob"
    )
    parser.add_argument("--radii", help="surround radii, e.g. 7 (default: production)")
    parser.add_argument("--max-height", type=float, help="export cap in metres")
    parser.add_argument("--workers", type=int, default=1, help="seeds run in parallel")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=REPO / "data" / "output" / "regrow",
    )
    parser.add_argument("--dry-run", action="store_true", help="configs only, no run")
    args = parser.parse_args(argv)

    seeds = [int(s) for s in args.seeds.split(",")]
    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        overrides[key.strip()] = _parse_value(value.strip())
    radii = [float(r) for r in args.radii.split(",")] if args.radii else None
    arm_dir = (args.out_root / species_key(args.species) / args.arm).resolve()
    seed_dirs = [arm_dir / f"seed{s}" for s in seeds]

    arm_dir.mkdir(parents=True, exist_ok=True)
    root = arm_dir / "root" if overrides else REPO
    knobs = build_sandbox(root, args.species, overrides) if overrides else {}
    for seed, seed_dir in zip(seeds, seed_dirs, strict=True):
        build_seed_config(seed_dir / "config", seed, seed_dir / "forest", radii)
        got = verify_seed_config(
            seed_dir / "config", seed, seed_dir / "forest", root
        )
        print(f"seed {seed}: {got}")
    record = {
        "species": args.species,
        "arm": args.arm,
        "seeds": seeds,
        "preset_overrides": knobs,
        "radii": radii or "production",
        "max_height": args.max_height,
        "started": datetime.now().isoformat(timespec="seconds"),
    }
    (arm_dir / "arm.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    if args.dry_run:
        return 0

    def one(pair):
        seed, seed_dir = pair
        if (seed_dir / "forest").exists():
            shutil.rmtree(seed_dir / "forest")
        code, secs = run_seed(
            args.species, seed_dir / "config", root, seed_dir / "run.log",
            args.max_height,
        )  # fmt: skip
        print(f"seed {seed}: exit {code} after {secs / 60:.1f} min")
        return seed, code, secs

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(one, zip(seeds, seed_dirs, strict=True)))
    record["runs"] = [
        {"seed": s, "exit": c, "minutes": round(t / 60, 1)} for s, c, t in results
    ]
    record["finished"] = datetime.now().isoformat(timespec="seconds")
    (arm_dir / "arm.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    failed = [s for s, c, _ in results if c != 0]
    if failed:
        print(f"seeds failed: {failed} (see seed<k>/run.log)")

    print(f"score it: tree-structure-score-arm {arm_dir}  (tree-structure env)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
