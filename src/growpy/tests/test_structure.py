"""growpy.structure: axis rule, standardisation, TreeQSM .mat layouts, species, store."""

import io
import json

import numpy as np
import pandas as pd
import pytest
import scipy.io as sio

from growpy.structure.axes import assign_axes, axis_table
from growpy.structure.exchange import from_exchange, to_exchange
from growpy.structure.growth_json import to_growth_json
from growpy.structure.readers import read_growth_json, read_treeqsm_mat
from growpy.structure.schema import CYL_COLUMNS, normalize_species
from growpy.structure.standardize import RawQsm, standardize
from growpy.structure.store import iter_trees, write_dataset


def _raw() -> RawQsm:
    """Trunk of three 1 m cylinders at (10, 20, 5); a thick 0.5 m side branch off cylinder 1."""
    rows = [
        # parent, start xyz, axis xyz, length, radius
        (-1, (10, 20, 5), (0, 0, 1), 1.0, 0.10),
        (0, (10, 20, 6), (0, 0, 1), 1.0, 0.09),
        (1, (10, 20, 7), (0, 0, 1), 1.0, 0.08),
        (1, (10, 20, 6.5), (1, 0, 0), 0.5, 0.12),  # thicker than the trunk above it
    ]
    df = pd.DataFrame(
        {
            "parent": [r[0] for r in rows],
            "start_x": [r[1][0] for r in rows],
            "start_y": [r[1][1] for r in rows],
            "start_z": [r[1][2] for r in rows],
            "axis_x": [r[2][0] for r in rows],
            "axis_y": [r[2][1] for r in rows],
            "axis_z": [r[2][2] for r in rows],
            "length": [r[3] for r in rows],
            "radius": [r[4] for r in rows],
        }
    )
    return RawQsm(df, {"qsm_tool": "TreeQSM"})


def test_longer_subtree_continues_the_axis_even_when_the_other_child_is_thicker():
    axes, continues = assign_axes(
        np.array([-1, 0, 1, 1]),
        np.array([1.0, 1.0, 1.0, 0.5]),
        np.array([0.1, 0.09, 0.08, 0.12]),
    )
    assert continues[1] == 2  # the radius rule would have picked cylinder 3
    assert list(axes["axis_order"]) == [0, 0, 0, 1]
    assert list(axes["axis_pos"]) == [0, 1, 2, 0]
    assert axes["subtree_length"].iloc[0] == pytest.approx(3.5)


def test_axis_rule_rejects_cycles_and_bad_parents():
    with pytest.raises(ValueError):
        assign_axes(np.array([1, 0]), np.ones(2), np.ones(2))
    with pytest.raises(ValueError):
        assign_axes(np.array([-1, 5]), np.ones(2), np.ones(2))


def test_standardize_puts_the_base_at_the_origin_and_measures_the_cylinders():
    tree = standardize(_raw(), {"tree_uid": "t:1", "source": "t", "tier": "C"})
    cyl, meta = tree.cyl, tree.meta
    assert (cyl.loc[0, ["start_x", "start_y", "start_z"]] == 0).all()
    assert meta["base_z_src"] == 5 and meta["base_x_src"] == 10
    assert meta["height_m"] == pytest.approx(3.0)
    assert meta["volume_m3"] == pytest.approx(
        np.pi * (0.1**2 + 0.09**2 + 0.08**2 + 0.12**2 * 0.5)
    )
    assert meta["n_axes"] == 2 and meta["max_axis_order"] == 1
    # DBH: trunk cylinders overlapping 1.3 m +- 0.2 m, here only cylinder 1 (z 1..2)
    assert meta["dbh_m"] == pytest.approx(0.18)
    assert meta["n_roots"] == 1 and meta["gap_frac"] == 0.0
    table = axis_table(from_exchange(cyl))
    assert table.loc[1, "parent_axis"] == 0 and table.loc[1, "attach_cyl"] == 1


def test_exchange_table_speaks_the_rtwig_and_treeqsm_conventions():
    cyl = standardize(_raw(), {"tree_uid": "t:1"}).cyl
    assert list(cyl.columns) == CYL_COLUMNS
    assert list(cyl["id"]) == [1, 2, 3, 4]  # from 1
    assert list(cyl["parent"]) == [0, 1, 2, 2]  # 0 = base
    assert list(cyl["branch"]) == [1, 1, 1, 2]
    assert list(cyl["branch_order"]) == [0, 0, 0, 1]
    assert list(cyl["branch_position"]) == [1, 2, 3, 1]
    assert cyl["raw_radius"].isna().all() and cyl["src_branch"].isna().all()
    assert list(cyl["src_extension"]) == [0, 0, 0, 0]
    # axis is a unit vector for every row
    assert np.allclose(np.linalg.norm(cyl[["axis_x", "axis_y", "axis_z"]], axis=1), 1.0)


