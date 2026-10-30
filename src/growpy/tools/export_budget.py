"""Export budget of the PVE tree catalog and its skinned cost per site x scenario step.

    growpy-export-budget --twin-cache <XRFF_Twin>/Saved/TwinCache --out-dir <dir>
    growpy-export-budget --twin-cache <dir> --bones <bones.json> --sites ECOSENSE \\
        --measured ECOSENSE:10:2025=52.9 --floor-bones 2900 --out-dir <dir>

Reads files only; it never needs the editor (XRFF-592, extends XRFF-454).

``export_budget_trees.csv``, one row per catalog mesh. Columns and their source:

- ``bones``: the asset registry ``Bones`` tag of the skeletal mesh, dumped by an
  editor script to ``--bones`` (``{"SK_<Species>_r07_h25m": "9742", ...}``);
  ``bone_reduction``: ``bone_reduction_strength_per_species`` in
  ``config/pve_calibration.toml`` (what the graphs were built with);
- ``points``, ``branches``: the growth JSON (points = bones before PVE's
  resampling and Bone Reduction; polylines = branches that carry bones, because
  Bone Reduction keeps at least one bone per run; within 3 % of the bone tips
  counted on the meshes, 2026-10-26);
- ``parts_plan``, ``unique_parts``, ``capped``: the PVE plan manifest
  (``pve_export_manifest.json``: predicted foliage instances and the palette).
  ``plan_current`` is False when the growth JSON was regrown after the plan;
  then the plan's counts are left empty, not guessed;
- ``part_tris_min``/``max``: triangles of the palette parts, from the twig USDs
  under ``Instances/`` (the source of the palette meshes);
  ``tris_lo``/``tris_hi`` = ``parts_plan`` x those: an estimate band of the
  instanced foliage triangles, not a count.

``export_budget_scenarios.csv``, one row per site x scenario x year: the trees
``PCG_TreeData`` places from the twin cache (``TreeData[_<code>]Cache.json``,
the rows the editor fetched), joined to the catalog by the graph's own rule
(stage = round(height / 5) x 5 clamped 5..45, radius class 7 when the nearest
neighbour is within 8.5 m else 10, nearest cell of the species, European Larch
-> Douglas Fir). Dead trees (status 4) are drawn as a static twin
(``PCG_Trees`` ``DeadFilter``) and cost no bones; status 5-8 are not placed.
Cost: 16 x bones per distinct mesh (Dynamic Wind, 8 slices x current and
previous) against 4,194,302 slots. ``switch_pct``: worst case of a switch into
this step from any other year of the scenario or the same year of another
scenario, both allocations counted in full; ``switch_union_pct`` counts a mesh
the two steps share once (which one the engine does is not measured yet).
Gate: the draft budget (65k bones, 30 meshes per step) and the buffer.
``export_budget_meshes.csv`` lists the meshes per step.

Not readable without UE (left out, never estimated): the foliage instance count
of the exported mesh, its triangle count after the Nanite build, part sizes, the
floor plants' bones (``--floor-bones`` takes a measured value). Hub:
``05-PRESENTATION-TIER/tree-asset-budget-2026-10``.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

SLOTS = 4_194_302  # scene-wide skinned transform buffer (UE 5.8)
SLOTS_PER_BONE = 16  # Dynamic Wind: 8 slices x (current + previous)
IMPORT_BONE_CAP = 32_767  # our import path crashes above it
# Draft budget, owner 2026-10-27 (to be replaced by the PCVR ladder, XRFF-591).
GATE_BONES = 65_000  # skinned bones per site x scenario step
GATE_MESHES = 30  # distinct skinned tree meshes per step
GATE_PARTS = 1_500  # foliage parts per near tree (conifers up to ~2,500)
GATE_PARTS_CONIFER = 2_500
GATE_UNIQUE_PARTS = 20
GATE_TRIS = 10_000_000
TRIS_CAP_454 = 50_000_000  # per-tree ceiling asked for in XRFF-454
EXPORT_PART_CAP = 40_000  # the exporter asserts above it (XRFF-474)
CONIFERS = {"norway_spruce", "silver_fir", "douglas_fir", "scots_pine"}

TREE_COLUMNS = [
    "mesh", "species", "radius", "stage_m", "bones", "bone_reduction",
    "buffer_pct_one_mesh", "points", "branches", "plan_current", "unique_parts",
    "part_tris_min", "part_tris_max", "parts_plan", "capped", "tris_lo", "tris_hi",
    "gate",
]  # fmt: skip
MESH = re.compile(r"^SK_(?P<camel>[A-Za-z]+)_r(?P<r>\d+)_h(?P<h>\d+)m$")
CACHE = re.compile(r"^TreeData(?:_(?P<code>\d+))?Cache\.json$")


@dataclass(frozen=True)
class SpawnRule:
    """``PCG_TreeData``'s graph defaults (hub ``tree-spawning-pipeline``)."""

    height_increment: int = 5
    min_height: int = 5
    max_height: int = 45
    dense_max_cm: float = 850.0
    open_min_cm: float = 1500.0
    dense_class: int = 7
    mid_class: int = 10
    open_class: int = 10
    search_cm: float = 20_000.0
    status_min: int = 0
    status_max: int = 4
    dead_status: int = 4
    stand_in: dict[str, str] = field(
        default_factory=lambda: {"European Larch": "Douglas Fir"}
    )


