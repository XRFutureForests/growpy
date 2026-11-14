"""PVE Carve (radius basis) model and its wiring (owner, 2026-11-12)."""

from pathlib import Path

import pytest

from growpy.io.unreal.pve_carve_model import (
    carve_for_trim,
    carve_skeleton,
    lateral_length,
)
from growpy.io.unreal.pve_graph_builder import (
    DistributorSpec,
    TreeChainSpec,
    generate_pve_graph_builder_script,
)
from growpy.tests.test_pve_calibration import _species
from growpy.tests.test_pve_graph_builder import _graph


def _tree():
    """A trunk of 5 points (radius 10 -> 2 cm) and two laterals of 5 points
    (radius 1.0 -> 0.2 cm), the second with a child at its third point."""
    positions, meristem = [], []

    def point(xyz, r_cm, lfr):
        positions.append(list(xyz))
        meristem.append([r_cm / 100.0, 1.0, 0.0, 0.0, 1.0, lfr, 0.0])
        return len(positions) - 1

    trunk = [
        point((0, y, 0), r, y) for y, r in zip(range(5), (10, 8, 6, 4, 2), strict=True)
    ]
    lat1 = [trunk[1]] + [
        point((x, 1, 0), r, 1 + x)
        for x, r in zip(range(1, 5), (0.8, 0.6, 0.4, 0.2), strict=True)
    ]
    lat2 = [trunk[2]] + [
        point((x, 2, 0), r, 2 + x)
        for x, r in zip(range(1, 5), (0.8, 0.6, 0.4, 0.2), strict=True)
    ]
    child = [lat2[3]] + [
        point((3, 2, z), r, 5 + z) for z, r in zip(range(1, 3), (0.3, 0.2), strict=True)
    ]
    return {
        "points": {
            "positions": positions,
            "attributes": {"budLateralMeristem": {"values": meristem}},
        },
        "primitives": {
            "points": [trunk, lat1, lat2, child],
            "attributes": {
                "branchNumber": {"values": [1, 2, 3, 4]},
                "branchParentNumber": {"values": [None, 1, 1, 3]},
            },
        },
    }


def test_zero_carve_keeps_everything_and_never_edits_the_input():
    tree = _tree()
    assert carve_skeleton(tree, 0.0) == tree
    carve_skeleton(tree, 0.05)
    assert tree == _tree()


def test_a_branch_is_cut_where_it_gets_thinner_than_the_line():
    # r_min 0.2, r_max 10: carve 0.03 puts the line at r = 0.2 + 0.03 * 9.8 = 0.494 cm
    out = carve_skeleton(_tree(), 0.03)
    trunk, lat1, lat2, child = out["primitives"]["points"]
    assert len(trunk) == 5  # the trunk never gets that thin
    assert len(lat1) == 4  # 0.8, 0.6 kept, the 0.4 point pulled back to the crossing
    end = out["points"]["positions"][lat1[-1]]
    assert 2.0 < end[0] < 3.0  # between the last kept point (x=2) and x=3
    assert child == []  # rooted at x=3 on lat2, beyond the cut


def test_the_trim_search_hits_the_asked_share_of_lateral_length():
    tree = _tree()
    carve = carve_for_trim(tree, 0.3, tolerance=0.02)
    removed = 1.0 - lateral_length(carve_skeleton(tree, carve)) / lateral_length(tree)
    assert removed == pytest.approx(0.3, abs=0.02)
    assert carve_for_trim(tree, 0.0) == 0.0


def test_the_calibration_refuses_a_trim_of_one_or_more():
    with pytest.raises(ValueError, match="carve_trim"):
        _species(carve_trim=1.0)


def test_a_trimmed_chain_wires_a_carve_node_before_the_mesher(tmp_path):
    chain = TreeChainSpec(
        Path("data/tmp/tree.json"),
        "SK_Test",
        DistributorSpec(branch_density=17),
        carve=0.0035,
    )
    body = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
    body = body.read_text(encoding="utf-8")
    assert "'carve': 0.0035" in body
    assert "unreal.PVCarveSettings" in body and "unreal.CarveBasis.RADIUS" in body
    assert '(skeleton, "Out", mesh_node, "In")' in body
    assert 'c["carve"] > 0.0' in body  # the extra edge is counted
    with pytest.raises(ValueError, match="carve"):
        TreeChainSpec(
            Path("t.json"), "SK_T", DistributorSpec(branch_density=1), carve=1.5
        )


def test_a_sagging_chain_wires_a_gravity_node_after_the_carve(tmp_path):
    chain = TreeChainSpec(
        Path("data/tmp/tree.json"),
        "SK_Test",
        DistributorSpec(branch_density=17),
        carve=0.0035,
        gravity=0.3,
    )
    body = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
    body = body.read_text(encoding="utf-8")
    assert "'gravity': 0.3" in body
    assert "unreal.PVGravitySettings" in body and '"PHOTOTROPIC"' in body
    assert 'c.get("gravity", 0.0) > 0.0' in body  # the extra edge is counted
    assert _species(gravity=0.3).gravity == 0.3
    with pytest.raises(ValueError, match="gravity"):
        _species(gravity=1.5)
    with pytest.raises(ValueError, match="gravity"):
        TreeChainSpec(
            Path("t.json"), "SK_T", DistributorSpec(branch_density=1), gravity=-0.1
        )