def test_zero_length_cylinder_gets_a_unit_axis_and_survives_the_round_trip():
    raw = _raw()
    del raw.cyl["axis_x"], raw.cyl["axis_y"], raw.cyl["axis_z"]
    raw.cyl["end_x"] = raw.cyl["start_x"]  # derive the ends ourselves: a vertical trunk
    raw.cyl["end_y"] = raw.cyl["start_y"]
    raw.cyl["end_z"] = raw.cyl["start_z"] + raw.cyl["length"]
    raw.cyl.loc[3, ["end_x", "end_y", "end_z", "length"]] = [10.0, 20.0, 6.5, 0.0]
    cyl = standardize(raw, {"tree_uid": "t:0len"}).cyl
    assert cyl.loc[3, "length"] == 0
    assert list(cyl.loc[3, ["axis_x", "axis_y", "axis_z"]]) == [0.0, 0.0, 1.0]
    back = from_exchange(cyl)
    assert list(back["parent"]) == [-1, 0, 1, 1]
    pd.testing.assert_frame_equal(to_exchange(back), cyl, check_dtype=False)


def test_loose_fragments_are_dropped_and_counted_and_parents_are_remapped():
    raw = _raw()
    frag = raw.cyl.iloc[[0]].copy()
    frag[["start_x", "start_y", "start_z", "length", "radius"]] = [50, 50, 0, 0.1, 0.02]
    frag["parent"] = -1
    # the fragment sits second in the table, so every later parent index shifts by one
    df = pd.concat([raw.cyl.iloc[[0]], frag, raw.cyl.iloc[1:]], ignore_index=True)
    df["parent"] = [-1, -1, 0, 2, 2]
    tree = standardize(RawQsm(df, {}), {"tree_uid": "t:frag"})
    assert tree.meta["n_roots"] == 2 and tree.meta["detached_cyl"] == 1
    assert tree.meta["detached_length_m"] == pytest.approx(0.1)
    assert tree.meta["n_cyl"] == 4 and tree.meta["n_axes"] == 2
    assert tree.meta["height_m"] == pytest.approx(3.0)
    assert list(tree.cyl["parent"]) == [0, 1, 2, 2]


def test_standardize_refuses_non_metre_input():
    raw = _raw()
    raw.cyl["radius"] = raw.cyl["radius"] * 1000  # millimetres
    with pytest.raises(ValueError, match="not metres"):
        standardize(raw, {"tree_uid": "t:1"})


def _cylinder_arrays(n):
    start = np.column_stack(
        [np.zeros(n), np.zeros(n), np.arange(n, dtype=float)]
    ).astype("f4")
    return {
        "start": start,
        "axis": np.tile(np.array([0, 0, 1], "f4"), (n, 1)),
        "length": np.ones(n, "f4"),
        "radius": np.full(n, 0.1, "f4"),
        "UnmodRadius": np.full(n, 0.12, "f4"),
        "parent": np.arange(
            n, dtype="u1"
        ),  # 1-based: cylinder i's parent is i (0 for the first)
        "extension": np.append(np.arange(2, n + 1), 0).astype("u1"),
        "added": np.zeros(n, "u1"),
        "branch": np.ones(n, "u2"),
        "BranchOrder": np.zeros(n, "u1"),
        "PositionInBranch": np.arange(1, n + 1, dtype="u1"),
    }


def _mat_bytes(mapping) -> bytes:
    buf = io.BytesIO()
    sio.savemat(buf, mapping)
    return buf.getvalue()


def test_treeqsm_struct_layout_converts_unsigned_one_based_indices():
    # uint8 0 - 1 would wrap to 255; the reader must cast to a signed type first
    raw = read_treeqsm_mat(_mat_bytes({"qsm": {"cylinder": _cylinder_arrays(4)}}))
    assert list(raw.cyl["parent"]) == [-1, 0, 1, 2]
    assert list(raw.cyl["src_extension"]) == [1, 2, 3, -1]
    assert raw.cyl["radius_raw"].iloc[0] == pytest.approx(0.12)
    assert raw.info["qsm_format"] == "treeqsm_mat_struct"


def test_treeqsm_flat_layout_with_a_single_branch():
    # an older-TreeQSM tree whose only branch is the trunk: scipy squeezes CiB to a flat array
    n = 4
    flat = {
        "Sta": _cylinder_arrays(n)["start"],
        "Axe": _cylinder_arrays(n)["axis"],
        "Rad": np.full(n, 0.1),
        "Len": np.ones(n),
        "CPar": np.arange(n, dtype="u1"),
        "CExt": np.append(np.arange(2, n + 1), 0).astype("u1"),
        "Added": np.zeros(n, "u1"),
        "BOrd": np.array([0], "u1"),
        "CiB": np.arange(1, n + 1, dtype="u1").reshape(1, n),
    }
    raw = read_treeqsm_mat(_mat_bytes(flat))
    assert raw.info["qsm_format"] == "treeqsm_mat_flat"
    assert list(raw.cyl["src_branch"]) == [1, 1, 1, 1]
    assert list(raw.cyl["src_pos"]) == [1, 2, 3, 4]
    assert "radius_raw" not in raw.cyl  # this layout keeps no unmodified radius
    assert standardize(raw, {"tree_uid": "t:1"}).cyl["raw_radius"].isna().all()