def species_of(camel: str) -> str:
    """``SmallLeavedLinden`` -> ``small_leaved_linden``."""
    return re.sub(r"(?<!^)([A-Z])", r"_\1", camel).lower()


def parse_mesh(name: str) -> tuple[str, int, int] | None:
    """``SK_EuropeanOak_r07_h25m`` -> (``european_oak``, 7, 25)."""
    m = MESH.match(name)
    return (species_of(m["camel"]), int(m["r"]), int(m["h"])) if m else None


def load_bones(path: Path) -> dict[str, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: int(v) for k, v in raw.items() if str(v).isdigit() and parse_mesh(k)}


def build_catalog(meshes) -> dict[str, dict[tuple[int, int], str]]:
    """Display species -> {(radius class, stage): mesh}, as ``DT_TreeCatalog``."""
    from growpy.tools.pve_catalog import species_display_name

    catalog: dict[str, dict[tuple[int, int], str]] = {}
    for name in meshes:
        species, radius, stage = parse_mesh(name)
        catalog.setdefault(species_display_name(species), {})[(radius, stage)] = name
    return catalog


def height_stage(height_m: float, rule: SpawnRule) -> int:
    stage = math.floor(height_m / rule.height_increment + 0.5) * rule.height_increment
    return int(min(rule.max_height, max(rule.min_height, stage)))


def radius_class(nn_cm: float, rule: SpawnRule) -> int:
    if nn_cm <= rule.dense_max_cm:
        return rule.dense_class
    return rule.mid_class if nn_cm <= rule.open_min_cm else rule.open_class


def pick_mesh(catalog, species: str, stage: int, rclass: int) -> str | None:
    """The cell, else the species' nearest: same radius class, closest stage, smaller on a tie."""
    cells = catalog.get(species)
    if not cells:
        return None
    if (rclass, stage) in cells:
        return cells[(rclass, stage)]
    pool = [c for c in cells if c[0] == rclass] or list(cells)
    return cells[min(pool, key=lambda c: (abs(c[1] - stage), c[1]))]


def nearest_neighbour_cm(xy_m: np.ndarray, search_cm: float) -> np.ndarray:
    """Horizontal distance to the nearest other tree, inf beyond ``search_cm``."""
    from scipy.spatial import cKDTree

    if len(xy_m) < 2:
        return np.full(len(xy_m), np.inf)
    d, _ = cKDTree(xy_m).query(xy_m, k=2, distance_upper_bound=search_cm / 100)
    return d[:, 1] * 100


def place_step(rows: list[dict], catalog, rule: SpawnRule) -> dict:
    """Skinned meshes (with tree counts) of one variant, as ``PCG_TreeData`` joins them."""
    placed = [
        r
        for r in rows
        if rule.status_min <= (r.get("tree_status_id") or 0) <= rule.status_max
    ]
    xy = np.array([[r["original_x"], r["original_y"]] for r in placed], float)
    nn = nearest_neighbour_cm(xy.reshape(-1, 2), rule.search_cm)
    skinned: Counter = Counter()
    dead = 0
    unmatched: Counter = Counter()
    for r, d in zip(placed, nn, strict=True):
        if (r.get("tree_status_id") or 0) == rule.dead_status:
            dead += 1
            continue
        species = rule.stand_in.get(r["species_name"], r["species_name"])
        mesh = pick_mesh(
            catalog, species, height_stage(r["height_m"], rule), radius_class(d, rule)
        )
        if mesh is None:
            unmatched[r["species_name"]] += 1
        else:
            skinned[mesh] += 1
    return {
        "placed": len(placed),
        "dead": dead,
        "meshes": skinned,
        "unmatched": unmatched,
    }


