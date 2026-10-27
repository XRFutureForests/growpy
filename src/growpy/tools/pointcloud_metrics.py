"""L2 structure metrics of single-tree point clouds (``growpy.structure.pointcloud``).

    growpy-pointcloud-metrics <cloud> [<cloud> ...] --out <metrics.csv>
    growpy-pointcloud-metrics <dir>/*.npy --out <csv> --voxel 0.1 --alpha 1.0

Clouds: ``.npy``, ``.xyz``/``.txt``/``.csv``, ``.ply``, and ``.las``/``.laz`` when laspy
is installed. Metres, z up, one leaf-off tree per file; the same code serves real and
synthetic scans. ``--keep-connected`` first drops points not connected to the stem
(``keep_connected``). One row per cloud, ``tree_id`` from the file name (a trailing ``_TLS``
is dropped), clouds read one at a time.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from growpy.structure.pointcloud import (
    ALPHA_M,
    MIN_BOX_M,
    N_BINS,
    VOXEL_M,
    keep_connected,
    metrics,
    read_points,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("clouds", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--voxel", type=float, default=VOXEL_M)
    parser.add_argument("--alpha", type=float, default=ALPHA_M)
    parser.add_argument("--min-box", type=float, default=MIN_BOX_M)
    parser.add_argument("--bins", type=int, default=N_BINS)
    parser.add_argument(
        "--keep-connected",
        action="store_true",
        help="drop points not connected to the stem (0.2 m voxels) before measuring",
    )
    args = parser.parse_args(argv)
    rows = []
    for path in args.clouds:
        t0 = time.perf_counter()
        try:
            pts = read_points(path)
            n_raw = len(pts)
            if args.keep_connected:
                pts = keep_connected(pts)
            row = metrics(pts, args.voxel, args.alpha, args.min_box, args.bins)
            row["L2.n_points_raw"] = n_raw
        except (ValueError, OSError) as exc:
            print(f"{path.name}: skipped ({exc})")
            continue
        tree_id = path.stem.removesuffix("_TLS")
        rows.append({"tree_id": tree_id, "file": path.name, **row})
        print(
            f"{tree_id}: {row['L2.n_points']} pts, h {row['L2.height_m']:.1f} m, "
            f"Db {row['L2.box_dimension']:.3f}, {time.perf_counter() - t0:.1f} s"
        )
    if not rows:
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False, float_format="%.5g")
    print(f"{len(rows)} clouds -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
