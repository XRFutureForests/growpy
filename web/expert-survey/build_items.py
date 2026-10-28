"""Build the item pool for the expert tree survey (follow-up to the XRFF-576 owner ranking).

    conda run -n growpy python web/expert-survey/build_items.py

Every item is one leaf-off tree drawn exactly like the owner's blind sheet
(``growpy-structure-gallery``: common-resolution prune, pipe-model radii from DBH, 512 px),
front and side view, so catalog trees and real QSM trees cannot be told apart by the drawing.

Pool:
- catalog: every species, r07 at 10 / 20 / 30 m (or the tallest stage below 30 m) plus r10 at 20 m;
- real: per species and target height one QSM tree within 2 m, best tier first (A > B > C);
- ranked: four real beech and two candidate-A seeds from the owner's blind sheet, so the
  experts' verdict can be set against the owner's.

Writes ``site/img/<code>_{front,side}.png``, ``site/items.json`` (what the app shows: code,
height, set, intended species) and ``items_key.csv`` (what it hides: kind, source, tree id; gitignored, the frozen copy
is in the hub, ``publications/generated-vs-real-tree-structure/expert-survey/``). The draw is
seeded: on unchanged inputs a rebuild reproduces the same codes. Inputs: the standardised sets
in ``data/output/structure/std/`` and the owner's blind sheet in
``data/output/structure/ranking_2026-10-28/``.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure.store import iter_trees
from growpy.tools.structure_gallery import _draw

ROOT = Path(__file__).resolve().parents[2]  # growpy repo
STD = ROOT / "data/output/structure/std"
HERE = Path(__file__).resolve().parent
APP = HERE / "site"
IMG = APP / "img"
RANKING = ROOT / "data/output/structure/ranking_2026-10-28"
TARGETS = (10, 20, 30)
TOL = 2.0
TIER_ORDER = {"A": 0, "B": 1, "C": 2}
SEED = 20261028

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


def catalog_picks() -> list[dict]:
    trees = pd.read_csv(STD / "growpy_thinned_2026-10-26/trees.csv")
    trees["r"] = trees.source_tree_id.str.extract(r"_r(\d+)_")[0]
    trees["h"] = trees.source_tree_id.str.extract(r"_h(\d+)m_")[0].astype(int)
    picks = []
    for sp in SPECIES:
        t = trees[trees.species_key == sp]
        r07 = sorted(t[t.r == "07"].h)
        stages = [10, 20, max(h for h in r07 if h <= 30)]
        cells = [("07", h) for h in stages] + [("10", 20)]
        for r, h in cells:
            row = t[(t.r == r) & (t.h == h)].iloc[0]
            picks.append(
                dict(kind="catalog", species_key=sp, uid=row.tree_uid, dataset="growpy_thinned_2026-10-26",
                     source_id=row.source_tree_id, tier="", height_m=float(row.height_m), stage=f"r{r}_h{h:02d}")
            )
    return picks


def real_picks(rng: np.random.Generator) -> list[dict]:
    frames = []
    for ds in ("biodiv", "belgium", "kew"):
        t = pd.read_csv(STD / ds / "trees.csv", low_memory=False)
        t["dataset"] = ds
        frames.append(t)
    t = pd.concat(frames, ignore_index=True)
    t = t[t.species_key.isin(SPECIES) & t.tier.isin(TIER_ORDER)]
    # A failed fit or an arboretum tree would teach the experts that real trees look odd:
    # tier A/B only, a resolved crown (>= 100 axes, crown base below 70 % of height); the one
    # exception is Norway spruce, whose only QSMs are Kew tier C, below the broken-top range.
    good = (t.n_axes >= 100) & (t.crown_base_m <= 0.7 * t.height_m)
    tier_ok = t.tier.isin(["A", "B"]) | ((t.species_key == "norway_spruce") & (t.height_m <= 15))
    t = t[good & tier_ok]
    picks = []
    for sp in SPECIES:
        for target in TARGETS:
            near = t[(t.species_key == sp) & ((t.height_m - target).abs() <= TOL)]
            if near.empty:
                continue
            best = min(near.tier, key=TIER_ORDER.get)
            pool = near[near.tier == best]
            row = pool.iloc[int(rng.integers(len(pool)))]
            picks.append(
                dict(kind="real", species_key=sp, uid=row.tree_uid, dataset=row.dataset,
                     source_id=row.source_tree_id, tier=best, height_m=float(row.height_m), stage=f"h{target:02d}")
            )
    return picks


def ranked_picks() -> list[dict]:
    """Owner's blind sheet: its 3 bottom and 1 top real beech, 2 candidate-A seeds (images exist)."""
    key = {int(r["tile"]): r for r in csv.DictReader((RANKING / "blind_sheet_h20_key.csv").open())}
    rank = {int(r["tile"]): r["rank"] for r in csv.DictReader((RANKING / "ranking_form.csv").open())}
    picks = []
    for tile in (9, 10, 19, 14, 13, 3):
        r = key[tile]
        picks.append(
            dict(kind="ranked_" + r["kind"], species_key="european_beech", uid=r["id"], dataset="ranking_2026-10-28",
                 source_id=f"tile{tile}", tier="A" if r["kind"] == "real" else "", height_m=20.0,
                 stage=f"owner_rank_{rank[tile]}", image=str(ROOT / r["path"]))
        )
    return picks