def read_cache(path: Path) -> list[dict] | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else None  # an error body is a dict


def scenario_steps(twin_cache: Path, sites: set[str] | None):
    """(site, scenario code, cache file, year, variant id, rows) per variant."""
    for site_dir in sorted(p for p in twin_cache.iterdir() if p.is_dir()):
        if sites and site_dir.name not in sites:
            continue
        for path in sorted(site_dir.iterdir()):
            m = CACHE.match(path.name)
            rows = read_cache(path) if m else None
            if not rows:
                if m:
                    print(f"skip {path}: not a row list")
                continue
            code = int(m["code"]) if m["code"] else None
            if code is None:  # the default request: its own scenario code
                code = Counter(r["scenario_code"] for r in rows).most_common(1)[0][0]
            by_variant: dict[int, list[dict]] = {}
            for r in rows:
                by_variant.setdefault(r["variant_id"], []).append(r)
            for vid, vrows in by_variant.items():
                year = vrows[0].get("simulation_year")
                yield site_dir.name, code, path.name, year, vid, vrows


def scenario_table(
    twin_cache: Path, bones: dict[str, int], rule: SpawnRule, sites=None, floor_bones=0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    catalog = build_catalog(bones)
    steps, mesh_rows, sets = [], [], []
    for site, code, cache, year, vid, rows in scenario_steps(twin_cache, sites):
        step = place_step(rows, catalog, rule)
        sets.append(set(step["meshes"]))
        total = sum(bones[m] for m in step["meshes"])
        steps.append(
            {
                "site": site,
                "scenario_code": code,
                "year": year,
                "variant_id": vid,
                "cache": cache,
                "trees_placed": step["placed"],
                "dead_static": step["dead"],
                "unmatched": sum(step["unmatched"].values()),
                "distinct_meshes": len(step["meshes"]),
                "bones": total,
                "buffer_pct": round(100 * SLOTS_PER_BONE * total / SLOTS, 1),
                "buffer_pct_with_floor": round(
                    100 * SLOTS_PER_BONE * (total + floor_bones) / SLOTS, 1
                ),
                "max_mesh_bones": max((bones[m] for m in step["meshes"]), default=0),
            }
        )
        for mesh, n in sorted(step["meshes"].items()):
            mesh_rows.append(
                {"site": site, "scenario_code": code, "year": year,
                 "mesh": mesh, "trees": n, "bones": bones[mesh]}
            )  # fmt: skip
    df = pd.DataFrame(steps)
    if df.empty:
        return df, pd.DataFrame(mesh_rows)
    df["_meshes"] = sets
    df = df.sort_values(["site", "scenario_code", "year"]).reset_index(drop=True)
    df["switch_pct"], df["switch_union_pct"] = switch_peaks(
        df, list(df.pop("_meshes")), bones, floor_bones
    )
    df["gate"] = [gate_step(r) for r in df.itertuples()]
    return df, pd.DataFrame(mesh_rows)


def switch_peaks(
    df: pd.DataFrame, sets: list[set], bones: dict[str, int], floor_bones: int = 0
) -> tuple[list[float], list[float]]:
    """Worst switch into each step from another year of the scenario or the same
    year of another scenario of the site. ``full``: both allocations in full (a
    mesh in both steps counted twice); ``union``: a shared mesh counted once."""
    full, union = [], []
    for i, r in enumerate(df.itertuples()):
        src = df.index[
            (df.site == r.site)
            & (
                ((df.scenario_code == r.scenario_code) & (df.year != r.year))
                | ((df.scenario_code != r.scenario_code) & (df.year == r.year))
            )
        ]
        old = max((int(df.bones[j]) for j in src), default=0)
        both = max((sum(bones[m] for m in sets[i] | sets[j]) for j in src), default=0)
        full.append(
            round(100 * SLOTS_PER_BONE * (r.bones + old + floor_bones) / SLOTS, 1)
        )
        union.append(round(100 * SLOTS_PER_BONE * (both + floor_bones) / SLOTS, 1))
    return full, union


def gate_step(r) -> str:
    flags = []
    if r.bones > GATE_BONES:
        flags.append(f"bones>{GATE_BONES // 1000}k")
    if r.distinct_meshes > GATE_MESHES:
        flags.append(f"meshes>{GATE_MESHES}")
    if r.buffer_pct_with_floor > 100:
        flags.append("buffer>100%")
    if r.switch_union_pct > 100:
        flags.append("switch>100%")
    elif r.switch_pct > 100:
        flags.append("switch>100%?")  # only if shared meshes are allocated twice
    return " ".join(flags) or "ok"


def part_triangles(usda: Path) -> int:
    """Triangles of a USD mesh file: sum over faces of (vertices - 2)."""
    text = usda.read_text(encoding="utf-8")
    tris = 0
    for m in re.finditer(r"int\[\] faceVertexCounts = \[([^\]]*)\]", text):
        tris += sum(int(n) - 2 for n in m.group(1).split(",") if n.strip())
    return tris


def palette_triangles(
    palette: list[str], instances_dir: Path, cache: dict
) -> list[int]:
    """``/Game/.../SM_<name>_ZUP`` -> triangles of ``Instances/<name>_static.usda``."""
    out = []
    for asset in palette:
        name = re.sub(r"^SM_|_ZUP$", "", asset.rsplit("/", 1)[-1])
        if name not in cache:
            usda = instances_dir / f"{name}_static.usda"
            cache[name] = part_triangles(usda) if usda.is_file() else None
        if cache[name] is not None:
            out.append(cache[name])
    return out


def tree_rows(
    bones: dict[str, int], forest_dir: Path, manifest_path: Path | None
) -> pd.DataFrame:
    from growpy.config.pve_calibration import load_pve_calibration

    strength = load_pve_calibration().bone_reduction_per_species
    plan, plan_mtime = {}, 0.0
    if manifest_path and manifest_path.is_file():
        plan_mtime = manifest_path.stat().st_mtime
        for g in json.loads(manifest_path.read_text(encoding="utf-8"))["graphs"]:
            for m in g["meshes"]:
                plan[m["mesh_name"]] = (m, g.get("palette_meshes") or [])
    tri_cache: dict = {}
    rows = []
    for mesh in sorted(bones):
        species, radius, stage = parse_mesh(mesh)
        row = {
            "mesh": mesh, "species": species, "radius": radius, "stage_m": stage,
            "bones": bones[mesh],
            "bone_reduction": strength.get(species, 0.0),
            "buffer_pct_one_mesh": round(100 * SLOTS_PER_BONE * bones[mesh] / SLOTS, 2),
        }  # fmt: skip
        found = sorted(
            (forest_dir / species / f"r{radius:02d}").glob(
                f"*_r{radius:02d}_h{stage:02d}m_d*cm_full_growth_data.json"
            )
        )
        gj = found[-1] if found else None
        if gj is not None:
            # The graph reads the crown-floor copy where there is one (beech).
            floor = gj.with_name(gj.name.replace(".json", ".floor.json"))
            data = json.loads((floor if floor.is_file() else gj).read_text("utf-8"))
            row["points"] = len(data["points"]["positions"])
            row["branches"] = len(data["primitives"]["points"])
        entry, palette = plan.get(mesh, (None, []))
        current = (
            entry is not None
            and gj is not None
            and Path(entry["growth_json"].replace(".floor.json", ".json")).resolve()
            == gj.resolve()
            and gj.stat().st_mtime <= plan_mtime
        )
        row["plan_current"] = current
        tris = palette_triangles(palette, forest_dir / "Instances", tri_cache)
        row["unique_parts"] = len(palette) if palette else None
        row["part_tris_min"] = min(tris) if tris else None
        row["part_tris_max"] = max(tris) if tris else None
        if current:
            parts = int(entry["predicted_instances"])
            row["parts_plan"] = parts
            row["capped"] = bool(entry.get("capped"))
            if tris:
                row["tris_lo"] = parts * min(tris)
                row["tris_hi"] = parts * max(tris)
        row["gate"] = gate_tree(row)
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=TREE_COLUMNS)


