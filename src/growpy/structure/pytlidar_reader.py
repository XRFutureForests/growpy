"""PyTLidar output (the Python port of TreeQSM) -> ``RawQsm``, so our own fits of real and
synthetic clouds go through ``standardize`` and the descriptors like every published QSM.

PyTLidar 1.1.2 writes, per model, ``cylinder_<name>_t<tree>_m<model>.txt``: a tab-separated
table with a one-line header and 17 columns, ``radius``, ``length``, ``start`` (x, y, z),
``axis`` (x, y, z), ``parent`` (0-based row, -1 for the base), ``extension`` (the row that
continues this cylinder, 0 for none), ``branch`` (0 = trunk), ``branch_order``,
``position_in_branch``, ``mad``, ``SurfCov``, ``added`` and ``UnmodRadius``. Its default
inputs keep TreeQSM's taper correction on, so ``radius`` is corrected and ``UnmodRadius``
is the fitted value, as in a TreeQSM ``.mat``.

``pytlidar_trees`` standardises a set of such files with caller-given metadata (identity,
species, tier), e.g. BioDiv clouds and synthetic scans fitted with one setting (XRFF-575).
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure.schema import QsmTree
from growpy.structure.standardize import RawQsm, standardize

N_COLUMNS = 17


def read_pytlidar_txt(path: str | Path, version: str = "PyTLidar 1.1.2") -> RawQsm:
    """One PyTLidar ``cylinder_*.txt`` model."""
    data = np.loadtxt(path, skiprows=1, ndmin=2)
    if data.shape[1] != N_COLUMNS:
        raise ValueError(
            f"{Path(path).name}: {data.shape[1]} columns, expected {N_COLUMNS}"
        )
    frame: dict = {
        "radius": data[:, 0],
        "length": data[:, 1],
        "parent": data[:, 8].astype(np.int64),
        # 0 marks a tip: row 0 is the base and never continues another cylinder
        "src_extension": np.where(data[:, 9] > 0, data[:, 9], -1).astype(np.int64),
        "src_branch": data[:, 10].astype(np.int64),
        "src_order": data[:, 11].astype(np.int64),
        "src_pos": data[:, 12].astype(np.int64),
        "is_virtual": data[:, 15].astype(bool),
        "radius_raw": data[:, 16],
    }
    for i, c in enumerate("xyz"):
        frame[f"start_{c}"] = data[:, 2 + i]
        frame[f"axis_{c}"] = data[:, 5 + i]
    return RawQsm(
        pd.DataFrame(frame),
        {
            "qsm_tool": "PyTLidar",
            "qsm_version": version,
            "qsm_format": "pytlidar_txt",
            "radius_correction": "treeqsm_taper",
        },
    )


def pytlidar_trees(
    files: Iterable[str | Path], meta_of: Callable[[Path], dict]
) -> Iterator[QsmTree]:
    """Standardised trees from PyTLidar cylinder files; ``meta_of(path)`` gives the
    ``TREE_COLUMNS`` identity of each (``tree_uid``, source, species, tier, ...). A file
    that fails to read or standardise is reported and skipped."""
    for path in map(Path, files):
        try:
            yield standardize(read_pytlidar_txt(path), meta_of(path))
        except Exception as exc:  # noqa: BLE001 - one bad model must not end a batch
            print(f"skip {path.name}: {exc}", file=sys.stderr)
