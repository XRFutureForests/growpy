"""Tests for growpy.tools.icon_crown_metrics.

All fixtures are synthetic images rendered here with the same matplotlib
primitives ``io/usd/preview.py::generate_icon_image`` uses (LineCollection
skeleton in "#3b2a1a", scatter twigs in "#1f7a1f" at alpha=0.5), so these
tests do not depend on pipeline output existing on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

from growpy.tools import icon_crown_metrics as icm  # noqa: E402


def _render_icon_pair(
    out_dir: Path,
    prefix: str,
    view: str,
    segments: list[list[tuple[float, float]]],
    dot_layers: list[np.ndarray],
    size_px: int = 256,
    dpi: int = 150,
    linewidth_pts: float = 8.0,
    marker_s: float = 4.0,
) -> tuple[Path, Path]:
    """Render a base + twig icon pair exactly like generate_icon_image does.

    ``dot_layers`` is a list of (N, 2) arrays; each array is drawn with its
    own ``ax.scatter(...)`` call, matching how preview.py would draw twig
    positions -- and, crucially, matching how repeated/overlapping scatter
    calls composite in Agg (each call alpha-blends against what's already
    rendered).
    """
    fig_inches = size_px / dpi
    fig, ax = plt.subplots(1, 1, figsize=(fig_inches, fig_inches))

    lc = LineCollection(
        segments,
        linewidths=[linewidth_pts] * len(segments),
        colors="#3b2a1a",
        alpha=1.0,
        capstyle="round",
        joinstyle="round",
    )
    ax.add_collection(lc)
    ax.set_aspect("equal")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    base_path = out_dir / f"{prefix}_icon_{view}.png"
    fig.savefig(base_path, dpi=dpi, facecolor="white")

    for layer in dot_layers:
        ax.scatter(
            layer[:, 0],
            layer[:, 1],
            s=marker_s,
            c="#1f7a1f",
            alpha=0.5,
            linewidths=0,
            zorder=3,
        )
    twig_path = out_dir / f"{prefix}_icon_{view}_twigs.png"
    fig.savefig(twig_path, dpi=dpi, facecolor="white")

    plt.close(fig)
    return base_path, twig_path


SKELETON_SEGMENTS = [[(5.0, 1.0), (5.0, 9.0)], [(5.0, 6.0), (8.0, 8.0)]]


class TestClassifyMasks:
    def test_no_twigs_no_green(self, tmp_path):
        base, twig = _render_icon_pair(
            tmp_path, "t", "front", SKELETON_SEGMENTS, dot_layers=[]
        )
        analysis = icm.analyze_icon_pair(base, twig, "front")
        assert analysis.metrics.green_px == 0
        assert analysis.metrics.dot_count == 0
        assert analysis.metrics.branch_px > 0

    def test_scattered_dots_detected(self, tmp_path):
        rng = np.random.default_rng(0)
        pts = rng.uniform(1, 9, size=(20, 2))
        base, twig = _render_icon_pair(
            tmp_path, "t", "front", SKELETON_SEGMENTS, dot_layers=[pts]
        )
        analysis = icm.analyze_icon_pair(base, twig, "front")
        assert analysis.metrics.green_px > 0
        assert analysis.metrics.dot_count >= 1


class TestHull:
    def test_union_hull_gte_black_only_hull(self, tmp_path):
        """crown_fill (union hull) must not silently exceed 1.0 the way a
        black-only-hull ratio can (property #1 in the module docstring)."""
        # Dots placed well outside the thin skeleton -> green legitimately
        # extends past the branch-only hull.
        far_dots = np.array(
            [[1.0, 1.0], [1.2, 1.1], [1.1, 1.3], [9.0, 9.0], [8.8, 8.9], [8.9, 9.1]]
        )
        base, twig = _render_icon_pair(
            tmp_path,
            "t",
            "front",
            SKELETON_SEGMENTS,
            dot_layers=[far_dots],
            linewidth_pts=1.0,
        )
        analysis = icm.analyze_icon_pair(base, twig, "front")
        m = analysis.metrics
        assert m.hull_px >= m.black_hull_px
        assert m.crown_fill <= 1.0
        # Against the (smaller) black-only hull, coverage should read
        # higher than against the union hull -- demonstrating the bias
        # the union-hull definition is designed to avoid hiding.
        assert m.crown_fill_vs_black_hull >= m.crown_fill

    def test_crown_fill_scale_free(self, tmp_path):
        """A big and a small render of the same relative layout should
        give similar crown_fill despite very different pixel counts."""
        rng = np.random.default_rng(1)
        pts = rng.uniform(2, 8, size=(15, 2))
        b1, t1 = _render_icon_pair(
            tmp_path, "small", "front", SKELETON_SEGMENTS, [pts], size_px=128
        )
        b2, t2 = _render_icon_pair(
            tmp_path, "big", "front", SKELETON_SEGMENTS, [pts], size_px=512
        )
        m1 = icm.analyze_icon_pair(b1, t1, "front").metrics
        m2 = icm.analyze_icon_pair(b2, t2, "front").metrics
        assert m1.crown_fill == pytest.approx(m2.crown_fill, abs=0.15)


class TestBlobMetrics:
    def test_clustered_vs_scattered_largest_cc(self, tmp_path):
        rng = np.random.default_rng(2)
        clustered = rng.normal(loc=(5.0, 5.0), scale=0.15, size=(40, 2))
        clustered = np.clip(clustered, 0.5, 9.5)
        b1, t1 = _render_icon_pair(
            tmp_path, "clustered", "front", SKELETON_SEGMENTS, [clustered]
        )
        m1 = icm.analyze_icon_pair(b1, t1, "front").metrics

        # Spread across a coarse, well-separated grid.
        xs, ys = np.meshgrid(np.linspace(0.5, 9.5, 8), np.linspace(0.5, 9.5, 5))
        scattered = np.stack([xs.ravel(), ys.ravel()], axis=1)
        b2, t2 = _render_icon_pair(
            tmp_path, "scattered", "front", SKELETON_SEGMENTS, [scattered]
        )
        m2 = icm.analyze_icon_pair(b2, t2, "front").metrics

        assert m1.blob_largest_cc > m2.blob_largest_cc
        assert m2.connected_components > m1.connected_components

    def test_stacked_dots_higher_saturation_than_single_layer(self, tmp_path):
        # Same exact position, drawn once vs. drawn 6 times (stacked
        # alpha-compositing layers) -- same footprint, different depth.
        single_pos = np.array([[5.0, 5.0]])
        b1, t1 = _render_icon_pair(
            tmp_path, "single", "front", SKELETON_SEGMENTS, dot_layers=[single_pos]
        )
        m1 = icm.analyze_icon_pair(b1, t1, "front").metrics

        stacked_layers = [single_pos.copy() for _ in range(6)]
        b2, t2 = _render_icon_pair(
            tmp_path, "stacked", "front", SKELETON_SEGMENTS, dot_layers=stacked_layers
        )
        m2 = icm.analyze_icon_pair(b2, t2, "front").metrics

        assert m2.blob_saturation > m1.blob_saturation
        assert m1.blob_saturation == pytest.approx(0.0, abs=0.1)

    def test_dot_count_is_lower_bound_flag_always_true(self, tmp_path):
        rng = np.random.default_rng(3)
        pts = rng.uniform(1, 9, size=(10, 2))
        base, twig = _render_icon_pair(
            tmp_path, "t", "front", SKELETON_SEGMENTS, dot_layers=[pts]
        )
        m = icm.analyze_icon_pair(base, twig, "front").metrics
        assert m.dot_count_is_lower_bound is True

    def test_dot_count_reasonable_for_well_separated_dots(self, tmp_path):
        xs, ys = np.meshgrid(np.linspace(0.5, 9.5, 6), np.linspace(0.5, 9.5, 4))
        pts = np.stack([xs.ravel(), ys.ravel()], axis=1)
        base, twig = _render_icon_pair(
            tmp_path, "t", "front", SKELETON_SEGMENTS, dot_layers=[pts]
        )
        m = icm.analyze_icon_pair(base, twig, "front").metrics
        # Lower bound should be in the right ballpark for non-overlapping
        # dots, not off by an order of magnitude.
        assert m.dot_count >= len(pts) * 0.5
        assert m.dot_count <= len(pts) * 1.5


class TestAnalyzeTree:
    def test_per_view_and_aggregate(self, tmp_path):
        rng = np.random.default_rng(4)
        for view in ("front", "side", "top"):
            pts = rng.uniform(1, 9, size=(12, 2))
            _render_icon_pair(
                tmp_path, "Tree_001", view, SKELETON_SEGMENTS, dot_layers=[pts]
            )
        result, analyses = icm.analyze_tree(tmp_path, "Tree_001")
        assert set(result["views"].keys()) == {"front", "side", "top"}
        assert set(analyses.keys()) == {"front", "side", "top"}
        assert "crown_fill_mean" in result["aggregate"]
        assert result["aggregate"]["dot_count_is_lower_bound"] is True

    def test_missing_view_is_skipped_not_fatal(self, tmp_path):
        rng = np.random.default_rng(5)
        pts = rng.uniform(1, 9, size=(8, 2))
        _render_icon_pair(
            tmp_path, "Tree_002", "front", SKELETON_SEGMENTS, dot_layers=[pts]
        )
        result, analyses = icm.analyze_tree(tmp_path, "Tree_002")
        assert set(result["views"].keys()) == {"front"}
        assert set(analyses.keys()) == {"front"}


class TestFindAndResolveTargets:
    def test_find_icon_prefixes_in_dir(self, tmp_path):
        rng = np.random.default_rng(6)
        pts = rng.uniform(1, 9, size=(5, 2))
        tree_a = tmp_path / "species" / "tree_a"
        tree_b = tmp_path / "species" / "tree_b"
        tree_a.mkdir(parents=True)
        tree_b.mkdir(parents=True)
        _render_icon_pair(tree_a, "A", "front", SKELETON_SEGMENTS, [pts])
        _render_icon_pair(tree_a, "A", "side", SKELETON_SEGMENTS, [pts])
        _render_icon_pair(tree_b, "B", "front", SKELETON_SEGMENTS, [pts])

        found = icm.find_icon_prefixes(tmp_path)
        prefixes = {p for _d, p in found}
        assert prefixes == {"A", "B"}

    def test_resolve_targets_directory(self, tmp_path):
        rng = np.random.default_rng(7)
        pts = rng.uniform(1, 9, size=(5, 2))
        _render_icon_pair(tmp_path, "T", "front", SKELETON_SEGMENTS, [pts])
        targets = icm.resolve_targets(tmp_path, icm.VIEWS)
        assert targets == [(tmp_path, "T")]

    def test_resolve_targets_file(self, tmp_path):
        rng = np.random.default_rng(8)
        pts = rng.uniform(1, 9, size=(5, 2))
        base, twig = _render_icon_pair(tmp_path, "T", "front", SKELETON_SEGMENTS, [pts])
        targets = icm.resolve_targets(base, icm.VIEWS)
        assert targets == [(tmp_path, "T")]
        targets2 = icm.resolve_targets(twig, icm.VIEWS)
        assert targets2 == [(tmp_path, "T")]

    def test_resolve_targets_bare_prefix(self, tmp_path):
        rng = np.random.default_rng(9)
        pts = rng.uniform(1, 9, size=(5, 2))
        _render_icon_pair(tmp_path, "T", "front", SKELETON_SEGMENTS, [pts])
        targets = icm.resolve_targets(tmp_path / "T", icm.VIEWS)
        assert targets == [(tmp_path, "T")]

    def test_resolve_targets_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            icm.resolve_targets(tmp_path / "nope", icm.VIEWS)


class TestMainCli:
    def test_main_writes_json_single_tree(self, tmp_path):
        rng = np.random.default_rng(10)
        for view in ("front", "side", "top"):
            pts = rng.uniform(1, 9, size=(10, 2))
            _render_icon_pair(tmp_path, "Tree_003", view, SKELETON_SEGMENTS, [pts])

        json_out = tmp_path / "out.json"
        rc = icm.main([str(tmp_path / "Tree_003"), "--json", str(json_out)])
        assert rc == 0
        payload = json.loads(json_out.read_text())
        assert payload["prefix"] == "Tree_003"
        assert set(payload["views"].keys()) == {"front", "side", "top"}

    def test_main_batch_mode_json_shape(self, tmp_path):
        rng = np.random.default_rng(11)
        for name in ("Tree_A", "Tree_B"):
            pts = rng.uniform(1, 9, size=(6, 2))
            _render_icon_pair(tmp_path, name, "front", SKELETON_SEGMENTS, [pts])

        json_out = tmp_path / "batch.json"
        rc = icm.main([str(tmp_path), "--json", str(json_out), "--views", "front"])
        assert rc == 0
        payload = json.loads(json_out.read_text())
        assert payload["count"] == 2
        prefixes = {t["prefix"] for t in payload["trees"]}
        assert prefixes == {"Tree_A", "Tree_B"}

    def test_main_contact_sheet_single_tree(self, tmp_path):
        rng = np.random.default_rng(12)
        pts = rng.uniform(1, 9, size=(10, 2))
        _render_icon_pair(tmp_path, "Tree_004", "front", SKELETON_SEGMENTS, [pts])

        sheet_out = tmp_path / "sheet.png"
        rc = icm.main(
            [
                str(tmp_path / "Tree_004"),
                "--contact-sheet",
                str(sheet_out),
                "--views",
                "front",
            ]
        )
        assert rc == 0
        assert sheet_out.exists()

    def test_main_no_targets_returns_error(self, tmp_path):
        rc = icm.main([str(tmp_path)])
        assert rc == 1