def gate_tree(row: dict) -> str:
    flags = []
    if row["bones"] > IMPORT_BONE_CAP:
        flags.append("bones>import cap")
    if row["bones"] > GATE_BONES / GATE_MESHES:
        flags.append(f"bones>{GATE_BONES // GATE_MESHES}/mesh")
    cap = GATE_PARTS_CONIFER if row["species"] in CONIFERS else GATE_PARTS
    if (row.get("parts_plan") or 0) > cap:
        flags.append(f"parts>{cap}")
    if (row.get("unique_parts") or 0) > GATE_UNIQUE_PARTS:
        flags.append(f"unique>{GATE_UNIQUE_PARTS}")
    if (row.get("parts_plan") or 0) > EXPORT_PART_CAP:
        flags.append("parts>export assert")
    if (row.get("tris_lo") or 0) > TRIS_CAP_454:
        flags.append("tris>50M")
    elif (row.get("tris_lo") or 0) > GATE_TRIS:
        flags.append("tris>10M")
    return " ".join(flags) or "ok"


def parse_measured(items: list[str]) -> dict[tuple[str, int, int], float]:
    """``ECOSENSE:10:2025=52.9`` -> {(site, code, year): pct}."""
    out = {}
    for item in items:
        key, pct = item.split("=")
        site, code, year = key.split(":")
        out[(site, int(code), int(year))] = float(pct)
    return out


