"""growpy.structure.mtg_io and branching_model on the hand-built tree of
test_qsm_prototypes (10 m trunk, 2 m branches at 4, 6 and 8 m). The OpenAlea parts skip
where openalea.mtg / openalea.lpy are missing (they live in the growpy-openalea env)."""

import math

import numpy as np
import pytest

from growpy.structure import branching_model as bm
from growpy.structure.descriptors import prune
from growpy.structure.prototypes import PRUNE
from growpy.tests.test_qsm_prototypes import _tree


def test_tree_events_use_the_descriptor_labels():
    ev = bm.tree_events(prune(_tree(twig=True), **PRUNE))
    trunk = next(s for s in ev["seqs"] if s["order"] == 0)
    # 4 m: 2 m against 6 m beyond -> long; 6 m: 2 / 4 -> long; 8 m: carries as much as
    # the leader above it -> fork (descriptors' _event)
    assert trunk["events"] == [0, 0, 0, 0, 2, 0, 2, 0, 3, 0]
    assert trunk["comps"][8] == ((3, 0.0),)  # (event, position within the decile)
    # the 4 m branch carries the twig at mid-length: its own sequence has a lateral there
    limb = [s for s in ev["seqs"] if s["order"] == 1 and any(s["events"])]
    assert len(limb) == 1 and limb[0]["events"][5] > 0
    twig = [r for r in ev["laterals"] if r["order"] == 2]
    assert len(twig) == 1 and twig[0]["len_rel"] == pytest.approx(0.25)
    assert abs(twig[0]["dphi"]) == pytest.approx(90.0, abs=1.0)
    assert ev["trunk_elev"] == pytest.approx(np.full(20, 90.0))
    assert ev["trunk_azim"] == pytest.approx(np.zeros(20))
    first = sorted(
        (r for r in ev["laterals"] if r["order"] == 1), key=lambda r: r["zone"]
    )
    assert [r["zone"] for r in first] == [2, 3, 4]
    assert first[0]["elev"] == pytest.approx(np.zeros(20), abs=1e-6)  # horizontal
    assert first[0]["azim"] == pytest.approx(np.zeros(20), abs=1e-6)  # straight


def test_fit_chain_is_a_smoothed_probability_table():
    trees = [bm.tree_events(prune(_tree(d), **PRUNE)) for d in (0, 30, 60)]
    m = bm.fit(trees, trees, "test", "h10m")
    assert m.chain.shape == (bm.MAX_ORDER, bm.DECILES, 4, 4)
    assert m.chain.sum(axis=-1) == pytest.approx(np.ones((bm.MAX_ORDER, bm.DECILES, 4)))
    # decile 5 (index 4) of the trunk always follows 'none' with a long lateral
    assert m.chain[0, 4, 0].argmax() == 2
    # unseen transitions keep a small, non-zero probability (the prior)
    assert 0 < m.chain[0, 4, 0, 3] < 0.1
    m.seed(1)
    assert m.composition(0, 8, 3) == ((3, 0.0),)
    assert m.lateral(1, 4, 3)["len_rel"] == pytest.approx(0.2)


def test_head_up_makes_pitch_change_elevation_only():
    vals = bm.head_up(30.0, 90.0)
    h, u = np.array(vals[:3]), np.array(vals[3:])
    assert h == pytest.approx([0.0, math.cos(math.radians(30)), 0.5])
    assert float(h @ u) == pytest.approx(0.0, abs=1e-12)
    a = math.radians(10)
    h2 = h * math.cos(a) + u * math.sin(a)  # L-Py's ^(10)
    assert math.degrees(math.asin(h2[2])) == pytest.approx(40.0)
    assert math.degrees(math.atan2(h2[1], h2[0])) == pytest.approx(90.0)


