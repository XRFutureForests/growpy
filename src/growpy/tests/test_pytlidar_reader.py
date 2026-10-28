"""PyTLidar cylinder text -> standardised tree (growpy.structure.pytlidar_reader)."""

from __future__ import annotations

import numpy as np
import pytest

from growpy.structure.pytlidar_reader import pytlidar_trees, read_pytlidar_txt

HEADER = (
    "radius (m)\tlength (m)\tstart_point\taxis_direction\tparent\textension\tbranch\t"
    "branch_order\tposition_in_branch\tmad\tSurfCov\tadded\tUnmodRadius (m)\n"
)


def _write(path):
    """A 5 m trunk of 1, 1 and 3 m cylinders (r 0.15, 0.14, 0.13) and a 1 m horizontal
    first-order branch from the top of the second, offset 10 m in x like a site frame."""
    rows = [
        # r, L, start xyz, axis xyz, parent, extension, branch, order, pos, mad, cov, added, r0
        (0.15, 1.0, 10, 0, 0, 0, 0, 1, -1, 1, 0, 0, 1, 0, 1, 0, 0.16),
        (0.14, 1.0, 10, 0, 1, 0, 0, 1, 0, 2, 0, 0, 2, 0, 1, 0, 0.14),
        (0.13, 3.0, 10, 0, 2, 0, 0, 1, 1, 0, 0, 0, 3, 0, 1, 0, 0.13),
        (0.05, 1.0, 10, 0, 2, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0.05),
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER)
        for r in rows:
            f.write("\t".join(str(float(v)) for v in r) + "\n")


def test_read_pytlidar_txt(tmp_path):
    path = tmp_path / "cylinder_toy_t1_m1.txt"
    _write(path)
    raw = read_pytlidar_txt(path)
    cyl = raw.cyl
    assert list(cyl["parent"]) == [-1, 0, 1, 1]
    assert list(cyl["src_extension"]) == [1, 2, -1, -1]  # 0 = none in the file
    assert list(cyl["src_order"]) == [0, 0, 0, 1]
    assert list(cyl["is_virtual"]) == [False, False, False, True]
    assert cyl["radius_raw"].iloc[0] == pytest.approx(0.16)
    assert raw.info["qsm_tool"] == "PyTLidar"


def test_pytlidar_trees_standardises(tmp_path):
    path = tmp_path / "cylinder_toy_t1_m1.txt"
    _write(path)
    meta = {"tree_uid": "toy:1", "source": "toy", "source_kind": "scan"}
    tree = next(pytlidar_trees([path], lambda p: meta))
    assert tree.meta["height_m"] == pytest.approx(5.0)
    assert tree.meta["dbh_m"] == pytest.approx(
        0.28
    )  # the second cylinder spans 1.1-1.5 m
    assert tree.meta["trunk_length_m"] == pytest.approx(5.0)
    assert tree.meta["branch_length_m"] == pytest.approx(1.0)
    assert tree.meta["base_x_src"] == pytest.approx(10.0)  # moved to the origin
    assert np.isclose(tree.cyl["start_x"].min(), 0.0)


def test_bad_file_is_skipped(tmp_path, capsys):
    bad = tmp_path / "cylinder_bad_t1_m1.txt"
    bad.write_text(HEADER + "1 2 3\n", encoding="utf-8")
    assert list(pytlidar_trees([bad], lambda p: {})) == []
    assert "skip cylinder_bad" in capsys.readouterr().err
