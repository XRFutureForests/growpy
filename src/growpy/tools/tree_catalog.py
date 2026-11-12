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

``check`` lists every asset with a missing entry or a pass/fail trait outside the real
p25-p75 of its height row. It exits 1 when anything is missing, not for traits: an
out-of-target tree is a finding, not a broken catalog.

Owner scope (2026-11-12): the manifest is a record; the export reads it only once bark
stages by DBH exist. It lives in data/input/, not config/, because growpy merges every
config/*.toml into its settings.
"""

import argparse
import csv
import json
import logging
import sys
import tomllib
from pathlib import Path

from growpy.tools.material_intake import CATALOG as MATERIAL_CATALOG
from growpy.tools.material_intake import _toml_value

logger = logging.getLogger(__name__)

MANIFEST = Path("data/input/tree_catalog.toml")
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


def entry(row: dict, materials: dict[str, str], bones: dict, scores: dict) -> dict:
    """One manifest entry from a plan row."""
    growth = Path(row["growth_json"])
    bark = row.get("bark_material")
    out = {
        "species": row["species"],
        "tree_id": row["tree_id"],
        "radius": int(row["tree_id"][1:3]),
        "height_m": round(float(row["height_m"]), 2),
        "dbh_cm": round(float(row["dbh_cm"]), 1),
        "generator": "grove",
        "growth_json": growth.as_posix(),
        "twig_set": row.get("palette"),
        "material": materials.get(bark, bark),
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


def build(plans, bones_path=None, score_paths=(), out: Path = MANIFEST) -> dict:
    """Write the manifest; a later plan of the same tree replaces an earlier one."""
    materials = material_ids()
    bones = (
        json.loads(Path(bones_path).read_text(encoding="utf-8")) if bones_path else {}
    )
    scores = read_scores(score_paths)
    trees: dict[str, dict] = {}
    for plan in plans:
        for row in plan_rows(Path(plan)):
            trees[f"{row['species']}.{row['tree_id']}"] = entry(
                row, materials, bones, scores
            )
    lines = [
        "# GENERATED by growpy-tree-catalog build -- do not edit; re-plan, export,",
        "# then rebuild. One entry per catalog tree asset (XRFF-678): structure,",
        "# twig set, bark material, variant, exported meshes, twigs, bones and the",
        "# target-sheet result.",
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
    return trees


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
