"""growpy.structure.descriptors on a tree whose answers can be worked out by hand.

A vertical 10 m trunk of ten 1 m cylinders, and three horizontal 1 m laterals (two 0.5 m
cylinders each) leaving the trunk at heights 4, 6 and 8 m, pointing +x, +y and -x.
"""

import math

import numpy as np
import pandas as pd
import pytest

from growpy.structure.descriptors import DEFINITIONS, _pipe_exponent, describe
from growpy.structure.standardize import RawQsm, standardize


def _tree(lateral_radius=0.05):
    rows = []
    for i in range(10):
        rows.append((i - 1, (0, 0, i), (0, 0, 1), 1.0, 0.2 - 0.01 * i))
    for attach, (dx, dy) in zip((3, 5, 7), ((1, 0), (0, 1), (-1, 0)), strict=True):
        z = attach + 1.0  # the end of trunk cylinder `attach`
        first = len(rows)
        rows.append((attach, (0, 0, z), (dx, dy, 0), 0.5, lateral_radius))
        rows.append((first, (0.5 * dx, 0.5 * dy, z), (dx, dy, 0), 0.5, lateral_radius))
    df = pd.DataFrame(
        {
            "parent": [r[0] for r in rows],
            "start_x": [float(r[1][0]) for r in rows],
            "start_y": [float(r[1][1]) for r in rows],
            "start_z": [float(r[1][2]) for r in rows],
            "axis_x": [float(r[2][0]) for r in rows],
            "axis_y": [float(r[2][1]) for r in rows],
            "axis_z": [float(r[2][2]) for r in rows],
            "length": [r[3] for r in rows],
            "radius": [r[4] for r in rows],
        }
    )
    return standardize(RawQsm(df, {}), {"tree_uid": "t:hand"}).cyl


def test_every_descriptor_is_declared():
    values = describe(_tree())
    assert set(DEFINITIONS) <= set(values)
    for key, (unit, frame, robust, _) in DEFINITIONS.items():
        assert unit and frame and robust in {"yes", "weak", "no"}, key


def test_tree_crown_and_branch_geometry():
    d = describe(_tree())
    assert d["L1.height_m"] == pytest.approx(10.0)
    assert d["L1.crown_base_m"] == pytest.approx(4.0)
    assert d["L1.crown_base_p10_m"] == pytest.approx(4.4)  # 10th percentile of 4, 6, 8
    assert d["L1.crown_ratio"] == pytest.approx(0.56)
    # crown 4.4..10 m: the 8 m branch is in the middle third, 4 and 6 m in the bottom one
    assert math.isnan(d["L4.chord_angle_deg_top"])
    for third in ("middle", "bottom"):
        assert d[f"L4.chord_angle_deg_{third}"] == pytest.approx(90.0)
        assert d[f"L4.straightness_{third}"] == pytest.approx(1.0)
    # measured from the branch's own first cylinder, not the trunk vertex it leaves from:
    # 0.05 against trunk cylinders of 0.17 (at 4 m) and 0.15 (at 6 m)
    assert d["L4.radius_ratio_bottom"] == pytest.approx(
        np.median([0.05 / 0.17, 0.05 / 0.15])
    )
    assert d["L3.branches_per_node_p50"] == 1


def test_trunk_form():
    d = describe(_tree())
    assert d["L1.trunk_lean_deg"] == pytest.approx(0.0)
    assert d["L1.trunk_sinuosity"] == pytest.approx(1.0)
    assert d["L1.trunk_bow_rel"] == pytest.approx(0.0)
    # bend the top half of the trunk 45 degrees: it leans and bows
    cyl = _tree().copy()
    top = cyl["id"].between(6, 10)
    s = np.sqrt(0.5)
    cyl.loc[top, ["axis_x", "axis_z"]] = [s, s]
    for i in range(5, 10):  # rows 5..9 are trunk cylinders 6..10, rebuilt end to end
        prev_end = cyl.loc[i - 1, ["end_x", "end_y", "end_z"]].to_numpy()
        cyl.loc[i, ["start_x", "start_y", "start_z"]] = prev_end
        cyl.loc[i, ["end_x", "end_y", "end_z"]] = prev_end + np.array([s, 0.0, s])
    bent = describe(cyl)
    assert bent["L1.trunk_lean_deg"] > 10
    assert bent["L1.trunk_sinuosity"] > 1.02
    assert bent["L1.trunk_bow_rel"] > 0.05


