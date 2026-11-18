"""Tree catalog manifest (XRFF-678): a generated record of every catalog tree asset.

    growpy-tree-catalog build --plan <unreal_scripts dir> [--plan ...]
                              [--bones bones.json]
                              [--scores target_score.csv ...]
    growpy-tree-catalog check

``build`` reads the PVE plan manifests (``pve_export_manifest.json``) and writes one
entry per tree asset: structure (generator, growth JSON, stand radius, height, DBH),
twig set, bark material, variant, the exported meshes, twig count and leaf area, bones
(from an editor dump, ``{"SK_<Species>_<tree>": 2307}``) and the target-sheet result
(``tree-structure-target-sheet score`` CSVs). A later plan of the same tree replaces the
earlier one, so pass the plans oldest first.

Each entry also names its trunk and branch bark as material catalog ids and its
structure settings (the species' ``config/preset_patches.json`` entry, since when it
holds, and when the growth JSON was written).

``build`` also writes ``catalog_index.toml`` beside the manifest: one row per catalog
component (structure, twig, spray, compound, material, tree) with source, licence,
path, cost fields where known and status.

``check`` lists every asset with a missing entry or a pass/fail trait outside the real
p25-p75 of its height row, and every tree grown before its structure settings last
changed (STALE). It exits 1 when anything is missing, not for traits: an
out-of-target tree is a finding, not a broken catalog.

Owner scope (2026-11-12): the manifest is a record; the export reads it only once bark
stages by DBH exist. It lives in data/input/, not config/, because growpy merges every
config/*.toml into its settings.
"""

import argparse
import csv
import json
import logging
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

from growpy.io.unreal.pve_graph_plan import intake_dbh, young_bark
from growpy.tools.material_intake import CATALOG as MATERIAL_CATALOG
from growpy.tools.material_intake import _toml_value
from growpy.tools.twig_catalog import ASSETS as TWIG_ASSETS
from growpy.tools.twig_catalog import ROOT as TWIG_ROOT

logger = logging.getLogger(__name__)

MANIFEST = Path("data/input/tree_catalog.toml")
PRESET_PATCHES = Path("config/preset_patches.json")
FOREST = Path("data/output/forest")
HOLDS = Path("data/input/release_holds.toml")  # species = "<release>: why"
PASS_FAIL = (
    "dbh_m",
    "crown_base_m",
    "crown_radius_m",
)  # owner Q57: height only picks the row
REQUIRED = ("growth_json", "twig_set", "material", "mesh")


def plan_rows(plan_dir: Path) -> list[dict]:
    """Per-mesh rows of one plan, each with its graph's bark material."""
    manifest = json.loads(
        (plan_dir / "pve_export_manifest.json").read_text(encoding="utf-8")
    )
    rows = []
    for graph in manifest.get("graphs", []):
        for mesh in graph.get("meshes", []):
            rows.append(
                {
                    **mesh,
                    "bark_material": graph.get("bark_material"),
                    "plan": plan_dir.name,
                }
            )
    return rows


def material_ids(catalog: Path = MATERIAL_CATALOG) -> dict[str, str]:
    """Material instance path -> material catalog id (intake entries only)."""
    if not catalog.is_file():
        return {}
    with catalog.open("rb") as fh:
        materials = tomllib.load(fh).get("materials", {})
    return {m["instance"]: mid for mid, m in materials.items() if m.get("instance")}


def read_scores(paths) -> dict[str, dict[str, dict]]:
    """Growth JSON name -> trait -> {value, p25, p75, inside}, from score CSVs."""
    scores: dict[str, dict[str, dict]] = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["trait"] not in PASS_FAIL:
                    continue
                scores.setdefault(row["tree"], {})[row["trait"]] = {
                    "value": round(float(row["value"]), 3),
                    "p25": round(float(row["p25"]), 3),
                    "p75": round(float(row["p75"]), 3),
                    "inside": row["inside"] == "True",
                    "n": int(row["n"]),
                }
    return scores


