"""Fit the stochastic branching model to real trees (MTG files), generate trees with its
L-Py rule set, and check them against the real trees and the Grove catalog.

    growpy-branching-model --mtg-dir <dir> --descriptors <descriptors.csv> --out-dir <dir>
        [--species european_beech] [--samples 12]
        [--prototypes-dir <qsm_prototypes out>] [--catalog data/output/forest]

``--mtg-dir`` is ``growpy-qsm-to-mtg`` output (``index.csv`` + one ``.mtg`` per tree). Per
height class with at least ``--min-trees`` trees this writes, under ``--out-dir``:

  models/<Species>_<hNNm>.pkl      the fitted model (``BranchingModel.load``)
  models/<Species>_<hNNm>_chain.csv the Markov chain as a table
  tiles/<Species>_<hNNm>_model<NN>_front.png   samples in the catalog icon style
  generated_descriptors.csv        descriptors of every generated sample
  validation.csv                   per descriptor: real median, model and Grove robust z
  <Species>_model_sheet.png        catalog | real medoid | prototype | model samples
Runs in the ``growpy-openalea`` env (openalea.mtg, openalea.lpy). Radii of generated trees
are pipe-model radii from the yield-table DBH, so radius descriptors are not validated.
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure import branching_model as bm
from growpy.structure import mtg_io
from growpy.structure import prototype_icons as icons
from growpy.structure import prototypes as pt
from growpy.structure.descriptors import DEFINITIONS, describe
from growpy.structure.standardize import RawQsm, standardize

NOT_VALIDATED = (
    "L1.height_m",  # scaled to the target by construction
    "L4.radius_ratio_top",
    "L4.radius_ratio_middle",
    "L4.radius_ratio_bottom",
    "G.pipe_exponent_p50",
    "T.axis_radius_ratio_2_1",
)


def _events(mtg_dir: Path, index: pd.DataFrame, cache: Path) -> dict[str, dict]:
    events = pickle.loads(cache.read_bytes()) if cache.exists() else {}
    todo = [r for r in index.itertuples() if r.tree_uid not in events]
    for k, r in enumerate(todo):
        events[r.tree_uid] = bm.tree_events(
            mtg_io.from_mtg(mtg_io.read(mtg_dir / r.file))
        )
        if (k + 1) % 200 == 0:
            print(f"  events {k + 1}/{len(todo)}", flush=True)
            cache.write_bytes(pickle.dumps(events))
    cache.write_bytes(pickle.dumps(events))
    return events


def generated_tree(model: bm.BranchingModel, height: float, dbh: float, seed: int):
    """One sample: cylinders scaled to ``height``, pipe radii from ``dbh``; returns the
    drawable geometry, its radii and the standardised exchange table."""
    _, lstring = bm.generate(model, height, seed)
    c = bm.lstring_cylinders(lstring)
    start = c[["start_x", "start_y", "start_z"]].to_numpy()
    end = c[["end_x", "end_y", "end_z"]].to_numpy()
    scale = height / max(float(end[:, 2].max()), 1e-9)
    start, end = start * scale, end * scale
    parent = c["parent"].to_numpy()
    trunk = list(np.flatnonzero(c["order"].to_numpy() == 0))
    geo = pt.Geometry(start, end, parent, np.zeros(len(start)), trunk)
    radius = pt.pipe_radii(start, end, parent, trunk, dbh)
    seg = end - start
    length = np.linalg.norm(seg, axis=1)
    raw = pd.DataFrame(
        {
            "parent": parent,
            "start_x": start[:, 0],
            "start_y": start[:, 1],
            "start_z": start[:, 2],
            "axis_x": seg[:, 0] / length,
            "axis_y": seg[:, 1] / length,
            "axis_z": seg[:, 2] / length,
            "length": length,
            "radius": radius,
        }
    )
    tree = standardize(RawQsm(raw, {}), {"tree_uid": f"model:{seed}"})
    return geo, radius, tree.cyl


def robust_z(values: pd.Series, real: pd.Series) -> float:
    real = real.dropna()
    values = values.dropna()
    if len(real) < 5 or values.empty:
        return float("nan")
    mad = 1.4826 * float((real - real.median()).abs().median())
    if mad <= 1e-12:
        mad = float(real.quantile(0.75) - real.quantile(0.25)) / 1.349
    if mad <= 1e-12:
        return float("nan")
    return (float(values.median()) - float(real.median())) / mad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mtg-dir", type=Path, required=True)
    ap.add_argument("--descriptors", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--species", default="european_beech")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--min-trees", type=int, default=15)
    ap.add_argument("--prototypes-dir", type=Path)
    ap.add_argument("--catalog", type=Path, default=Path("data/output/forest"))
    ap.add_argument("--catalog-radius", default="r07")
    args = ap.parse_args(argv)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    title = pt.species_title(args.species)

    index = pd.read_csv(args.mtg_dir / "index.csv")
    index = index[index["species_key"] == args.species].drop_duplicates("tree_uid")
    print(f"{len(index)} {args.species} trees", flush=True)
    events = _events(args.mtg_dir, index, out / f"events_{args.species}.pkl")
    species = [events[u] for u in index["tree_uid"]]

    desc = pd.read_csv(args.descriptors, low_memory=False)
    desc = desc[desc["species_key"] == args.species].copy()
    desc["snap"] = desc["height_m"].map(pt.height_label)
    keys = [k for k in DEFINITIONS if k not in NOT_VALIDATED and k in desc]

    gen_rows, val_rows, sheet = [], [], {}
    for hc, cell in index.groupby("height_class"):
        if len(cell) < args.min_trees:
            continue
        model = bm.fit([events[u] for u in cell["tree_uid"]], species, args.species, hc)
        model.save(out / "models" / f"{title}_{hc}.pkl")
        model.chain_table().to_csv(
            out / "models" / f"{title}_{hc}_chain.csv", index=False
        )
        height = model.height_m
        from growpy.utils.allometry import get_height_dbh_model

        dbh_model = get_height_dbh_model(args.species)
        dbh = float(dbh_model["a"] * height ** dbh_model["b"]) if dbh_model else 0.3
        tiles = []
        for s in range(args.samples):
            geo, radius, cyl = generated_tree(model, height, dbh, seed=s)
            gen_rows.append(
                {"height_class": hc, "seed": s, **describe(cyl, **pt.PRUNE)}
            )
            if s < 3:
                tiles.append(
                    icons.tree_icon(
                        out / "tiles" / f"{title}_{hc}_model{s:02d}_front.png",
                        geo,
                        radius,
                    )
                )
        sheet[hc] = (tiles, len(cell), height)
        gen = pd.DataFrame([r for r in gen_rows if r["height_class"] == hc])
        real = desc[
            (desc["source_kind"] == "scan") & desc["tree_uid"].isin(cell["tree_uid"])
        ]
        grove = desc[(desc["source_kind"] == "generated") & (desc["snap"] == hc)]
        for k in keys:
            val_rows.append(
                {
                    "height_class": hc,
                    "descriptor": k,
                    "real_p50": float(real[k].median()),
                    "model_p50": float(gen[k].median()) if k in gen else float("nan"),
                    "grove_p50": float(grove[k].median())
                    if len(grove)
                    else float("nan"),
                    "z_model": robust_z(gen[k], real[k]) if k in gen else float("nan"),
                    "z_grove": robust_z(grove[k], real[k])
                    if len(grove)
                    else float("nan"),
                    "n_real": int(real[k].notna().sum()),
                    "n_grove": len(grove),
                }
            )
        v = pd.DataFrame([r for r in val_rows if r["height_class"] == hc])
        zm, zg = v["z_model"].abs(), v["z_grove"].abs()
        print(
            f"  {hc}: n={len(cell)} H={height:.1f} m | |z|<1: model {np.mean(zm.dropna() < 1):.0%}"
            f" (median |z| {zm.median():.2f}), Grove {np.mean(zg.dropna() < 1):.0%}"
            f" (median |z| {zg.median():.2f}, n={len(grove)})",
            flush=True,
        )
    pd.DataFrame(gen_rows).to_csv(out / "generated_descriptors.csv", index=False)
    pd.DataFrame(val_rows).to_csv(out / "validation.csv", index=False)

    cols = sorted(sheet)
    rows = []
    if args.catalog is not None and args.catalog.is_dir():
        from growpy.tools.qsm_prototypes import _catalog_icon

        rows.append(
            (
                f"catalog\n(Grove {args.catalog_radius})",
                [
                    (
                        _catalog_icon(
                            args.catalog, args.catalog_radius, args.species, h
                        ),
                        "",
                    )
                    for h in cols
                ],
            )
        )
    if args.prototypes_dir is not None:
        for label, kind in (("real medoid", "medoid"), ("prototype", "proto")):
            rows.append(
                (
                    label,
                    [
                        (
                            args.prototypes_dir
                            / "tiles"
                            / f"{title}_qsm_{h}_w0_{kind}_front.png",
                            "",
                        )
                        for h in cols
                    ],
                )
            )
    for s in range(3):
        rows.append(
            (
                f"model sample {s + 1}",
                [
                    (
                        sheet[h][0][s] if s < len(sheet[h][0]) else None,
                        f"n={sheet[h][1]}  H {sheet[h][2]:.1f} m" if s == 0 else "",
                    )
                    for h in cols
                ],
            )
        )
    icons.compose(
        out / f"{title}_model_sheet.png",
        rows,
        cols,
        tile_px=256,
        title=f"{title.replace('_', ' ')}: stochastic branching model (L-Py) vs real and Grove",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
