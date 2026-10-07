"""Prototype silhouettes of real trees per species x height class x crown-width class.

    growpy-qsm-prototypes --descriptors <descriptors.csv> --standardized <dir> --out-dir <dir>
        [--species norway_spruce european_beech] [--catalog data/output/forest --catalog-radius r07]
        [--grove-lane <sweep dir> --grove-arms base_s512 C8_s512]

Groups come from the descriptor table (``growpy-qsm-descriptors``): height classes snap like
``dataset_overview.md`` (``h20m`` = 17.5-22.5 m), ``w0`` is the whole cell and ``w1..w3`` its
crown-width tertiles. Cylinders are streamed once from the standardised datasets
(``growpy-qsm-standardize``), at most ``--max-per-group`` trees per width class.

Writes, under ``--out-dir``:
  tiles/<Species>_qsm_<hNNm>_<w>_{proto,medoid,occupancy}_front.png   catalog-icon style
  tiles/<Species>_qsm_<hNNm>_<w>_curves.png                            unrolled branches
  grids/<Species>_<w>.png, verify_<Species>_<hNNm>.png                 composed sheets
  branch_curves.csv   median / p25 / p75 unrolled first-order branch per crown decile
  second_order.csv    median second-order branch per third of its parent limb
  groups.csv          per group: n, tiers, median height, yield-table DBH, medoid
  grove/              Grove trees: plain and overlay tiles, curves, grove_scores.csv
  prototype_overview.md
Radii are synthetic (pipe model from DBH); see ``growpy.structure.prototypes``.
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure import prototype_icons as icons
from growpy.structure import prototypes as pt
from growpy.structure.sources import growpy_forest
from growpy.structure.store import iter_trees

VIEW = "front"
# best-ranked trees per group kept drawable, from which the medoid + neighbours are drawn
GEOMETRY_CANDIDATES = 25
CATALOG_GLOB = "*_{h}_*_icon_front.png"


def _yield_dbh(species: str, height: float) -> float:
    from growpy.utils.allometry import get_height_dbh_model

    model = get_height_dbh_model(species)
    return float(model["a"] * height ** model["b"]) if model else float("nan")


def _sample(groups: pd.DataFrame, cap: int, seed: int) -> pd.DataFrame:
    """At most ``cap`` trees per width tertile; ``w0`` keeps the union of its tertiles'
    samples (or ``cap`` of its own when the cell has no tertiles)."""
    rng = np.random.default_rng(seed)
    keep = []
    for _, g in groups.groupby(["species_key", "height_class", "width_class"]):
        if g["width_class"].iloc[0] == "w0":
            continue
        keep.append(
            g if len(g) <= cap else g.iloc[rng.choice(len(g), cap, replace=False)]
        )
    tert = pd.concat(keep) if keep else groups.iloc[:0]
    out = [tert]
    for (sp, hc), g in groups[groups["width_class"] == "w0"].groupby(
        ["species_key", "height_class"]
    ):
        t = tert[(tert["species_key"] == sp) & (tert["height_class"] == hc)]
        if len(t):
            out.append(g[g["tree_uid"].isin(t["tree_uid"])])
        else:
            out.append(
                g if len(g) <= cap else g.iloc[rng.choice(len(g), cap, replace=False)]
            )
    return pd.concat(out, ignore_index=True)


def _stream(std_dir: Path, wanted: set[str], geometry_for: set[str]) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for ds in sorted(
        p for p in std_dir.iterdir() if p.is_dir() and p.name != "growpy_forest"
    ):
        uids = set(pd.read_csv(ds / "trees.csv", usecols=["tree_uid"])["tree_uid"])
        todo = wanted & uids
        if not todo:
            continue
        print(f"  {ds.name}: {len(todo)} trees", flush=True)
        for tree in iter_trees(ds):
            uid = tree.meta["tree_uid"]
            if uid not in todo:
                continue
            prof = pt.tree_profile(tree.cyl, keep_geometry=uid in geometry_for)
            if prof is not None:
                prof["dbh_m"] = float(tree.meta.get("dbh_m") or np.nan)
                profiles[uid] = prof
            todo.discard(uid)
            if not todo:
                break
    return profiles


def _outline(desc_rows: pd.DataFrame, height: float) -> tuple[np.ndarray, np.ndarray]:
    """Median crown outline in metres: z and half width per crown-depth tenth (top first),
    closed at the apex."""
    ratio = float(desc_rows["L1.crown_ratio"].median())
    widths = np.array(
        [
            float(desc_rows[f"L1.crown_width_rel_d{k:02d}"].median())
            for k in range(1, 11)
        ]
    )
    z = height * (1 - (np.arange(10) + 0.5) / 10 * ratio)
    return np.concatenate([[height], z]), np.concatenate([[0.0], widths * height / 2])


def _tile(out: Path, sp: str, hc: str, w: str, kind: str) -> Path:
    return out / "tiles" / f"{pt.species_title(sp)}_qsm_{hc}_{w}_{kind}_{VIEW}.png"


def _catalog_icon(catalog: Path | None, radius: str, sp: str, hc: str) -> Path | None:
    if catalog is None:
        return None
    hits = sorted((catalog / sp / radius).glob(CATALOG_GLOB.format(h=hc)))
    return hits[0] if hits else None


def build_groups(
    desc, groups, sample, profiles, out: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Height, outline and medoid ranking use the whole group (descriptor table);
    occupancy and curves use the profiled sample."""
    curve_rows, summary, outlines, seconds, fork_sets = [], [], {}, {}, {}
    for (sp, hc, w), g in groups.groupby(
        ["species_key", "height_class", "width_class"]
    ):
        s = sample[
            (sample["species_key"] == sp)
            & (sample["height_class"] == hc)
            & (sample["width_class"] == w)
        ]
        profs = [profiles[u] for u in s["tree_uid"] if u in profiles]
        if len(profs) < pt.MIN_GROUP:
            continue
        rows = desc.loc[g["tree_uid"]]
        height = float(rows["height_m"].median())
        crown_base_rel = float(
            np.nanmedian([p["crown_base_m"] / p["height_m"] for p in profs])
        )
        curves = pt.group_curves(profs)
        for c in ("species_key", "height_class", "width_class"):
            curves.insert(
                0, c, {"species_key": sp, "height_class": hc, "width_class": w}[c]
            )
        curve_rows.append(curves)
        second = pt.group_second_order(profs)
        seconds[(sp, hc, w)] = second
        # forks and stem wander for broadleaves only: in conifer QSMs the hidden
        # upper stem breaks into offset pieces that the fork rule would mistake for
        # co-dominant leaders (76 % of Kew spruce at 20 m would 'fork')
        broadleaf = (rows["leaf_type"] == "broadleaf").mean() > 0.5
        forks = pt.group_forks(profs) if broadleaf else None
        fork_sets[(sp, hc, w)] = forks
        dbh = _yield_dbh(sp, height)
        # view 2: template tree, pipe radii from the yield-table DBH at the median height
        # broadleaves: branches reach the median crown outline (see template_tree)
        envelope = _outline(rows, 1.0) if broadleaf else None
        tmpl = pt.template_tree(curves, height, crown_base_rel, second, forks, envelope)
        r_tmpl = pt.pipe_radii(tmpl.start, tmpl.end, tmpl.parent, tmpl.trunk_rows, dbh)
        icons.tree_icon(_tile(out, sp, hc, w, "proto"), tmpl, r_tmpl)
        # view 1: occupancy with the median crown outline
        icons.occupancy_icon(
            _tile(out, sp, hc, w, "occupancy"),
            pt.group_occupancy(profs),
            height,
            _outline(rows, height),
        )
        outlines[(sp, hc, w)] = _outline(rows, 1.0)  # relative to height
        # view 3: medoid (nearest the group median in the descriptor vector) + neighbours
        ranked = pt.rank_medoids(rows).sort_values()
        drawable = [
            u for u in ranked.index if u in profiles and "geometry" in profiles[u]
        ]
        clean = pt.clean_stems({u: profiles[u] for u in s["tree_uid"] if u in profiles})
        drawn = [u for u in drawable if u in clean]
        drawn += [u for u in drawable if u not in clean]
        for k, uid in enumerate(drawn[:4]):
            p = profiles[uid]
            geo = p["geometry"]
            r = pt.pipe_radii(
                geo.start, geo.end, geo.parent, geo.trunk_rows, p["dbh_m"]
            )
            kind = "medoid" if k == 0 else f"neighbour{k}"
            icons.tree_icon(_tile(out, sp, hc, w, kind), geo, r)
        icons.curves_figure(
            out / "tiles" / f"{pt.species_title(sp)}_qsm_{hc}_{w}_curves.png",
            curves,
            f"{sp} {hc} {w} ({pt.WIDTH_LABELS[w]}): unrolled first-order branches, n={len(profs)}",
            [(f"medoid {drawn[0]}", profiles[drawn[0]])] if drawn else None,
        )
        summary.append(
            {
                "species_key": sp,
                "height_class": hc,
                "width_class": w,
                "n_group": int(g["n"].iloc[0]),
                "n_profiled": len(profs),
                "tiers": g["tiers"].iloc[0],
                "sources": ",".join(sorted(set(rows["source"]))),
                "height_m_p50": height,
                "crown_width_over_height_p50": float(
                    rows["L1.crown_width_over_height"].median()
                ),
                "crown_width_over_height_min": float(
                    rows["L1.crown_width_over_height"].min()
                ),
                "crown_width_over_height_max": float(
                    rows["L1.crown_width_over_height"].max()
                ),
                "crown_base_rel_p50": crown_base_rel,
                "dbh_yield_m": dbh,
                "dbh_qsm_m_p50": float(rows["dbh_m"].median()),
                "medoid": drawn[0] if drawn else "",
                "neighbours": ";".join(drawn[1:4]),
                "fork_rate": forks["rate"] if forks else float("nan"),
                "forks_per_tree": forks["n"] if forks else 0,
                "fork_z_rel": (
                    ";".join(f"{z:.3f}" for z in forks["z_rel"]) if forks else ""
                ),
                "fork_len_rel": forks["len_rel"] if forks else float("nan"),
                "fork_share": forks["share"] if forks else float("nan"),
                "stem_offset_top_rel": (
                    float(forks["stem_offset"][-1]) if forks else float("nan")
                ),
            }
        )
        print(f"  {sp} {hc} {w}: n={len(profs)} H={height:.1f} m", flush=True)
    curves_all = pd.concat(curve_rows, ignore_index=True)
    return curves_all, pd.DataFrame(summary), outlines, seconds, fork_sets