def test_growth_json_polylines_become_a_cylinder_tree(tmp_path):
    # y-up skeleton: trunk 0-1-2-3, a branch off vertex 1 (4, 5), one off the base (6)
    positions = [
        [0, 0, 0],
        [0, 1, 0],
        [0, 2, 0],
        [0, 3, 0],
        [1, 1.2, 0],
        [2, 1.4, 0],
        [0.5, 0.2, 0],
    ]
    radii = [0.10, 0.09, 0.08, 0.05, 0.04, 0.02, 0.03]
    data = {
        "points": {
            "positions": positions,
            "attributes": {"budLateralMeristem": {"values": [[r, 0] for r in radii]}},
        },
        "primitives": {"points": [[0, 1, 2, 3], [1, 4, 5], [0, 6]]},
    }
    path = tmp_path / "t_growth_data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    raw = read_growth_json(path)
    # trunk cylinders 0, 1, 2; branch 3, 4 (the first grows from the trunk cylinder that
    # ends at vertex 1); the base branch is 5 (it grows from the trunk's first cylinder)
    assert list(raw.cyl["parent"]) == [-1, 0, 1, 0, 3, 0]
    assert raw.cyl.loc[0, "end_z"] == 1.0  # grove y (up) is the exchange z
    assert raw.cyl.loc[0, "radius"] == pytest.approx(0.095)
    tree = standardize(raw, {"tree_uid": "g:1"})
    assert tree.meta["height_m"] == pytest.approx(3.0)
    assert tree.meta["qsm_tool"] == "The Grove"


def test_bridge_to_growth_json_and_back_keeps_the_structure(tmp_path):
    tree = standardize(_raw(), {"tree_uid": "t:1"})
    data = to_growth_json(tree.cyl)
    attrs = data["primitives"]["attributes"]
    assert attrs["branchNumber"]["values"] == [1, 2]
    assert attrs["branchParentNumber"]["values"] == [0, 1]  # Grove numbering
    assert attrs["branchHierarchyNumber"]["values"] == [1, 2]
    assert data["points"]["positions"][1] == [0.0, 1.0, 0.0]  # z up -> y up
    path = tmp_path / "t_growth_data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    back = standardize(read_growth_json(path), {"tree_uid": "t:1b"})
    for key in ("height_m", "n_axes", "max_axis_order", "trunk_length_m"):
        assert back.meta[key] == pytest.approx(tree.meta[key]), key
    assert list(back.cyl["branch_order"]) == list(tree.cyl["branch_order"])


def test_species_names_from_every_spelling_the_sources_use():
    assert normalize_species("Fagus_sylvatica")["species_key"] == "european_beech"
    assert normalize_species("Quercus_spec")["species_rank"] == "genus"
    assert normalize_species("Quercus_spec")["species_key"] == "european_oak"
    assert (
        normalize_species("Platanus × acerifolia")["species_latin"]
        == "Platanus acerifolia"
    )
    assert (
        normalize_species("Populus nigra 'Italica'")["species_latin"] == "Populus nigra"
    )
    picea = normalize_species("Picea abies")
    assert picea["leaf_type"] == "conifer" and picea["species_key"] == "norway_spruce"
    assert normalize_species("Betula_spec")["species_key"] is None  # no single preset
    assert normalize_species(None)["species_rank"] == "unknown"


def test_store_refuses_two_trees_under_one_uid(tmp_path):
    twins = [standardize(_raw(), {"tree_uid": "t:same"}) for _ in range(2)]
    with pytest.raises(ValueError, match="duplicate tree_uid"):
        write_dataset(twins, tmp_path)


def test_store_round_trip_streams_every_tree(tmp_path):
    trees = [
        standardize(_raw(), {"tree_uid": f"t:{i}", "source": "t", "tier": "C"})
        for i in range(3)
    ]
    assert write_dataset(trees, tmp_path) == 3
    back = list(iter_trees(tmp_path, chunk_rows=5))  # chunks split trees mid-way
    assert [t.meta["tree_uid"] for t in back] == ["t:0", "t:1", "t:2"]
    assert len(back[1].cyl) == 4
    assert back[2].meta["height_m"] == pytest.approx(3.0)
    assert list(back[0].cyl["id"]) == [1, 2, 3, 4]  # the exchange table, as stored
