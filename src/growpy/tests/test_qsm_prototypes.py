"""growpy.structure.prototypes on trees whose answers can be worked out by hand.

A vertical 10 m trunk of ten 1 m cylinders and three 2 m first-order branches leaving the
trunk at 4, 6 and 8 m. ``droop`` bends each branch's second metre down by that angle.
"""

import math

import numpy as np
import pandas as pd
import pytest

from growpy.structure import prototype_icons as icons
from growpy.structure import prototypes as pt
from growpy.structure.standardize import RawQsm, standardize


def _tree(droop_deg: float = 0.0, twig: bool = False):
    """``twig`` adds a 0.5 m horizontal second-order branch leaving the 4 m branch (+x)
    at its midpoint (x = 1 m) at a right angle (+y)."""
    rows = []
    for i in range(10):
        rows.append((i - 1, (0, 0, i), (0, 0, 1), 1.0, 0.2))
    c, s = math.cos(math.radians(droop_deg)), math.sin(math.radians(droop_deg))
    for attach, (dx, dy) in zip((3, 5, 7), ((1, 0), (0, 1), (-1, 0)), strict=True):
        z = attach + 1.0
        first = len(rows)
        rows.append((attach, (0, 0, z), (dx, dy, 0), 1.0, 0.05))
        rows.append((first, (dx, dy, z), (dx * c, dy * c, -s), 1.0, 0.05))
        if twig and attach == 3:
            rows.append((first, (1, 0, z), (0, 1, 0), 0.5, 0.02))
    df = pd.DataFrame(
        {
            "parent": [r[0] for r in rows],
            **{
                f"start_{k}": [float(r[1][i]) for r in rows]
                for i, k in enumerate("xyz")
            },
            **{
                f"axis_{k}": [float(r[2][i]) for r in rows] for i, k in enumerate("xyz")
            },
            "length": [r[3] for r in rows],
            "radius": [r[4] for r in rows],
        }
    )
    return standardize(RawQsm(df, {}), {"tree_uid": "t:hand"}).cyl


def test_height_label_snaps_like_the_dataset_overview():
    assert pt.height_label(17.6) == "h20m"
    assert pt.height_label(22.4) == "h20m"
    assert pt.height_label(22.6) == "h25m"
    assert pt.height_label(4.9) == "h05m"
    assert pt.species_title("norway_spruce") == "Norway_Spruce"


def test_profile_of_horizontal_branches():
    p = pt.tree_profile(_tree())
    assert p["height_m"] == pytest.approx(10.0)
    assert p["crown_base_m"] == pytest.approx(4.4)  # p10 of 4, 6, 8
    assert len(p["curves"]) == 3
    # straight horizontal branches: h runs 0..1 along the arc, v stays 0
    assert p["curves"][:, -1, 0] == pytest.approx(1.0, abs=1e-6)
    assert np.abs(p["curves"][:, :, 1]).max() == pytest.approx(0.0, abs=1e-6)
    # crown 4.4..10 m in tenths of 0.56 m: 4 m clips to decile 0, 6 m -> 2, 8 m -> 6
    assert sorted(p["decile"].tolist()) == [0, 2, 6]
    assert p["length_rel"] == pytest.approx([0.2, 0.2, 0.2])
    assert p["occupancy"].sum() == pytest.approx(1.0, abs=1e-5)


def test_unrolled_droop():
    p = pt.tree_profile(_tree(droop_deg=90))
    # second metre hangs straight down: tip at h = 0.5, v = -0.5 branch lengths
    assert p["curves"][:, -1, 0] == pytest.approx(0.5, abs=1e-6)
    assert p["curves"][:, -1, 1] == pytest.approx(-0.5, abs=1e-6)


def test_pipe_radii_conserve_area_and_hit_dbh():
    geo = pt.geometry(_tree(), max_order=None)
    r = pt.pipe_radii(geo.start, geo.end, geo.parent, geo.trunk_rows, dbh_m=0.3)
    # distal length worked out by hand: 9 m of trunk + 3 x 2 m of branch above z = 1.3 m
    # (15 - 0.3 = 14.7 m at breast height); the 1-2 m cylinder's midpoint carries 14.5 m
    assert r[geo.trunk_rows[1]] == pytest.approx(0.15 * math.sqrt(14.5 / 14.7))
    assert np.all(np.diff(r[geo.trunk_rows]) < 0)  # thinner going up
    # area is the distal length at the midpoint: at the 4 m fork the trunk above carries
    # 6 m + 2 x 2 m of branch and the branch 2 m, against 12 m below the fork
    trunk_above = geo.trunk_rows[4]
    branch = int(
        np.flatnonzero(
            (geo.parent == geo.trunk_rows[3]) & (np.arange(len(r)) != trunk_above)
        )[0]
    )
    scale = 0.15**2 / 14.7
    assert r[trunk_above] ** 2 == pytest.approx(scale * (10.0 - 0.5))
    assert r[branch] ** 2 == pytest.approx(scale * (2.0 - 0.5))