def test_growth_rule_fingerprint_is_relative():
    d = describe(_tree())
    assert d["G.k0.lateral_density_per_m"] == pytest.approx(3 / 10)
    assert d["G.k0.insertion_deg_mid"] == pytest.approx(90.0)  # laterals at 0.4 and 0.6
    assert d["G.k0.insertion_deg_tip"] == pytest.approx(90.0)  # lateral at 0.8
    # lateral length / trunk length left above the attachment: 1/6 and 1/4 in the middle
    assert d["G.k0.length_ratio_mid"] == pytest.approx(np.median([1 / 6, 1 / 4]))
    assert d["G.k0.length_ratio_tip"] == pytest.approx(1 / 2)
    # the 8 m lateral (1 m) is half the trunk above it (2 m): a fork by the 0.5 rule
    assert d["G.k0.fork_share"] == pytest.approx(1 / 3)


def test_topology_is_scale_free():
    d = describe(_tree())
    assert d["T.strahler_max"] == 2
    assert d["T.bifurcation_ratio"] == pytest.approx(
        4.0
    )  # 4 first-order streams, 1 second
    assert d["T.path_fraction"] == pytest.approx((10 + 5 + 7 + 9) / 4 / 10)
    assert d["T.partition_asymmetry"] == pytest.approx((0 + 1 + 1) / 3)
    assert d["T.n_axes_order_1"] == 3


def test_branching_sequence_along_the_trunk():
    # laterals at 0.4 (1 m of 6 m left: short), 0.6 (1 of 4: long), 0.8 (fork, see above)
    d = describe(_tree())
    assert d["S.k0.bare_base_rel"] == pytest.approx(0.4)
    assert d["S.k0.bare_tip_rel"] == pytest.approx(0.2)
    assert d["S.k0.share_none"] == pytest.approx(0.7)
    for s in ("short", "long", "fork"):
        assert d[f"S.k0.share_{s}"] == pytest.approx(0.1)
    # deciles 0 0 0 0 S 0 L 0 F 0: from "none" 3 of 6 moves stay, nothing else repeats
    assert d["S.k0.persist_none"] == pytest.approx(0.5)
    assert d["S.k0.persist_short"] == 0.0


def test_common_resolution_prunes_thin_branches():
    d = describe(_tree(), min_radius_m=0.06)
    assert d["T.n_axes_order_1"] == 0
    assert math.isnan(d["G.k0.insertion_deg_mid"])
    assert d["L1.height_m"] == pytest.approx(10.0)


def test_common_resolution_by_branch_length_and_order():
    # the laterals are 1 m long: a 1.5 m floor drops all three, 0.5 m keeps them
    assert describe(_tree(), min_length_m=1.5)["T.n_axes_order_1"] == 0
    assert describe(_tree(), min_length_m=0.5)["T.n_axes_order_1"] == 3
    assert describe(_tree(), max_order=0)["T.n_axes_order_1"] == 0


def test_rank_matched_branches_and_crown_outline():
    d = describe(_tree())
    # one branch in the middle third (8 m), two in the bottom (4 and 6 m); all 1 m long
    assert d["L4.top5_length_rel_middle"] == pytest.approx(0.1)
    assert d["L4.top5_chord_angle_deg_bottom"] == pytest.approx(90.0)
    assert math.isnan(d["L4.top5_length_rel_top"])
    outline = [d[f"L1.crown_width_rel_d{k:02d}"] for k in range(1, 11)]
    assert max(outline) == pytest.approx(d["L1.crown_width_over_height"])


def _custom(laterals):
    """A vertical 10 m trunk (ten 1 m cylinders) plus laterals, each a list of
    (direction, length) cylinders starting at the end of trunk cylinder ``attach``."""
    rows = [(i - 1, (0, 0, i), (0, 0, 1), 1.0, 0.2 - 0.01 * i) for i in range(10)]
    for attach, segments in laterals:
        pos = np.array([0.0, 0.0, attach + 1.0])
        parent = attach
        for direction, length in segments:
            d = np.asarray(direction, dtype=float)
            d /= np.linalg.norm(d)
            rows.append((parent, tuple(pos), tuple(d), length, 0.05))
            parent = len(rows) - 1
            pos = pos + d * length
    df = pd.DataFrame(
        {
            "parent": [r[0] for r in rows],
            **{
                f"start_{c}": [float(r[1][i]) for r in rows]
                for i, c in enumerate("xyz")
            },
            **{
                f"axis_{c}": [float(r[2][i]) for r in rows] for i, c in enumerate("xyz")
            },
            "length": [r[3] for r in rows],
            "radius": [r[4] for r in rows],
        }
    )
    return standardize(RawQsm(df, {}), {"tree_uid": "t:custom"}).cyl


