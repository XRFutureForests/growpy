"""Write standardised QSM trees as MTG files (OpenAlea multiscale tree graphs).

    growpy-qsm-to-mtg --descriptors <descriptors.csv> --standardized <dir> --out-dir <dir>
        [--species european_beech norway_spruce]

The trees are the same quality-checked set the prototypes use (``prototypes.select_groups``:
species x height-class cells, tiers A/B unless fewer than five, height and crown-width QC),
written after the common-resolution prune: ``<out-dir>/<species_key>/<tree>.mtg`` plus
``index.csv`` (tree, file, species, height class, height, DBH, tier, source). See
``growpy.structure.mtg_io`` for the layout. Needs ``openalea.mtg`` (the ``growpy-openalea``
conda env; not on PyPI).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from growpy.structure import mtg_io
from growpy.structure import prototypes as pt
from growpy.structure.store import iter_trees


def file_name(tree_uid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", tree_uid) + ".mtg"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--descriptors", type=Path, required=True)
    ap.add_argument("--standardized", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--species", nargs="*", default=["european_beech", "norway_spruce"])
    args = ap.parse_args(argv)

    desc = pd.read_csv(args.descriptors, low_memory=False)
    desc = desc[desc["species_key"].isin(args.species)]
    groups = pt.select_groups(desc)
    chosen = groups[groups["width_class"] == "w0"].set_index("tree_uid")
    wanted = set(chosen.index)
    print(f"{len(wanted)} trees", flush=True)
    rows, done = [], set()
    for ds in sorted(
        p
        for p in args.standardized.iterdir()
        if p.is_dir() and p.name != "growpy_forest"
    ):
        # a tree in two datasets (BioDiv QSM and its graph twin) is written once
        todo = (wanted - done) & set(
            pd.read_csv(ds / "trees.csv", usecols=["tree_uid"])["tree_uid"]
        )
        if not todo:
            continue
        print(f"  {ds.name}: {len(todo)} trees", flush=True)
        for tree in iter_trees(ds):
            uid = tree.meta["tree_uid"]
            if uid not in todo:
                continue
            todo.discard(uid)
            done.add(uid)
            sp = chosen.at[uid, "species_key"]
            path = args.out_dir / sp / file_name(uid)
            mtg_io.write(
                mtg_io.to_mtg(tree.cyl, {**tree.meta, "species_key": sp}), path
            )
            rows.append(
                {
                    "tree_uid": uid,
                    "file": path.relative_to(args.out_dir).as_posix(),
                    "species_key": sp,
                    "height_class": chosen.at[uid, "height_class"],
                    "height_m": tree.meta.get("height_m"),
                    "dbh_m": tree.meta.get("dbh_m"),
                    "tier": tree.meta.get("tier"),
                    "source": tree.meta.get("source"),
                }
            )
            if not todo:
                break
    index = pd.DataFrame(rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    index.to_csv(args.out_dir / "index.csv", index=False)
    print(index.groupby(["species_key", "height_class"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
