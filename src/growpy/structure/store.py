"""Write and read a standardised dataset: two flat files and a schema note.

    <out>/trees.csv           one row per tree, ``TREE_COLUMNS``
    <out>/cylinders.csv.gz    one row per cylinder, ``tree_uid`` + ``CYL_COLUMNS``
    <out>/schema.json         columns, frame, tier meaning, units

Plain CSV keeps it readable from R, the database importers and a spreadsheet, and needs no
dependency beyond pandas (the environment has no pyarrow). Rows of one tree are
contiguous, so ``iter_trees`` streams a 3,000-tree dataset without loading it.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

import pandas as pd

from growpy.structure.schema import CYL_COLUMNS, TIERS, TREE_COLUMNS, QsmTree

FRAME = "metres, z up, tree base (start of the trunk's first cylinder) at the origin"


def write_dataset(trees: Iterable[QsmTree], out_dir: Path) -> int:
    """Stream ``trees`` into ``out_dir``; returns the number written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with gzip.open(
        out_dir / "cylinders.csv.gz", "wt", encoding="utf-8", newline=""
    ) as gz:
        first = True
        seen: set[str] = set()
        for tree in trees:
            uid = tree.meta["tree_uid"]
            if uid in seen:  # two trees under one uid would merge their cylinders
                raise ValueError(f"duplicate tree_uid {uid!r}")
            seen.add(uid)
            rows.append(tree.meta)
            frame = tree.cyl.copy()
            frame.insert(0, "tree_uid", tree.meta["tree_uid"])
            frame.to_csv(gz, header=first, index=False, float_format="%.5f")
            first = False
    pd.DataFrame(rows, columns=TREE_COLUMNS).to_csv(
        out_dir / "trees.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    (out_dir / "schema.json").write_text(
        json.dumps(
            {
                "frame": FRAME,
                "tiers": TIERS,
                "tree_columns": TREE_COLUMNS,
                "cylinder_columns": ["tree_uid", *CYL_COLUMNS],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(rows)


def read_trees(dataset_dir: Path) -> pd.DataFrame:
    return pd.read_csv(dataset_dir / "trees.csv")


def iter_trees(dataset_dir: Path, chunk_rows: int = 500_000) -> Iterator[QsmTree]:
    """Stream ``QsmTree`` objects (meta from ``trees.csv``, cylinders from the gzip)."""
    meta = read_trees(dataset_dir).set_index("tree_uid", drop=False)
    carry: pd.DataFrame | None = None
    for chunk in pd.read_csv(dataset_dir / "cylinders.csv.gz", chunksize=chunk_rows):
        if carry is not None:
            chunk = pd.concat([carry, chunk], ignore_index=True)
        last = chunk["tree_uid"].iloc[-1]
        carry = chunk[chunk["tree_uid"] == last]  # may continue in the next chunk
        for uid, frame in chunk[chunk["tree_uid"] != last].groupby(
            "tree_uid", sort=False
        ):
            yield QsmTree(
                meta.loc[uid].to_dict(),
                frame.drop(columns="tree_uid").reset_index(drop=True),
            )
    if carry is not None and len(carry):
        uid = carry["tree_uid"].iloc[0]
        yield QsmTree(
            meta.loc[uid].to_dict(),
            carry.drop(columns="tree_uid").reset_index(drop=True),
        )