def grove_overlays(
    args,
    curves: pd.DataFrame,
    summary: pd.DataFrame,
    outlines: dict,
    seconds: dict,
    fork_sets: dict,
    out: Path,
) -> pd.DataFrame:
    """Score every Grove tree's leading branches against the real w0 curves of its
    species and height class; for ``--grove-icons`` stages also draw it plainly (Grove
    radii, as the catalog icon) and over the real template and median crown outline,
    both scaled to the Grove tree's own height (shape relative to height)."""
    rows = []
    gdir = out / "grove"
    for arm in args.grove_arms:
        forest = args.grove_lane / arm / "forest"
        if not forest.is_dir():
            print(f"  grove arm {arm}: no forest dir, skipped", flush=True)
            continue
        for tree in growpy_forest(forest):
            sp = tree.meta.get("species_key")
            stage = tree.meta.get("height_m_reported")
            if sp is None or stage is None:
                continue
            hc = pt.height_label(float(stage))
            real = curves[
                (curves["species_key"] == sp)
                & (curves["height_class"] == hc)
                & (curves["width_class"] == "w0")
            ]
            prof = pt.tree_profile(tree.cyl, keep_geometry=True)
            if prof is None:
                continue
            if len(real):
                score = pt.score_curves(prof, real)
                for _, s in score.iterrows():
                    rows.append(
                        {"arm": arm, "species_key": sp, "height_class": hc, **s}
                    )
            if args.grove_icons and hc in args.grove_icons:
                stem = f"{arm}_{pt.species_title(sp)}_{hc}"
                # plain: the whole Grove tree with Grove's own radii, as the catalog icon
                full = pt.geometry(tree.cyl, max_order=None)
                icons.tree_icon(gdir / f"{stem}_grove_{VIEW}.png", full, full.radius)
                # structure only: both re-radiused by the pipe rule, common prune
                grp = summary[
                    (summary["species_key"] == sp)
                    & (summary["height_class"] == hc)
                    & (summary["width_class"] == "w0")
                ]
                geo = prof["geometry"]
                dbh = float(
                    tree.meta.get("dbh_m_reported") or _yield_dbh(sp, prof["height_m"])
                )
                r_geo = pt.pipe_radii(
                    geo.start, geo.end, geo.parent, geo.trunk_rows, dbh
                )
                if len(grp) and len(real):
                    g = grp.iloc[0]
                    h = prof["height_m"]
                    tmpl = pt.template_tree(
                        real,
                        h,
                        g["crown_base_rel_p50"],
                        seconds.get((sp, hc, "w0")),
                        fork_sets.get((sp, hc, "w0")),
                        outlines[(sp, hc, "w0")]
                        if fork_sets.get((sp, hc, "w0")) is not None
                        else None,
                    )
                    r_t = pt.pipe_radii(
                        tmpl.start, tmpl.end, tmpl.parent, tmpl.trunk_rows, dbh
                    )
                    z_rel, half_rel = outlines[(sp, hc, "w0")]
                    icons.overlay_icon(
                        gdir / f"{stem}_overlay_{VIEW}.png",
                        (tmpl, r_t),
                        (geo, r_geo),
                        outline=(z_rel * h, half_rel * h),
                    )
                    icons.curves_figure(
                        gdir / f"{stem}_curves.png",
                        real,
                        f"{arm} vs real {sp} {hc} (w0)",
                        [(arm, prof)],
                    )
        print(f"  grove arm {arm}: done", flush=True)
    return pd.DataFrame(rows)