def main() -> int:
    rng = np.random.default_rng(SEED)
    picks = catalog_picks() + real_picks(rng) + ranked_picks()
    codes = rng.choice(np.arange(100, 1000), size=len(picks), replace=False)
    for p, c in zip(picks, codes):
        p["code"] = f"T{c}"
    if IMG.exists():
        shutil.rmtree(IMG)
    IMG.mkdir(parents=True)

    want: dict[str, dict[str, dict]] = {}
    for p in picks:
        if "image" not in p:
            want.setdefault(p["dataset"], {})[p["uid"]] = p
    for ds, by_uid in want.items():
        found = 0
        for tree in iter_trees(STD / ds):
            p = by_uid.get(tree.meta["tree_uid"])
            if p is None:
                continue
            for view in ("front", "side"):
                ok = _draw(tree, IMG / f"{p['code']}_{view}.png", view)
                p[f"ok_{view}"] = ok is not None
            found += 1
            print(f"{ds}: {found}/{len(by_uid)} {p['code']} {p['species_key']} {p['kind']}", flush=True)
            if found == len(by_uid):
                break
    for p in picks:
        if "image" in p:  # side views for the ranked trees are not redrawn: front only
            shutil.copy(p["image"], IMG / f"{p['code']}_front.png")
            p["ok_front"], p["ok_side"] = True, False

    picks = [p for p in picks if p.get("ok_front")]
    # two sets: every kind x species group alternates A/B, the start flips per group so
    # odd-sized groups do not pile into set A
    start = 0
    for kind in sorted({p["kind"] for p in picks}):
        for sp in SPECIES:
            group = [p for p in picks if p["kind"] == kind and p["species_key"] == sp]
            rng.shuffle(group)
            for k, p in enumerate(group):
                p["set"] = "AB"[(k + start) % 2]
            start += len(group) % 2

    items = [
        dict(code=p["code"], set=p["set"], height_m=round(p["height_m"]),
             species=SPECIES[p["species_key"]], species_key=p["species_key"],
             front=f"img/{p['code']}_front.png", side=f"img/{p['code']}_side.png" if p.get("ok_side") else None)
        for p in sorted(picks, key=lambda p: p["code"])
    ]
    (APP / "items.json").write_text(json.dumps(items, indent=1), encoding="utf-8")
    with (HERE / "items_key.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        cols = ["code", "set", "kind", "species_key", "dataset", "tier", "source_id", "uid", "stage", "height_m"]
        w.writerow(cols)
        for p in sorted(picks, key=lambda p: p["code"]):
            w.writerow([p.get(c, "") for c in cols])
    n = pd.DataFrame(picks).groupby(["set", "kind"]).size()
    print(n.to_string())
    print(f"{len(items)} items -> {APP / 'items.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