def test_group_curves_and_score_identity():
    profs = [pt.tree_profile(_tree(d)) for d in (0, 30, 60)]
    curves = pt.group_curves(profs)
    assert set(curves["decile"]) == {1, 3, 7}
    d1 = curves[curves["decile"] == 1].sort_values("point")
    # median of 0, 30 and 60 degree droops is the 30 degree tree
    assert d1["v_p50"].iloc[-1] == pytest.approx(profs[1]["curves"][0, -1, 1], abs=1e-6)
    assert int(d1["n_trees"].iloc[0]) == 3
    score = pt.score_curves(profs[1], curves)
    assert score["dv_abs"].max() == pytest.approx(0.0, abs=1e-6)
    assert score["in_band"].min() == pytest.approx(1.0)
    hang = pt.score_curves(profs[2], curves)
    assert (hang["dv_signed"] < 0).all()  # the 60 degree tree hangs below the median


def test_template_tree_shape():
    profs = [pt.tree_profile(_tree(d)) for d in (0, 30, 60)]
    curves = pt.group_curves(profs)
    tmpl = pt.template_tree(curves, height_m=20.0, crown_base_rel=0.44)
    assert tmpl.height == pytest.approx(20.0, abs=1e-6)
    trunk = tmpl.end[tmpl.trunk_rows]
    assert np.abs(trunk[:, :2]).max() == pytest.approx(0.0)
    n_branch_cyl = len(tmpl.start) - len(tmpl.trunk_rows)
    assert n_branch_cyl % (pt.N_POINTS - 1) == 0 and n_branch_cyl > 0


def _desc(n, species="norway_spruce", tier="C", height=20.0):
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "tree_uid": [f"{species}:{tier}:{height}:{i}" for i in range(n)],
            "source": "kew",
            "source_kind": "scan",
            "tier": tier,
            "species_key": species,
            "valid_qsm": True,
            "height_m": height + rng.uniform(-2, 2, n),
            "L1.crown_width_over_height": np.linspace(0.2, 0.6, n),
        }
    )


def test_select_groups_tertiles_tiers_and_qc():
    table = pd.concat(
        [
            _desc(15),  # 15 tier C at h20: w0 + three tertiles of 5
            _desc(7, height=10.0),  # 7 at h10: w0 only
            _desc(3, height=30.0),  # 3 at h30: dropped
            _desc(6, species="european_beech", tier="A"),
            _desc(30, species="european_beech", tier="C"),  # A/B suffice: C not used
        ],
        ignore_index=True,
    )
    bad = _desc(1, height=127.5)
    table = pd.concat([table, bad], ignore_index=True)
    g = pt.select_groups(table)
    sp = g[g["species_key"] == "norway_spruce"]
    assert sorted(
        sp[sp["height_class"] == "h20m"]["width_class"].value_counts().items()
    ) == [("w0", 15), ("w1", 5), ("w2", 5), ("w3", 5)]
    assert set(sp[sp["height_class"] == "h10m"]["width_class"]) == {"w0"}
    assert "h30m" not in set(sp["height_class"])
    assert "h130m" not in set(g["height_class"])
    beech = g[g["species_key"] == "european_beech"]
    assert set(beech["tiers"]) == {"A/B"} and len(beech) == 6
    # narrow tertile holds the narrowest crowns
    h20 = sp[sp["height_class"] == "h20m"].merge(table, on="tree_uid")
    assert (
        h20[h20["width_class"] == "w1"]["L1.crown_width_over_height"].max()
        < h20[h20["width_class"] == "w3"]["L1.crown_width_over_height"].min()
    )


