"""Owner gallery: regrow arms next to real trees of the same height, in the catalog icon style.

    growpy-structure-gallery --arm baseline=<arm dir> --arm btm0.1=<arm dir> \\
        --real data/output/structure/std/biodiv --species european_beech --height 20 \\
        --out data/output/structure/regrow/european_beech/gallery_h20.png

One row per arm (its seeds across, the r07 tree whose height stage is ``--height``) and
one row of real trees (tier A, within ``--tol`` metres of that height, a fixed random
draw). Every tile is front view, 512 px, drawn like a catalog branch icon
(``structure.prototype_icons``) with pipe-model radii anchored at the tree's DBH, so Grove
and QSM radii are drawn alike. No Unreal editor needed. ``--blind`` shuffles all tiles
into one unlabeled grid and writes the key to a CSV, for the owner ranking (XRFF-576).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np

from growpy.structure.prototype_icons import compose, tree_icon
from growpy.structure.prototypes import geometry, pipe_radii
from growpy.structure.store import iter_trees

_STAGE = re.compile(r"_r(?P<r>\d+)_h(?P<h>\d+)m_")


def _draw(tree, path: Path, view: str) -> Path | None:
    try:
        geo = geometry(tree.cyl)
    except Exception as exc:  # noqa: BLE001 - one odd tree must not end the sheet
        print(f"skip {tree.meta['tree_uid']}: {exc}", file=sys.stderr)
        return None
    dbh = tree.meta.get("dbh_m")
    dbh = float(dbh) if dbh and np.isfinite(dbh) else 0.01 * geo.height
    radius = pipe_radii(geo.start, geo.end, geo.parent, geo.trunk_rows, dbh)
    return tree_icon(path, geo, radius, view)


def arm_trees(arm_dir: Path, height: int, radius: str):
    for std in sorted((arm_dir / "std").glob("seed*")):
        for tree in iter_trees(std):
            m = _STAGE.search(str(tree.meta.get("source_tree_id", "")))
            if m and int(m["h"]) == height and m["r"] == radius:
                yield std.name, tree


def real_trees(real_dir: Path, species: str, height: float, tol: float, n: int, seed: int):
    picks = []
    for tree in iter_trees(real_dir):
        meta = tree.meta
        if (
            meta.get("species_key") == species
            and meta.get("tier") == "A"
            and abs(float(meta["height_m"]) - height) <= tol
        ):
            picks.append(tree)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(picks))[:n]
    return [picks[i] for i in order]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--arm", action="append", default=[], metavar="LABEL=DIR")
    parser.add_argument("--real", type=Path, required=True, help="standardised dataset")
    parser.add_argument("--species", default="european_beech")
    parser.add_argument("--height", type=int, default=20, help="height stage, metres")
    parser.add_argument("--radius", default="07", help="surround radius label")
    parser.add_argument("--tol", type=float, default=1.5)
    parser.add_argument("--n-real", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--view", default="front", choices=["front", "side"])
    parser.add_argument("--blind", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    tiles_dir = args.out.with_suffix("")
    rows, tiles = [], []
    for item in args.arm:
        label, _, path = item.partition("=")
        row = []
        for seed, tree in arm_trees(Path(path), args.height, args.radius):
            tile = _draw(tree, tiles_dir / f"{label}_{seed}.png", args.view)
            row.append((tile, f"{seed}, {float(tree.meta['height_m']):.1f} m"))
            tiles.append((label, seed, tile))
        rows.append((label, row))
    real = real_trees(
        args.real, args.species, args.height, args.tol, args.n_real, args.seed
    )
    row = []
    for tree in real:
        name = str(tree.meta["tree_uid"]).replace(":", "_")
        tile = _draw(tree, tiles_dir / f"real_{name}.png", args.view)
        row.append((tile, f"{tree.meta['source_tree_id']}, {tree.meta['height_m']:.1f} m"))
        tiles.append(("real", tree.meta["tree_uid"], tile))
    rows.append((f"real {args.species}\ntier A", row))
    width = max(len(r) for _, r in rows)
    if args.blind:
        rng = np.random.default_rng(args.seed)
        order = rng.permutation(len(tiles))
        key = args.out.with_name(args.out.stem + "_key.csv")
        with key.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["tile", "kind", "id", "path"])
            for k, i in enumerate(order, 1):
                w.writerow([k, tiles[i][0], tiles[i][1], tiles[i][2]])
        shuffled = [(tiles[i][2], f"#{k}") for k, i in enumerate(order, 1)]
        rows = [
            ("", shuffled[j : j + width]) for j in range(0, len(shuffled), width)
        ]
        print(f"key -> {key}")
    columns = [""] * width
    title = f"{args.species} at {args.height} m, {args.view} view"
    compose(args.out, rows, columns, title=title)
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