def _patches(text: str) -> dict[str, dict]:
    def strip(d):
        return {k: v for k, v in d.items() if not k.startswith("_")}

    return {sp: strip(p) for sp, p in strip(json.loads(text)).items()}


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def structure_settings(path: Path = PRESET_PATCHES) -> dict[str, tuple[dict, str]]:
    """Species -> (its preset patch now, since when it has been that patch).

    The catalog trees are grown from the Grove seed presets plus these tracked patches,
    so a tree grown before its species' patch last changed is stale. "Since" is the
    oldest commit in the unbroken run of commits that carry today's entry, or the
    file's own time for an uncommitted edit or a file outside git.
    shortcut: walks the committed history of this one file (a rename loses it);
    upgrade if settings ever move out of preset_patches.json.
    """
    current = _patches(path.read_text(encoding="utf-8"))
    since: dict[str, str] = {sp: _iso(path.stat().st_mtime) for sp in current}
    log = subprocess.run(
        ["git", "log", "--format=%H %cI", "--", path.name],
        capture_output=True, text=True, cwd=path.parent,
    )  # fmt: skip
    if log.returncode != 0:  # not in git: only the file's own time is known
        return {sp: (p, since[sp]) for sp, p in current.items()}
    open_ = set(current)
    for line in log.stdout.splitlines():
        sha, date = line.split()
        old = subprocess.run(
            ["git", "show", f"{sha}:./{path.name}"],
            capture_output=True, text=True, cwd=path.parent,
        )  # fmt: skip
        if old.returncode != 0:
            break
        old_patches = _patches(old.stdout)
        for sp in list(open_):
            if old_patches.get(sp) == current[sp]:
                since[sp] = date
            else:
                open_.discard(sp)
        if not open_:
            break
    return {sp: (current[sp], since[sp]) for sp in current}


def bark_sources(species: str, materials: dict[str, str]):
    """(trunk, branch, calibration) of a species: material catalog ids, "grove" for
    the Grove map, or a UE path when the source is not an intake entry."""
    from growpy.config.paths import get_species_growth_habit
    from growpy.config.pve_calibration import BarkAtlasStrip, load_pve_calibration

    try:
        cal = load_pve_calibration().for_species(
            species, get_species_growth_habit(species)
        )
    except (KeyError, FileNotFoundError, ValueError):
        return None
    if cal.bark_trunk_source is not None:
        trunk = cal.bark_trunk_source
        if isinstance(trunk, BarkAtlasStrip):
            trunk = materials.get(trunk.material, trunk.material)
        return str(trunk), str(cal.bark_branch_source), cal
    source = cal.bark_material_source
    textured = source and cal.bark_source_textures
    bark = materials.get(source, source) if textured else "grove"
    return bark, bark, cal


def twig_entries_for(species: str, palette: str | None) -> list[str]:
    """Twig catalog ids (XRFF-684) this tree wears with its PVE palette."""
    from growpy.tools.twig_catalog import entries_for

    return entries_for(species, palette) if palette else []


def entry(
    row: dict,
    materials: dict[str, str],
    bones: dict,
    scores: dict,
    settings: dict | None = None,
    barks: dict | None = None,
) -> dict:
    """One manifest entry from a plan row."""
    growth = Path(row["growth_json"])
    bark = row.get("bark_material")
    patch, since = (settings or {}).get(row["species"], (None, None))
    trunk, branch, cal = (barks or {}).get(row["species"]) or (None, None, None)
    if cal is not None and young_bark(cal, float(row["dbh_cm"]), intake_dbh()):
        trunk = cal.bark_young_source
    out = {
        "species": row["species"],
        "tree_id": row["tree_id"],
        "radius": int(row["tree_id"][1:3]),
        "height_m": round(float(row["height_m"]), 2),
        "dbh_cm": round(float(row["dbh_cm"]), 1),
        "generator": "grove",
        "growth_json": growth.as_posix(),
        "twig_set": row.get("palette"),
        "twig_entries": twig_entries_for(row["species"], row.get("palette")) or None,
        "material": materials.get(bark, bark),
        "bark_trunk": trunk,
        "bark_branch": branch,
        "structure_settings": patch,
        "settings_since": since,
        "grown": grown_at(growth),
        "variant": "summer",
        "mesh": row.get("asset"),
        "static_mesh": row.get("static_asset"),
        "twigs": row.get("predicted_instances"),
        "leaf_area_m2": round(float(row.get("predicted_m2", 0.0)), 1),
        "leaf_area_target_m2": round(float(row.get("target_m2", 0.0)), 1),
        "plan": row["plan"],
    }
    name = row.get("mesh_name") or Path(row.get("asset", "")).name
    if name in bones:
        out["bones"] = int(bones[name])
    if growth.name in scores:
        out["target"] = scores[growth.name]
    return {k: v for k, v in out.items() if v is not None}