def main(argv: list[str] | None = None) -> int:
    from growpy.config.paths import get_data_directory

    data_dir = get_data_directory()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--twin-cache",
        type=Path,
        required=True,
        help="<UE project>/Saved/TwinCache, one folder per site",
    )
    parser.add_argument(
        "--bones",
        type=Path,
        default=data_dir / "output" / "export_budget" / "bones_ue_2026-10-27.json",
        help="asset registry Bones tag per catalog mesh (an editor dump)",
    )
    parser.add_argument(
        "--forest-dir", type=Path, default=data_dir / "output" / "forest"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="PVE plan manifest (default <forest-dir>/unreal_scripts/pve_export_manifest.json)",
    )
    parser.add_argument("--sites", default=None, help="comma list, default all")
    parser.add_argument(
        "--floor-bones",
        type=int,
        default=0,
        help="skinned floor-plant bones per step, from a UE measurement",
    )
    parser.add_argument(
        "--measured",
        action="append",
        default=[],
        help="SITE:CODE:YEAR=PCT measured in UE, repeatable",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    bones = load_bones(args.bones)
    if not bones:
        print(f"no catalog meshes in {args.bones}")
        return 1
    sites = set(args.sites.split(",")) if args.sites else None
    manifest = (
        args.manifest or args.forest_dir / "unreal_scripts" / "pve_export_manifest.json"
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 500)

    trees = tree_rows(bones, args.forest_dir, manifest)
    trees.to_csv(args.out_dir / "export_budget_trees.csv", index=False)
    by_species = trees.groupby("species").agg(
        meshes=("bones", "size"),
        bones_p50=("bones", "median"),
        bones_max=("bones", "max"),
        reduction=("bone_reduction", "first"),
        branches_p50=("branches", "median"),
        parts_plan_p50=("parts_plan", "median"),
        unique_parts=("unique_parts", "max"),
        tris_lo_p50_M=("tris_lo", "median"),
        tris_hi_p50_M=("tris_hi", "median"),
        plan_current=("plan_current", "sum"),
    )
    by_species[["tris_lo_p50_M", "tris_hi_p50_M"]] /= 1e6
    by_species = by_species.round(1)
    by_species.to_csv(args.out_dir / "export_budget_species.csv")
    print(by_species.to_string())

    steps, meshes = scenario_table(
        args.twin_cache, bones, SpawnRule(), sites, args.floor_bones
    )
    if steps.empty:
        print(f"no tree caches under {args.twin_cache}")
        return 1
    measured = parse_measured(args.measured)
    steps["measured_pct"] = [
        measured.get((r.site, r.scenario_code, r.year)) for r in steps.itertuples()
    ]
    steps.to_csv(args.out_dir / "export_budget_scenarios.csv", index=False)
    meshes.to_csv(args.out_dir / "export_budget_meshes.csv", index=False)
    cols = ["site", "scenario_code", "year", "trees_placed", "dead_static",
            "distinct_meshes", "bones", "buffer_pct", "buffer_pct_with_floor",
            "switch_pct", "switch_union_pct", "measured_pct", "gate"]  # fmt: skip
    print("\n" + steps[cols].to_string(index=False))
    print(f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