def test_mtg_round_trip(tmp_path):
    pytest.importorskip("openalea.mtg")
    from growpy.structure import mtg_io

    cyl = _tree(twig=True)
    meta = {"tree_uid": "t:hand", "species_key": "test", "height_m": 10.0}
    path = mtg_io.write(mtg_io.to_mtg(cyl, meta), tmp_path / "t.mtg")
    g = mtg_io.read(path)
    a, b = mtg_io.coarsen(prune(cyl, **PRUNE)), mtg_io.from_mtg(g)
    for c in (
        "start_x",
        "start_y",
        "start_z",
        "end_x",
        "end_y",
        "end_z",
        "length",
        "radius",
    ):
        assert b[c].to_numpy() == pytest.approx(a[c].to_numpy())
    for c in ("parent", "axis_id", "axis_order", "axis_pos"):
        assert (b[c].to_numpy() == a[c].to_numpy()).all()
    assert mtg_io.tree_meta(g)["tree_uid"] == "t:hand"
    # three first-order branches and one twig branch off with '+'
    assert sum(1 for v in g.vertices(scale=2) if g.edge_type(v) == "+") == 4


def test_lpy_generation_and_turtle_agree():
    pytest.importorskip("openalea.lpy")
    import openalea.plantgl.all as pgl

    trees = [bm.tree_events(prune(_tree(d, twig=True), **PRUNE)) for d in (0, 30, 60)]
    m = bm.fit(trees, trees, "test", "h10m")
    ls, s = bm.generate(m, height_m=10.0, seed=3)
    c = bm.lstring_cylinders(s)
    # the trunk is grown in pieces between lateral positions: at least two per decile
    assert (c["order"] == 0).sum() >= bm.DECILES * bm.SUBSTEPS
    assert (c["order"] >= 1).any()
    # our turtle and L-Py's interpretation put the tree in the same place
    bb = pgl.BoundingBox(ls.sceneInterpretation(s))
    assert c[["start_z", "end_z"]].to_numpy().max() == pytest.approx(
        bb.getZMax(), abs=0.2
    )
    assert c[["start_x", "end_x"]].to_numpy().min() == pytest.approx(
        bb.getXMin(), abs=0.2
    )


def test_coarsen_keeps_axes_and_branch_points():
    from growpy.structure import mtg_io
    from growpy.structure.descriptors import _model

    work = prune(_tree(twig=True), **PRUNE)
    seg = mtg_io.coarsen(work, segment_m=2.5)
    tree = _model(seg)
    # the 10 m trunk becomes four 2.5 m segments; each 2 m branch stays one segment
    assert len(tree.axes[0]) == 4
    assert seg.groupby("axis_id")["length"].sum().sort_values().tolist()[
        -1
    ] == pytest.approx(10.0)
    # the same laterals, each still starting where it did and hanging on the trunk
    assert sorted(seg.loc[seg["axis_order"] == 1, "start_z"]) == pytest.approx(
        [4.0, 6.0, 8.0]
    )
    on_trunk = seg.loc[(seg["axis_order"] == 1) & (seg["axis_pos"] == 0), "parent"]
    assert set(on_trunk) <= set(tree.axes[0])
    assert (seg["axis_order"] == 2).sum() == 1


def test_coarsen_chains_are_intact_on_a_shuffled_axis_order():
    from growpy.structure import mtg_io

    work = prune(_tree(twig=True), **PRUNE)
    seg = mtg_io.coarsen(work, segment_m=1.5)
    for _, ax in seg.groupby("axis_id"):
        ax = ax.sort_values("axis_pos")
        # every segment after the first follows the one before it on the same axis
        assert (ax["parent"].to_numpy()[1:] == ax.index.to_numpy()[:-1]).all()
    # laterals hang on a segment of another axis, the trunk on nothing
    firsts = seg[seg["axis_pos"] == 0]
    for i, r in firsts.iterrows():
        if r["axis_order"] == 0:
            assert r["parent"] == -1
        else:
            assert seg.at[int(r["parent"]), "axis_id"] != r["axis_id"]


def test_headings_follow_a_turning_branch():
    # 1 m east, then a quarter circle turning north, rising 45 degrees at the end
    t = np.linspace(0, np.pi / 2, 50)
    arc = np.column_stack([1 + np.sin(t), 1 - np.cos(t), np.zeros_like(t)])
    pts = np.vstack([[0, 0, 0], arc, arc[-1] + [0, 0.5, 0.5]])
    elev, azim = bm.headings(pts)
    assert elev[0] == pytest.approx(0.0, abs=1e-6)
    assert elev[-1] == pytest.approx(45.0, abs=1.0)
    assert azim[0] == pytest.approx(0.0) and azim[-1] == pytest.approx(90.0, abs=1.0)
    assert np.all(np.diff(azim) >= -1e-6)  # turns one way only