def test_rank_medoids_picks_the_central_tree():
    rows = pd.DataFrame(
        {
            "L1.crown_width_over_height": [0.1, 0.4, 0.41, 0.42, 0.9],
            "L1.crown_ratio": [0.5] * 5,
        },
        index=list("abcde"),
    )
    assert pt.rank_medoids(rows).idxmin() == "c"


def test_icons_match_the_catalog_canvas(tmp_path):
    from PIL import Image

    geo = pt.geometry(_tree(), max_order=None)
    r = pt.pipe_radii(geo.start, geo.end, geo.parent, geo.trunk_rows, 0.3)
    path = icons.tree_icon(tmp_path / "t.png", geo, r)
    with Image.open(path) as im:
        assert im.size == (512, 512)
        px = np.asarray(im.convert("RGB"))
    assert tuple(px[0, 0]) == (255, 255, 255)  # white background, no frame
    assert (px.reshape(-1, 3) == (0x3B, 0x2A, 0x1A)).all(axis=1).any()  # catalog brown
    occ = pt.tree_profile(_tree())["occupancy"]
    path = icons.occupancy_icon(tmp_path / "o.png", occ, 10.0)
    with Image.open(path) as im:
        assert im.size == (512, 512)


def test_curves_use_leading_branches_only():
    p = pt.tree_profile(_tree())
    # all three real branches in decile 0, plus four short fragments that must not count
    frag = dict(p)
    frag["decile"] = np.zeros(7, int)
    frag["length_rel"] = np.concatenate([p["length_rel"], np.full(4, 0.05)])
    frag["curves"] = np.concatenate([p["curves"], np.repeat(p["curves"][:1] * 0, 4, 0)])
    d1 = pt.group_curves([frag])
    d1 = d1[d1["decile"] == 1]
    assert d1["length_rel_p50"].iloc[0] == pytest.approx(0.2)
    assert int(d1["n_branches"].iloc[0]) == pt.LEADING_PER_DECILE


def test_clean_stems_reject_a_broken_stem():
    whole = pt.tree_profile(_tree())
    assert whole["trunk_gap_rel"] == pytest.approx(0.0)
    assert whole["trunk_sinuosity"] == pytest.approx(1.0)
    broken = dict(whole, trunk_gap_rel=0.6, trunk_sinuosity=1.3)
    short = dict(whole, trunk_top_rel=0.5)
    profiles = {"a": whole, "b": dict(whole), "c": broken, "d": short}
    assert pt.clean_stems(profiles) == {"a", "b"}


def test_group_occupancy_is_a_share_of_trees():
    a = pt.tree_profile(_tree())
    b = pt.tree_profile(_tree(droop_deg=90))
    occ = pt.group_occupancy([a, b])
    assert occ.max() == pytest.approx(1.0)  # the trunk column: both trees
    assert set(np.unique(occ)) <= {0.0, 0.5, 1.0}


def test_leading_branch_is_chosen_by_straight_line_reach():
    p = pt.tree_profile(_tree())
    p["decile"] = np.zeros(3, int)
    p["length_rel"] = np.array([0.5, 0.2, 0.1])
    p["curves"] = p["curves"].copy()
    # branch 0 is the longest but a zigzag whose tip ends where it starts: not chosen
    p["curves"][0, :, :] = 0.0
    assert pt.leading(p, 0).tolist() == [1]
    # an upright limb (tip 0.95 lengths up, 0.1 out) beats a shorter flat one, although
    # it reaches less far horizontally
    p["length_rel"] = np.array([0.1, 0.2, 0.3])
    p["curves"][2] = np.linspace(0, 1, pt.N_POINTS)[:, None] * [0.1, 0.95]
    assert pt.leading(p, 0).tolist() == [2]
    horizontal = p["curves"][:, :, 0].max(axis=1) * p["length_rel"]
    assert (
        int(np.argmax(horizontal)) == 1
    )  # the old horizontal rule picked the flat one


def test_trunk_top_flags_a_broken_stem():
    assert pt.tree_profile(_tree())["trunk_top_rel"] == pytest.approx(1.0)


def test_second_order_profile():
    p = pt.tree_profile(_tree(twig=True))
    assert len(p["curves"]) == 3  # the twig is not a first-order branch
    assert p["o2_third"].tolist() == [1]  # leaves at mid-length of its 2 m parent
    assert p["o2_len_ratio"] == pytest.approx([0.25])
    assert p["o2_div_deg"] == pytest.approx([90.0])
    # one twig in the middle third of 6 m of first-order length (2 m per third)
    assert p["o2_per_m"] == pytest.approx([0.0, 0.5, 0.0])
    assert pt.tree_profile(_tree())["o2_curves"].shape == (0, pt.N_POINTS, 2)