def test_form_of_straight_horizontal_branches():
    d = describe(_tree())
    assert d["F.lower_hang_len_frac"] == pytest.approx(
        0.0
    )  # only the 4 m branch is "lower"
    assert d["F.lower_tips_hanging"] == pytest.approx(0.0)
    assert d["F.wave_sag_rel_p50"] == pytest.approx(0.0)
    assert d["F.wave_rise_rel_p50"] == pytest.approx(0.0)
    assert d["F.wave_tip_turn_deg_p50"] == pytest.approx(0.0, abs=1e-6)
    # tips at (1, 0), (0, 1), (-1, 0) around a vertical trunk: mean (0, 1/3), reach 1
    assert d["F.crown_offset_rel"] == pytest.approx(1 / 3)
    assert math.isnan(d["F.length_cv_p50"])  # no crown tenth holds three branches
    assert math.isnan(d["F.whorl_gap_cv_p50"])  # one branch per node
    assert math.isnan(d["F.whorl_gap_max_deg_p50"])
    assert d["F.branches_per_node_cv"] == pytest.approx(0.0)  # 1, 1, 1
    # the topmost branch leaves the 10 m trunk at 8 m: 2 m of leader
    assert d["F.leader_m"] == pytest.approx(2.0)
    assert d["F.leader_rel"] == pytest.approx(0.2)
    # crown span 4..8 m: three branches fill three of the 10 x 8 cells
    assert d["F.crown_holes_share"] == pytest.approx(77 / 80)


def test_crown_per_dbh_uses_the_dbh_it_is_given():
    d = describe(_tree(), dbh_m=0.5)
    width = d["L1.crown_width_over_height"] * d["L1.height_m"]
    assert d["F.crown_m_per_dbh_cm"] == pytest.approx(width / 50)
    # without one the trunk is read at 1.3 +- 0.2 m: cylinder 1 (z 1-2 m), radius 0.19
    assert describe(_tree())["F.crown_m_per_dbh_cm"] == pytest.approx(width / 38)


def test_a_branch_that_sags_and_curls_up():
    # out and down 45 deg, flat, up 45 deg: 0.5 m each, a symmetric U under its chord
    s = 0.5 / math.sqrt(2)
    d = describe(
        _custom([(3, [((1, 0, -1), 0.5), ((1, 0, 0), 0.5), ((1, 0, 1), 0.5)])])
    )
    assert d["F.wave_sag_rel_p50"] == pytest.approx(s / 1.5)
    assert d["F.wave_rise_rel_p50"] == pytest.approx(0.0, abs=1e-9)
    assert d["F.wave_tip_turn_deg_p50"] == pytest.approx(90.0)
    # the first 0.5 m points 45 deg below horizontal: a third of the length hangs,
    # the tip does not
    assert d["F.lower_hang_len_frac"] == pytest.approx(1 / 3)
    assert d["F.lower_tips_hanging"] == pytest.approx(0.0)


def test_irregular_whorl_and_branch_lengths():
    # one node at 6 m with three branches of 1-2 m at 0, 90 and 180 deg:
    # azimuth gaps 90, 90, 180
    d = describe(
        _custom(
            [(5, [((1, 0, 0), 1.0)]), (5, [((0, 1, 0), 1.5)]), (5, [((-1, 0, 0), 2.0)])]
        )
    )
    gaps = np.array([90.0, 90.0, 180.0])
    assert d["F.whorl_gap_cv_p50"] == pytest.approx(gaps.std() / gaps.mean())
    lengths = np.array([1.0, 1.5, 2.0])
    assert d["F.length_cv_p50"] == pytest.approx(lengths.std() / lengths.mean())
    assert d["F.whorl_gap_max_deg_p50"] == pytest.approx(180.0)  # the missing branch


def test_whorl_count_irregularity():
    # a single branch at 4 m, a whorl of three at 6 m: counts 1 and 3
    one = [(3, [((1, 0, 0), 1.0)])]
    three = [(5, [((1, 0, 0), 1.0)]), (5, [((0, 1, 0), 1.0)]), (5, [((-1, 0, 0), 1.0)])]
    d = describe(_custom(one + three))
    assert d["F.branches_per_node_cv"] == pytest.approx(0.5)  # std 1 / mean 2


def test_pipe_exponent_of_an_area_preserving_fork_is_two():
    assert _pipe_exponent(np.array([0.8, 0.6])) == pytest.approx(2.0, abs=1e-6)
    assert math.isnan(
        _pipe_exponent(np.array([1.2, 0.5]))
    )  # a child thicker than its parent