def write_overview(out: Path, summary: pd.DataFrame, args) -> Path:
    """``prototype_overview.md``: the same table shape as dataset_overview.md (columns =
    height classes, rows = species x crown-width class), one table per view."""
    cols = sorted(summary["height_class"].unique())
    lines = [
        "# QSM Prototype Overview",
        "",
        "Real-tree prototypes by species, crown-width class and height class (5 m steps, "
        "snapped like `dataset_overview.md`). Tiles are drawn in the catalog icon style "
        "(front view, 512 px, catalog brown, 30 m line-width reference, thinnest 25 % "
        "dropped). QSMs carry no foliage, so there are no twig tiles.",
        "",
        "Radii are **synthetic**: pipe model (area preserved at every fork, split by distal "
        "branch length) from the QSM's own DBH for real trees and from the yield-table DBH "
        "at the group's median height for prototypes. Trees are pruned to the common "
        "resolution (laterals >= 0.3 m, orders <= 2).",
        "",
        "Conifer QSMs miss branches (Kew spruce resolves ~2 first-order branches per metre "
        "against 8-12 in Grove): for spruce trust the occupancy shape and the long-branch "
        "curves, not the branch count of the prototype. The QSMs also miss the thin, "
        "drooping branch ends, so real tips likely sag more than the curves show.",
        "",
        "The prototype skeleton is an excurrent abstraction: a straight trunk carrying, per "
        "crown decile, each tree's farthest-reaching first-order branch as a median curve. "
        "For broadleaves, whose crowns dissolve into forks, read the occupancy map and the "
        "medoid first and the prototype only as per-decile branch shape.",
        "",
    ]
    views = [
        ("Prototype skeleton (view 2)", "proto"),
        ("Real medoid tree (view 3)", "medoid"),
        ("Occupancy and median crown outline (view 1)", "occupancy"),
    ]
    header = f"| Species | Width | {' | '.join(cols)} |"
    sep = f"| {' | '.join(['---'] * (2 + len(cols)))} |"
    if args.catalog is not None:
        lines += [
            f"## Catalog icons (Grove, {args.catalog_radius}) for reference",
            "",
            header,
            sep,
        ]
        for sp in sorted(summary["species_key"].unique()):
            cells = []
            for hc in cols:
                icon = _catalog_icon(args.catalog, args.catalog_radius, sp, hc)
                cells.append(
                    f"![{hc}]({Path(os.path.relpath(icon, out)).as_posix()})"
                    if icon
                    else ""
                )
            lines.append(
                f"| {sp.replace('_', ' ').title()} | catalog | {' | '.join(cells)} |"
            )
        lines.append("")
    for title, kind in views:
        lines += [f"## {title}", "", header, sep]
        for (sp, w), g in summary.groupby(["species_key", "width_class"]):
            by_h = g.set_index("height_class")
            cells = []
            for hc in cols:
                if hc not in by_h.index:
                    cells.append("")
                    continue
                r = by_h.loc[hc]
                rel = _tile(out, sp, hc, w, kind).relative_to(out).as_posix()
                cells.append(
                    f"![{hc}]({rel})<br>n={int(r['n_profiled'])} · H {r['height_m_p50']:.1f} m"
                )
            label = f"{w} {pt.WIDTH_LABELS[w]}"
            lines.append(
                f"| {sp.replace('_', ' ').title()} | {label} | {' | '.join(cells)} |"
            )
        lines.append("")
    lines += [
        "Median branch curves: [branch_curves.csv](branch_curves.csv). "
        "Groups: [groups.csv](groups.csv).",
        "",
    ]
    path = out / "prototype_overview.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def compose_sheets(out: Path, summary: pd.DataFrame, args) -> None:
    for (sp, w), g in summary.groupby(["species_key", "width_class"]):
        cols = sorted(g["height_class"])
        by_h = g.set_index("height_class")
        rows = []
        if args.catalog is not None:
            rows.append(
                (
                    f"catalog\n(Grove {args.catalog_radius})",
                    [
                        (_catalog_icon(args.catalog, args.catalog_radius, sp, h), "")
                        for h in cols
                    ],
                )
            )
        for label, kind in (
            ("real medoid", "medoid"),
            ("prototype", "proto"),
            ("occupancy", "occupancy"),
        ):
            rows.append(
                (
                    label,
                    [
                        (
                            _tile(out, sp, h, w, kind),
                            f"n={int(by_h.loc[h, 'n_profiled'])}  H {by_h.loc[h, 'height_m_p50']:.1f} m"
                            if kind == "proto"
                            else "",
                        )
                        for h in cols
                    ],
                )
            )
        icons.compose(
            out / "grids" / f"{pt.species_title(sp)}_{w}.png",
            rows,
            cols,
            tile_px=256,
            title=f"{sp.replace('_', ' ').title()}, {w} ({pt.WIDTH_LABELS[w]}): synthetic pipe-model radii",
        )
    # the verification sheet: catalog | medoid | prototype at 100 %, one per species
    for sp, g in summary[summary["width_class"] == "w0"].groupby("species_key"):
        hc = (
            args.verify_height
            if args.verify_height in set(g["height_class"])
            else g.sort_values("n_profiled")["height_class"].iloc[-1]
        )
        icons.compose(
            out / f"verify_{pt.species_title(sp)}_{hc}.png",
            [
                (
                    "",
                    [
                        (
                            _catalog_icon(args.catalog, args.catalog_radius, sp, hc),
                            f"catalog Grove {args.catalog_radius}",
                        ),
                        (
                            _tile(out, sp, hc, "w0", "medoid"),
                            "real medoid (QSM, pipe radii)",
                        ),
                        (
                            _tile(out, sp, hc, "w0", "proto"),
                            "prototype (median curves)",
                        ),
                    ],
                )
            ],
            [hc, "", ""],
            tile_px=icons.ICON_PX,
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--descriptors", type=Path, required=True)
    ap.add_argument("--standardized", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--species", nargs="*", default=["norway_spruce", "european_beech"])
    ap.add_argument("--max-per-group", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--catalog", type=Path, default=Path("data/output/forest"))
    ap.add_argument("--catalog-radius", default="r07")
    ap.add_argument("--verify-height", default="h20m")
    ap.add_argument("--grove-lane", type=Path)
    ap.add_argument("--grove-arms", nargs="*", default=[])
    ap.add_argument(
        "--grove-icons",
        nargs="*",
        default=["h20m", "h25m"],
        help="height classes that get Grove plain/overlay tiles (scores cover every stage)",
    )
    ap.add_argument(
        "--reuse-profiles", action="store_true", help="skip streaming if cached"
    )
    args = ap.parse_args(argv)
    if args.catalog is not None and not args.catalog.is_dir():
        args.catalog = None
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    desc = pd.read_csv(args.descriptors, low_memory=False)
    desc = desc[desc["species_key"].isin(args.species)]
    groups = pt.select_groups(desc)
    if groups.empty:
        print("no group with enough trees", file=sys.stderr)
        return 1
    desc = desc.set_index("tree_uid", drop=False)
    sample = _sample(groups, args.max_per_group, args.seed)
    # medoid candidates are ranked on the FULL group; the best ones are always profiled
    geometry_for: set[str] = set()
    for _, g in groups.groupby(["species_key", "height_class", "width_class"]):
        ranked = pt.rank_medoids(desc.loc[g["tree_uid"]]).sort_values()
        geometry_for |= set(ranked.index[:GEOMETRY_CANDIDATES])
    extra = groups[groups["tree_uid"].isin(geometry_for)]
    sample = pd.concat([sample, extra]).drop_duplicates(
        ["tree_uid", "species_key", "height_class", "width_class"]
    )
    cache = out / "profiles.pkl"
    if args.reuse_profiles and cache.exists():
        profiles = pickle.loads(cache.read_bytes())
    else:
        print(f"streaming {sample['tree_uid'].nunique()} trees", flush=True)
        profiles = _stream(args.standardized, set(sample["tree_uid"]), geometry_for)
        cache.write_bytes(pickle.dumps(profiles))
    curves, summary, outlines, seconds, fork_sets = build_groups(
        desc, groups, sample, profiles, out
    )
    curves.to_csv(out / "branch_curves.csv", index=False)
    second_rows = [
        f.assign(species_key=k[0], height_class=k[1], width_class=k[2])
        for k, f in seconds.items()
        if len(f)
    ]
    if second_rows:
        pd.concat(second_rows).to_csv(out / "second_order.csv", index=False)
    summary.to_csv(out / "groups.csv", index=False)
    if args.grove_lane and args.grove_arms:
        scores = grove_overlays(
            args, curves, summary, outlines, seconds, fork_sets, out
        )
        if len(scores):
            scores.to_csv(out / "grove" / "grove_scores.csv", index=False)
    compose_sheets(out, summary, args)
    print(write_overview(out, summary, args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