def build(
    plans,
    bones_path=None,
    score_paths=(),
    out: Path = MANIFEST,
    patches: Path = PRESET_PATCHES,
    holds: Path = HOLDS,
    twigs: Path = TWIG_ROOT,
    forest: Path = FOREST,
) -> dict:
    """Write the manifest; a later plan of the same tree replaces an earlier one.

    Also writes ``catalog_index.toml`` beside ``out`` (see :func:`index_rows`).
    """
    materials = material_ids()
    bones = (
        json.loads(Path(bones_path).read_text(encoding="utf-8")) if bones_path else {}
    )
    scores = read_scores(score_paths)
    settings = structure_settings(patches) if patches.is_file() else {}
    held = tomllib.loads(holds.read_text(encoding="utf-8")) if holds.is_file() else {}
    barks: dict[str, tuple | None] = {}
    trees: dict[str, dict] = {}
    for plan in plans:
        for row in plan_rows(Path(plan)):
            if row["species"] not in barks:
                barks[row["species"]] = bark_sources(row["species"], materials)
            trees[f"{row['species']}.{row['tree_id']}"] = entry(
                row, materials, bones, scores, settings, barks
            )
            if row["species"] in held:
                trees[f"{row['species']}.{row['tree_id']}"]["release_hold"] = held[
                    row["species"]
                ]
    if bones:
        # the bones dump lists every mesh the UE catalog holds: a planned tree
        # without one was never exported or was dropped (e.g. r00), so it is
        # not a catalog asset
        dropped = sorted(k for k, t in trees.items() if "bones" not in t)
        for key in dropped:
            del trees[key]
        if dropped:
            print(f"{len(dropped)} planned trees not in the UE catalog: {dropped}")
    lines = [
        "# GENERATED by growpy-tree-catalog build -- do not edit; re-plan, export,",
        "# then rebuild. One entry per catalog tree asset (XRFF-678): structure,",
        "# twig set, bark material, variant, exported meshes, twigs, bones and the",
        "# target-sheet result. bark_trunk/bark_branch: material catalog ids (or",
        "# grove) from pve_calibration.toml at build time -- a species exported",
        "# before its bark source changed shows the new source until re-export.",
        "# structure_settings: the species' preset_patches.json entry; check flags",
        "# a tree grown before that entry last changed (STALE).",
        "# release_hold: the species is held out of that release",
        "# (data/input/release_holds.toml); the asset is not shipped from it.",
        "",
    ]
    for key in sorted(trees):
        tree = dict(trees[key])
        target = tree.pop("target", None)
        lines.append(f"[trees.{key}]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in tree.items()]
        for trait, result in (target or {}).items():
            lines.append(f"target.{trait} = {_toml_value(result)}")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    rows = index_rows(trees, twigs, MATERIAL_CATALOG, forest)
    write_index(rows, out.with_name("catalog_index.toml"))
    return trees


def _disk_mb(path: Path) -> float | None:
    return round(path.stat().st_size / 1e6, 3) if path.is_file() else None


def index_rows(
    trees: dict[str, dict],
    twigs: Path = TWIG_ROOT,
    materials_catalog: Path = MATERIAL_CATALOG,
    forest: Path = FOREST,
    assets: Path = TWIG_ASSETS,
) -> list[dict]:
    """One row per catalog component: structures, twig parts, materials, trees."""
    rows = []
    for growth in sorted(forest.glob("*/r??/*_full_growth_data.json")):
        rows.append({
            "kind": "structure",
            "id": growth.name.removesuffix("_full_growth_data.json"),
            "species": growth.parent.parent.name, "source": "grove",
            "licence": "own (Grove growth)", "path": growth.as_posix(),
            "disk_mb": _disk_mb(growth),
        })  # fmt: skip
    for entry_toml in sorted(twigs.glob("*/twig.toml")):
        e = tomllib.loads(entry_toml.read_text(encoding="utf-8"))
        kind = e.get("part_kind")
        ref = str(e.get("source_ref", ""))
        on_disk = not ref.startswith(("/Game/", "pack:"))
        rows.append({
            "kind": kind if kind in ("spray", "compound") else "twig",
            "id": e.get("id", entry_toml.parent.name), "species": e.get("species"),
            "source": e.get("source"), "licence": e.get("licence"), "path": ref,
            "source_faces": e.get("faces"),
            "nanite_triangles": e.get("nanite_triangles"),
            "textures": e.get("textures"),
            "disk_mb": _disk_mb(assets / ref) if on_disk and ref else None,
            "status": e.get("status"),
        })  # fmt: skip
    if materials_catalog.is_file():
        materials = tomllib.loads(materials_catalog.read_text(encoding="utf-8"))
        for mid, m in sorted(materials.get("materials", {}).items()):
            rows.append({
                "kind": "material", "id": mid, "species": m.get("species"),
                "source": m.get("source"), "licence": m.get("licence"),
                "path": m.get("instance"),
            })  # fmt: skip
    for key, t in sorted(trees.items()):
        hold = t.get("release_hold")
        rows.append({
            "kind": "tree", "id": key, "species": t.get("species"), "source": "own",
            "licence": "own (parts and bark: see their rows)", "path": t.get("mesh"),
            "bones": t.get("bones"),
            "status": f"held {hold.split(':', 1)[0]}" if hold else None,
        })  # fmt: skip
    return [{k: v for k, v in r.items() if v is not None} for r in rows]


def write_index(rows: list[dict], out: Path) -> Path:
    lines = [
        "# GENERATED by growpy-tree-catalog build -- never edit. One row per catalog",
        "# component (kind: structure | twig | spray | compound | material | tree)",
        "# from the twig entries, the material intake catalog, the tree manifest and",
        "# a scan of data/output/forest/<species>/r??/ (owner 2026-11-18).",
        "",
    ]
    for row in rows:
        lines.append("[[components]]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in row.items()]
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def grown_at(growth: Path) -> str | None:
    """When the tree was grown: the ``.tamf.json`` Grove writes beside the growth JSON at growth time. Post-passes
    (DBH rescale, re-cuts) rewrite the growth JSON itself, so its own time says nothing about the growth: on
    2026-11-17 it hid that the whole spruce and Douglas ladders predate their preset tunes."""
    tamf = growth.with_name(growth.name.replace("_growth_data.json", ".tamf.json"))
    for f in (tamf, growth):
        if f.is_file():
            return _iso(f.stat().st_mtime)
    return None


def grown_before(grown: str, since: str) -> bool:
    return datetime.fromisoformat(grown) < datetime.fromisoformat(since)


def check(manifest: Path = MANIFEST) -> tuple[list[str], list[str]]:
    """(missing entries, out-of-target traits), one line each."""
    with manifest.open("rb") as fh:
        species = tomllib.load(fh).get("trees", {})
    missing, out_of_target = [], []
    for sp, trees in sorted(species.items()):
        for tree_id, tree in sorted(trees.items()):
            key = f"{sp}.{tree_id}"
            gaps = [k for k in REQUIRED if not tree.get(k)]
            if tree.get("growth_json") and not Path(tree["growth_json"]).is_file():
                gaps.append("growth_json file")
            if "bones" not in tree:
                gaps.append("bones")
            if gaps:
                missing.append(f"{key}: no {', '.join(gaps)}")
            grown, since = tree.get("grown"), tree.get("settings_since")
            if grown and since and grown_before(grown, since):
                out_of_target.append(
                    f"{key}: STALE, grown {grown[:10]} before its structure "
                    f"settings changed {since[:10]}"
                )
            target = tree.get("target")
            if not target:
                out_of_target.append(f"{key}: no target-sheet result")
                continue
            for trait in PASS_FAIL:
                r = target.get(trait)
                if r and not r["inside"]:
                    out_of_target.append(
                        f"{key}: {trait} {r['value']} outside [{r['p25']}, {r['p75']}]"
                    )
    return missing, out_of_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="write the manifest from plan folders")
    b.add_argument(
        "--plan",
        action="append",
        required=True,
        type=Path,
        help="a plan folder; oldest first",
    )
    b.add_argument("--bones", type=Path, help="editor dump {mesh name: bones}")
    b.add_argument(
        "--scores",
        action="append",
        default=[],
        type=Path,
        help="target-sheet score CSV",
    )
    b.add_argument("--out", type=Path, default=MANIFEST)
    c = sub.add_parser("check", help="list missing entries and out-of-target traits")
    c.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.command == "build":
        trees = build(args.plan, args.bones, args.scores, args.out)
        logger.info("%d tree assets -> %s", len(trees), args.out)
        return 0
    missing, out_of_target = check(args.manifest)
    for line in missing:
        logger.info("MISSING %s", line)
    for line in out_of_target:
        logger.info("TARGET  %s", line)
    logger.info(
        "%d with missing entries, %d out-of-target findings",
        len(missing),
        len(out_of_target),
    )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