def test_template_carries_second_order_fans():
    profs = [pt.tree_profile(_tree(d, twig=True)) for d in (0, 30, 60)]
    curves = pt.group_curves(profs)
    second = pt.group_second_order(profs)
    assert set(second["third"]) == {2}
    assert second["div_deg_p50"].iloc[0] == pytest.approx(90.0)
    bare = pt.template_tree(curves, 20.0, 0.44)
    fans = pt.template_tree(curves, 20.0, 0.44, second)
    assert len(fans.start) > len(bare.start)

    # fans hang off limbs, never the trunk: as many trunk-attached cylinders as before
    def on_trunk(g):
        rows = np.setdiff1d(np.arange(len(g.start)), g.trunk_rows)
        return int(np.isin(g.parent[rows], g.trunk_rows).sum())

    assert on_trunk(fans) == on_trunk(bare)


def test_forks_follow_the_descriptor_rule():
    p = pt.tree_profile(_tree())
    # the 2 m branch at 8 m carries as much as the 2 m of leader above it (share 1.0);
    # at 6 m the branch carries 2 m against 6 m above it (0.33): no fork
    assert p["fork_z"] == pytest.approx([0.8])
    assert p["fork_share"] == pytest.approx([1.0])
    assert p["fork_len_rel"] == pytest.approx([0.2])
    assert p["stem_offset"] == pytest.approx(np.zeros(10))


def test_group_forks_rate_gate():
    profs = [pt.tree_profile(_tree(d)) for d in (0, 30, 60)]
    forks = pt.group_forks(profs)
    assert forks["rate"] == pytest.approx(1.0) and forks["n"] == 1
    assert forks["z_rel"] == pytest.approx([0.8])
    for p in profs:
        p["fork_z"] = np.zeros(0)
        p["fork_share"] = p["fork_len_rel"] = np.zeros(0)
        p["fork_curves"] = np.zeros((0, pt.N_POINTS, 2))
    assert pt.group_forks(profs) is None  # nobody forks: a single leader


def test_template_splits_and_wanders():
    profs = [pt.tree_profile(_tree(d)) for d in (0, 30, 60)]
    curves = pt.group_curves(profs)
    forks = pt.group_forks(profs)
    forks["stem_offset"] = np.full(10, 0.05)
    plain = pt.template_tree(curves, 20.0, 0.44)
    split = pt.template_tree(curves, 20.0, 0.44, forks=forks)
    # the leader wanders 0.05 x 20 m = 1 m by the top
    assert split.end[split.trunk_rows[-1], 0] == pytest.approx(1.0)
    assert plain.end[plain.trunk_rows[-1], 0] == pytest.approx(0.0)
    # the fork limb leaves the leader at 0.8 H and takes over some branches above it
    limb = np.flatnonzero(
        np.isin(split.parent, split.trunk_rows)
        & np.isclose(split.start[:, 2], 16.0)
        & ~np.isin(np.arange(len(split.parent)), split.trunk_rows)
    )
    assert len(limb) >= 1
    trunk_kids = lambda g: int(  # noqa: E731
        np.isin(g.parent, g.trunk_rows).sum() - (len(g.trunk_rows) - 1)
    )
    assert trunk_kids(split) <= trunk_kids(plain) + 1


def test_branches_grow_to_the_crown_envelope():
    profs = [pt.tree_profile(_tree(d)) for d in (0, 30, 60)]
    curves = pt.group_curves(profs)
    d1 = curves[curves["decile"] == 1].sort_values("point")
    h, v = d1["h_p50"].to_numpy(), d1["v_p50"].to_numpy()
    # an outline 0.1 H wide (half width) from 0.3 H to the top: the tip lands on it
    env = (np.array([0.3, 1.0]), np.array([0.1, 0.1]))
    length = pt._to_envelope(h, v, 10.0, 3.0, 20.0, env)
    assert length * h.max() == pytest.approx(2.0)
    # clipped to 0.5-3 x the median length, unchanged outside the outline's heights
    assert pt._to_envelope(h, v, 10.0, 0.1, 20.0, env) == pytest.approx(0.3)
    assert pt._to_envelope(h, v, 1.0, 3.0, 20.0, env) == pytest.approx(3.0)
