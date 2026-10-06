"""QSM graph -> growth JSON conversion (XRFF-535)."""

from growpy.tools.qsm_graph_to_growth import to_growth_json


def _graph():
    # z-up file frame: a 3-node stem along z, a side branch off node "1", and a thin twig off the tip.
    nodes = {
        "0": (0.0, 0.0, 0.0, 0.20),
        "1": (0.0, 0.0, 1.0, 0.18),
        "2": (0.0, 0.0, 2.0, 0.15),
        "3": (0.0, 0.0, 3.0, 0.12),
        "b1": (1.0, 0.0, 1.0, 0.05),
        "b2": (2.0, 0.0, 1.0, 0.04),
        "t1": (0.0, 0.5, 3.0, 0.01),
    }
    edges = [("0", "1"), ("1", "2"), ("2", "3"), ("1", "b1"), ("b1", "b2"), ("3", "t1")]
    return nodes, edges


def test_trunk_is_first_primitive_and_follows_the_bigger_subtree():
    data = to_growth_json(*_graph())
    prims = data["primitives"]["points"]
    positions = data["points"]["positions"]
    assert [positions[i][1] for i in prims[0]][:4] == [
        0.0,
        1.0,
        2.0,
        3.0,
    ]  # z became y (up)
    attrs = data["primitives"]["attributes"]
    assert attrs["branchParentNumber"]["values"][0] == -1
    assert attrs["branchHierarchyNumber"]["values"][0] == 1


def test_side_branch_shares_its_parent_point_and_is_one_order_higher():
    data = to_growth_json(*_graph())
    prims = data["primitives"]["points"]
    attrs = data["primitives"]["attributes"]
    side = next(
        i
        for i, p in enumerate(prims)
        if i and data["points"]["positions"][p[-1]][0] == 2.0
    )
    assert prims[side][0] == prims[0][1]  # starts at the stem point it grows from
    assert attrs["branchParentNumber"]["values"][side] == 0
    assert attrs["branchHierarchyNumber"]["values"][side] == 2
