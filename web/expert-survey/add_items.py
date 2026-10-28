"""Add trees to the survey item store (XRFF-593): draw them, check them, append them.

    conda run -n growpy python web/expert-survey/add_items.py            # dry run: the plan
    conda run -n growpy python web/expert-survey/add_items.py --write    # draw and append

The store is a folder of items, one per tree card, plus an append-only ``manifest.jsonl``
that the survey server reads (it picks up new lines without a restart)::

    items/<id>/front.png, side.png   the card drawings, served to respondents
    items/<id>/meta.json             where the tree comes from; never served before a vote
    items/manifest.jsonl             one meta record per line

Every drawing is a leaf-off branch skeleton after the descriptors' common prune
(``prototypes.PRUNE``), pipe-model radii from the reported DBH (catalog allometry for growpy
trees, field DBH for real ones), true-scale line widths and a 1.75 m person for scale
(``tree_icon(figure_m=...)``). Real and generated trees are drawn the same way.

Pool (stand-grown only, owner 2026-10-28): real QSM trees from BioDiv and Belgium (tier A/B,
a resolved crown, an unbroken stem), generated trees from the growpy catalog and the regrow
arms. Only species that have both. Per species and 5 m height class at most ``--per-cell``
real and as many generated trees, so height never gives the answer away; real trees rotate
over the datasets and generated trees over the generator groups (catalog, each arm), so no
single source dominates. Trees already in the manifest (same tree id and renderer) are
skipped, so the script can be rerun as new trees or arms appear.
"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure.prototype_icons import tree_icon
from growpy.structure.prototypes import geometry, pipe_radii
from growpy.structure.store import iter_trees

ROOT = Path(__file__).resolve().parents[2]  # growpy repo
STRUCT = ROOT / "data/output/structure"
STD = STRUCT / "std"
HERE = Path(__file__).resolve().parent
RENDER = "card-2026-10-28"  # bump when the drawing changes; old items stay as they were drawn
FIGURE_M = 1.75
STAGES = (10, 15, 20, 25, 30, 35)  # height classes: stage +- 2.5 m
REAL_SETS = ("biodiv", "belgium")  # stand-grown; Kew is open-grown and waits for open-grown Grove trees
CATALOG = "growpy_thinned_2026-10-26"

SPECIES = {
    "common_ash": "Common ash",
    "douglas_fir": "Douglas fir",
    "european_beech": "European beech",
    "european_oak": "Oak (pedunculate / sessile)",
    "norway_spruce": "Norway spruce",
    "scots_pine": "Scots pine",
    "silver_birch": "Silver birch",
    "silver_fir": "Silver fir",
    "small_leaved_linden": "Small-leaved lime",
    "sycamore_maple": "Sycamore maple",
    "wild_cherry": "Wild cherry",
}
DATASET_NAMES = {"biodiv": "BioDiv-3DTrees", "belgium": "Belgian forest plots"}


def stage_of(h: float) -> int | None:
    for s in STAGES:
        if abs(h - s) <= 2.5:
            return s
    return None


def real_candidates() -> pd.DataFrame:
    frames = []
    for ds in REAL_SETS:
        t = pd.read_csv(STD / ds / "trees.csv", low_memory=False)
        t["dataset"] = ds
        frames.append(t)
    t = pd.concat(frames, ignore_index=True)
    # a failed fit would teach the raters that real trees look odd: tier A/B, a resolved crown
    t = t[t.tier.isin(["A", "B"]) & (t.n_axes >= 100) & (t.crown_base_m <= 0.7 * t.height_m)]
    t = t.assign(kind="real", group=t.dataset, std_dir=[str(STD / d) for d in t.dataset])
    return t


def generated_candidates() -> pd.DataFrame:
    frames = []
    cat = pd.read_csv(STD / CATALOG / "trees.csv", low_memory=False)
    cat["radius"] = cat.source_tree_id.str.extract(r"_r(\d+)_")[0]
    cat = cat[cat.radius.isin(["07", "10"])]  # stand-grown stages
    frames.append(cat.assign(group="catalog", arm="", seed="", knobs="{}", std_dir=str(STD / CATALOG)))
    for arm_json in sorted(STRUCT.glob("regrow/*/*/arm.json")):
        arm = json.loads(arm_json.read_text(encoding="utf-8"))
        for std in sorted((arm_json.parent / "std").glob("seed*")):
            if not (std / "trees.csv").exists():
                continue  # a regrow still running
            t = pd.read_csv(std / "trees.csv", low_memory=False)
            t["radius"] = t.source_tree_id.str.extract(r"_r(\d+)_")[0]
            frames.append(t.assign(
                group=f"regrow:{arm['arm']}", arm=arm["arm"], seed=std.name.removeprefix("seed"),
                knobs=json.dumps(arm.get("preset_overrides", {}), sort_keys=True), std_dir=str(std)))
    t = pd.concat(frames, ignore_index=True)
    return t.assign(kind="generated", dataset="growpy")


def plan(per_cell: int, rng: np.random.Generator, skip: set[str], have: dict[tuple, int]) -> pd.DataFrame:
    real, gen = real_candidates(), generated_candidates()
    both = sorted(set(real.species_key) & set(gen.species_key) & set(SPECIES))
    picks = []
    for frame in (real, gen):
        frame["stage"] = frame.height_m.map(stage_of)
    for sp in both:
        for s in STAGES:
            r = real[(real.species_key == sp) & (real.stage == s) & ~real.tree_uid.isin(skip)]
            g = gen[(gen.species_key == sp) & (gen.stage == s) & ~gen.tree_uid.isin(skip)]
            n_real = min(per_cell - have.get((sp, s, "real"), 0), len(r))
            n_gen = have.get((sp, s, "real"), 0) + n_real - have.get((sp, s, "generated"), 0)
            n_gen = min(n_gen, len(g))
            if n_real > 0:
                picks += _rotate(r, n_real, rng)
            if n_gen > 0:
                picks += _rotate(g, n_gen, rng)
    return pd.DataFrame(picks)


def _rotate(frame: pd.DataFrame, n: int, rng: np.random.Generator) -> list[dict]:
    """n rows, one group after the other in random order, a random tree within each group;
    extra candidates per group are drawn so the stem check can reject some."""
    groups = {k: v.sample(frac=1, random_state=int(rng.integers(1 << 31))) for k, v in frame.groupby("group")}
    order = list(groups)
    rng.shuffle(order)
    out, i = [], 0
    while len(out) < 6 * n and any(len(v) for v in groups.values()):  # the stem check rejects ~half
        g = order[i % len(order)]
        if len(groups[g]):
            out.append(dict(groups[g].iloc[0]) | {"want": n})
            groups[g] = groups[g].iloc[1:]
        i += 1
    return out


def stem_problem(geo, dbh: float) -> str | None:
    """Why the stem would look broken on the card, or None. Only the lower 75 % of the
    height counts: higher up, fitted leaders end in short crooked pieces and the axis jumps at
    forks, both hidden in the crown. A gap counts when it is wider than 3 px on the 512 px card
    (frame ~1.1 x height), a kink when two trunk pieces of >= 15 cm meet at more than 35 deg."""
    rows = np.asarray(geo.trunk_rows)
    if len(rows) < 2:
        return "trunk has fewer than two cylinders"
    low = geo.end[rows[:-1], 2] < 0.75 * geo.height
    gap = np.linalg.norm(geo.start[rows[1:]] - geo.end[rows[:-1]], axis=1)[low]
    px = gap / (1.1 * geo.height) * 512 if len(gap) else np.zeros(1)
    if px.max() > 3:
        return f"stem gap {gap.max():.2f} m ({px.max():.0f} px)"
    d = geo.end[rows] - geo.start[rows]
    ln = np.linalg.norm(d, axis=1)
    u = d / np.maximum(ln, 1e-9)[:, None]
    kink = np.degrees(np.arccos(np.clip((u[1:] * u[:-1]).sum(axis=1), -1, 1)))
    ok = low & (ln[1:] >= 0.15) & (ln[:-1] >= 0.15)
    if ok.any() and kink[ok].max() > 35:
        return f"stem kink {kink[ok].max():.0f} deg"
    return None


def reveal(row: dict) -> dict:
    if row["kind"] == "real":
        tool = row.get("qsm_tool") or "QSM"
        tool = tool if isinstance(tool, str) else "QSM"
        return {"title": "Real tree, from a laser scan",
                "lines": [f"{DATASET_NAMES.get(row['dataset'], row['dataset'])}, tree {row['source_tree_id']}",
                          f"Structure fitted with {tool} (quality tier {row['tier']})"]}
    stage = f"grown to {int(row['stage'])} m in a stand (neighbours at {int(row['radius'])} m)"
    if row["group"] == "catalog":
        return {"title": "Generated tree", "lines": ["The Grove 2.3, growpy catalog", stage]}
    knobs = json.loads(row["knobs"]) or {}
    knob_txt = ", ".join(f"{k} {v}" for k, v in knobs.items()) or "catalog preset"
    return {"title": "Generated tree",
            "lines": [f"The Grove 2.3, test arm {row['arm']}, seed {row['seed']}", f"Settings: {knob_txt}", stage]}


def git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--items", type=Path, default=HERE / "items")
    p.add_argument("--per-cell", type=int, default=2, help="real trees per species x height class")
    p.add_argument("--seed", type=int, default=20261028)
    p.add_argument("--write", action="store_true", help="draw and append (default: show the plan)")
    a = p.parse_args()

    manifest = a.items / "manifest.jsonl"
    have = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()] if manifest.exists() else []
    have = [m for m in have if m["render"] == RENDER]
    skip = {m["source"]["tree_uid"] for m in have}
    cells: dict[tuple, int] = {}
    for m in have:
        key = (m["species_key"], int(m["source"]["stage"]), m["kind"])
        cells[key] = cells.get(key, 0) + 1
    picks = plan(a.per_cell, np.random.default_rng(a.seed), skip, cells)
    if picks.empty:
        print("nothing new to add")
        return 0
    print(picks.groupby(["species_key", "kind", "group"]).size().rename("candidates").to_string())
    if not a.write:
        return 0

    a.items.mkdir(parents=True, exist_ok=True)
    commit, now = git_commit(), datetime.now(timezone.utc).isoformat(timespec="seconds")
    taken: dict[tuple, int] = dict(cells)
    added, rejected = [], []
    # real trees first: a cell gets as many generated trees as real ones survived the stem check
    order = sorted(picks.groupby("std_dir", sort=False), key=lambda kv: kv[1].kind.iloc[0] != "real")
    for std_dir, rows in order:
        by_uid = {r["tree_uid"]: r for r in rows.to_dict("records")}
        for tree in iter_trees(Path(std_dir)):
            row = by_uid.pop(tree.meta["tree_uid"], None)
            if row is None:
                continue
            cell = (row["species_key"], row["stage"], row["kind"])
            real_key = (row["species_key"], row["stage"], "real")
            limit = cells.get(real_key, 0) + row["want"] if row["kind"] == "real" else taken.get(real_key, 0)
            if taken.get(cell, 0) >= limit:
                if not by_uid:
                    break
                continue
            geo = geometry(tree.cyl)
            rep = row.get("dbh_m_reported")
            dbh = float(rep) if rep == rep and rep else float(row["dbh_m"])
            # fitting artefacts only: a kinked Grove stem is model behaviour the raters should judge
            problem = stem_problem(geo, dbh) if row["kind"] == "real" else None
            if problem:
                rejected.append((row["tree_uid"], problem))
                continue
            radius = pipe_radii(geo.start, geo.end, geo.parent, geo.trunk_rows, dbh)
            item_id = secrets.token_hex(5)
            d = a.items / item_id
            for view in ("front", "side"):
                tree_icon(d / f"{view}.png", geo, radius, view, figure_m=FIGURE_M)
            meta = {
                "id": item_id, "added": now, "render": RENDER, "growpy_commit": commit, "active": True,
                "species_key": row["species_key"], "species": SPECIES[row["species_key"]],
                "height_m": round(float(row["height_m"])), "setting": "stand", "kind": row["kind"],
                "group": row["group"], "dbh_drawn_m": round(dbh, 3),
                "source": {k: (None if v != v else v) for k, v in row.items()
                           if k in ("dataset", "tree_uid", "source_tree_id", "tier", "plot", "qsm_tool",
                                    "arm", "seed", "knobs", "radius", "stage", "height_m", "dbh_m")},
                "reveal": reveal(row),
            }
            (d / "meta.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
            with manifest.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(meta, default=str) + "\n")
            taken[cell] = taken.get(cell, 0) + 1
            added.append(meta)
            print(f"+ {item_id} {row['species_key']} {row['stage']} m {row['kind']} {row['group']}", flush=True)
            if not by_uid:
                break
    for uid, why in rejected:
        print(f"- {uid}: {why}")
    mix = pd.DataFrame([{"species": m["species_key"], "kind": m["kind"], "group": m["group"]} for m in added])
    if not mix.empty:
        print("\nadded:\n" + mix.groupby(["species", "kind", "group"]).size().rename("items").to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
