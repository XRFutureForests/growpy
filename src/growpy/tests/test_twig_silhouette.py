"""Tests for growpy.utils.twig_silhouette.

Pure-geometry tests (no pxr) use small synthetic point/triangle arrays.
USD-loading tests build tiny synthetic ``.usda`` stages with pxr directly
(mirroring test_analyze_usda.py's ``pxr_usd`` fixture pattern) so nothing
here depends on the licensed twig assets under data/assets/twigs/.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from growpy.utils.twig_silhouette import (
    DEFAULT_PX_SIZE_M,
    discover_static_prototypes,
    fibonacci_sphere_directions,
    load_leaf_geometry,
    measure_and_write_prototype,
    measure_prototype_silhouette,
    measure_silhouette,
    project_silhouette_area,
    prototype_name_from_static_path,
    run_over_all_twigs,
    write_silhouette_sidecar,
)

# --- geometry fixtures -------------------------------------------------------

# A single 1m x 1m square in the XY plane (z=0), split into two triangles.
_SQUARE_POINTS = np.array(
    [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
    ]
)
_SQUARE_TRIANGLES = np.array([[0, 1, 2], [0, 2, 3]])

# A unit cube (side 1), all 12 triangles. Convex, so the classical
# mean-projected-area = 1/4 * surface_area result applies and gives an
# independent analytic check on the whole measure_silhouette pipeline
# (orientation sampling + rasterization + union) without relying on any
# non-convex-specific reasoning.
_CUBE_POINTS = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=np.float64,
)
_CUBE_TRIANGLES = np.array(
    [
        [0, 1, 2], [0, 2, 3],  # bottom (z=0)
        [4, 6, 5], [4, 7, 6],  # top (z=1)
        [0, 4, 5], [0, 5, 1],  # y=0
        [3, 2, 6], [3, 6, 7],  # y=1
        [0, 3, 7], [0, 7, 4],  # x=0
        [1, 5, 6], [1, 6, 2],  # x=1
    ]
)


class TestFibonacciSphereDirections:
    def test_returns_n_unit_vectors(self):
        dirs = fibonacci_sphere_directions(20)
        assert dirs.shape == (20, 3)
        norms = np.linalg.norm(dirs, axis=1)
        assert norms == pytest.approx(np.ones(20), abs=1e-9)

    def test_deterministic(self):
        a = fibonacci_sphere_directions(15)
        b = fibonacci_sphere_directions(15)
        assert np.array_equal(a, b)

    def test_rejects_non_positive_n(self):
        with pytest.raises(ValueError):
            fibonacci_sphere_directions(0)


class TestProjectSilhouetteArea:
    def test_flat_square_viewed_face_on(self):
        area = project_silhouette_area(
            _SQUARE_POINTS, _SQUARE_TRIANGLES, np.array([0.0, 0.0, 1.0]), px_size_m=1e-3
        )
        assert area == pytest.approx(1.0, rel=0.01)

    def test_empty_triangles_zero_area(self):
        area = project_silhouette_area(
            _SQUARE_POINTS, np.empty((0, 3), dtype=np.int64), np.array([0.0, 0.0, 1.0])
        )
        assert area == 0.0

    def test_overlapping_triangles_not_double_counted(self):
        """Two coincident squares should measure as ONE square's worth of
        area, not two -- this is the core silhouette-vs-leaf-area distinction.
        """
        points = np.vstack([_SQUARE_POINTS, _SQUARE_POINTS])  # duplicate
        triangles = np.vstack([_SQUARE_TRIANGLES, _SQUARE_TRIANGLES + 4])
        area = project_silhouette_area(
            points, triangles, np.array([0.0, 0.0, 1.0]), px_size_m=1e-3
        )
        # Sum of per-triangle areas would be 2.0; union must not double count.
        assert area == pytest.approx(1.0, rel=0.01)

    def test_grid_size_is_capped(self):
        """A pathologically fine px_size relative to extent must not hang;
        the grid is coarsened to respect max_grid_dim.
        """
        area = project_silhouette_area(
            _SQUARE_POINTS,
            _SQUARE_TRIANGLES,
            np.array([0.0, 0.0, 1.0]),
            px_size_m=1e-6,
            max_grid_dim=100,
        )
        assert area == pytest.approx(1.0, rel=0.1)


class TestMeasureSilhouette:
    def test_cube_matches_convex_body_theorem(self):
        """Mean projected area of a convex body = 1/4 its surface area.

        Unit cube surface area = 6, so mean projection should be ~1.5.
        This validates the sampling + rasterization + union pipeline
        end-to-end against an independent analytic result (this argument
        does NOT hold for the non-convex twig sprays this module actually
        targets -- see module docstring -- but a cube is exactly the
        convex case the theorem covers, so it is a valid sanity check).
        """
        result = measure_silhouette(
            _CUBE_POINTS, _CUBE_TRIANGLES, n_orientations=256, px_size_m=2e-3
        )
        assert result["silhouette_area_m2"] == pytest.approx(1.5, rel=0.05)

    def test_cube_axis_aligned_views_are_unit_area(self):
        result = measure_silhouette(
            _CUBE_POINTS, _CUBE_TRIANGLES, n_orientations=8, px_size_m=2e-3
        )
        for axis_area in result["axis_aligned_silhouette_area_m2"].values():
            assert axis_area == pytest.approx(1.0, rel=0.02)

    def test_result_schema(self):
        result = measure_silhouette(
            _SQUARE_POINTS, _SQUARE_TRIANGLES, n_orientations=4, px_size_m=1e-3
        )
        for key in (
            "silhouette_area_m2",
            "silhouette_area_std_m2",
            "silhouette_area_min_m2",
            "silhouette_area_max_m2",
            "n_orientations",
            "px_size_m",
            "axis_aligned_silhouette_area_m2",
        ):
            assert key in result
        assert result["n_orientations"] == 4
        assert set(result["axis_aligned_silhouette_area_m2"].keys()) == {"x", "y", "z"}


class TestPrototypeNameFromStaticPath:
    def test_strips_static_suffix(self, tmp_path):
        p = tmp_path / "european_beech_foliage_a_static.usda"
        assert prototype_name_from_static_path(p) == "european_beech_foliage_a"

    def test_leaves_non_static_name_unchanged(self, tmp_path):
        p = tmp_path / "some_prototype.usda"
        assert prototype_name_from_static_path(p) == "some_prototype"


# --- pxr-backed tests (require the growpy conda env) ------------------------


@pytest.fixture
def pxr_usd():
    """Lazily import pxr so the pure-geometry tests above don't require it."""
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
    from pxr import Usd, UsdGeom, Vt

    return SimpleNamespace(Usd=Usd, UsdGeom=UsdGeom, Vt=Vt)


def _build_synthetic_static_usda(
    pxr_usd,
    path,
    prototype_name: str,
    points,
    triangles,
    subsets: dict[str, list[int]] | None = None,
):
    """Build a minimal twig-prototype-shaped ``_static.usda`` file.

    Mirrors the real pipeline's layout: a Mesh prim under an Xform default
    prim, with one GeomSubset per material (named ``<prototype>_<material>``,
    e.g. ``..._leaf`` / ``..._bark``) when ``subsets`` is given, matching
    io/usd/twig_export.py's naming.
    """
    Usd = pxr_usd.Usd
    UsdGeom = pxr_usd.UsdGeom
    Vt = pxr_usd.Vt

    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, f"/{prototype_name}")
    stage.SetDefaultPrim(root.GetPrim())

    mesh_path = f"/{prototype_name}/{prototype_name}_mesh"
    mesh = UsdGeom.Mesh.Define(stage, mesh_path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([tuple(p) for p in points]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(triangles)))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray([int(i) for tri in triangles for i in tri])
    )

    if subsets:
        for name, face_indices in subsets.items():
            subset = UsdGeom.Subset.Define(stage, f"{mesh_path}/{name}")
            subset.CreateElementTypeAttr("face")
            subset.CreateIndicesAttr(Vt.IntArray([int(i) for i in face_indices]))

    stage.GetRootLayer().Save()
    return stage


class TestLoadLeafGeometry:
    def test_no_subsets_treats_all_faces_as_leaf(self, tmp_path, pxr_usd):
        path = tmp_path / "conifer_spray_static.usda"
        _build_synthetic_static_usda(
            pxr_usd, path, "conifer_spray", _SQUARE_POINTS, _SQUARE_TRIANGLES
        )
        points, leaf_tris, total_faces = load_leaf_geometry(path)
        assert total_faces == 2
        assert leaf_tris.shape[0] == 2

    def test_bark_subset_excluded(self, tmp_path, pxr_usd):
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(
            pxr_usd,
            path,
            "broadleaf",
            _SQUARE_POINTS,
            _SQUARE_TRIANGLES,
            subsets={"broadleaf_leaf": [0], "broadleaf_bark": [1]},
        )
        points, leaf_tris, total_faces = load_leaf_geometry(path)
        assert total_faces == 2
        assert leaf_tris.shape[0] == 1
        assert np.array_equal(leaf_tris[0], _SQUARE_TRIANGLES[0])

    def test_all_subsets_excluded_falls_back_to_all_faces(self, tmp_path, pxr_usd):
        path = tmp_path / "all_bark_static.usda"
        _build_synthetic_static_usda(
            pxr_usd,
            path,
            "all_bark",
            _SQUARE_POINTS,
            _SQUARE_TRIANGLES,
            subsets={"all_bark_bark": [0], "all_bark_wood": [1]},
        )
        _, leaf_tris, total_faces = load_leaf_geometry(path)
        assert leaf_tris.shape[0] == total_faces == 2

    def test_non_triangular_face_raises(self, tmp_path, pxr_usd):
        Usd = pxr_usd.Usd
        UsdGeom = pxr_usd.UsdGeom
        Vt = pxr_usd.Vt
        path = tmp_path / "quad_static.usda"
        stage = Usd.Stage.CreateNew(str(path))
        root = UsdGeom.Xform.Define(stage, "/quad")
        stage.SetDefaultPrim(root.GetPrim())
        mesh = UsdGeom.Mesh.Define(stage, "/quad/quad_mesh")
        mesh.CreatePointsAttr(Vt.Vec3fArray([tuple(p) for p in _SQUARE_POINTS]))
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]))
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([0, 1, 2, 3]))
        stage.GetRootLayer().Save()

        with pytest.raises(ValueError, match="non-triangular"):
            load_leaf_geometry(path)


class TestMeasureProtoypeSilhouette:
    def test_ratio_computed_when_leaf_area_sidecar_present(self, tmp_path, pxr_usd):
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(
            pxr_usd, path, "broadleaf", _SQUARE_POINTS, _SQUARE_TRIANGLES
        )
        (tmp_path / "broadleaf_leaf_area.json").write_text(
            json.dumps({"leaf_area_m2": 2.0})
        )

        result = measure_prototype_silhouette(path, n_orientations=4, px_size_m=1e-3)
        assert result["prototype"] == "broadleaf"
        assert result["leaf_area_m2"] == 2.0
        assert result["silhouette_to_leaf_area_ratio"] == pytest.approx(
            result["silhouette_area_m2"] / 2.0
        )
        assert "definition" in result and "orientation" in result["definition"].lower()

    def test_ratio_none_when_leaf_area_sidecar_missing(self, tmp_path, pxr_usd):
        path = tmp_path / "no_sidecar_static.usda"
        _build_synthetic_static_usda(
            pxr_usd, path, "no_sidecar", _SQUARE_POINTS, _SQUARE_TRIANGLES
        )
        result = measure_prototype_silhouette(path, n_orientations=4, px_size_m=1e-3)
        assert result["leaf_area_m2"] is None
        assert result["silhouette_to_leaf_area_ratio"] is None


class TestSidecarWriting:
    def test_write_and_roundtrip(self, tmp_path, pxr_usd):
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(
            pxr_usd, path, "broadleaf", _SQUARE_POINTS, _SQUARE_TRIANGLES
        )
        result, out_path = measure_and_write_prototype(
            path, n_orientations=4, px_size_m=1e-3
        )
        assert out_path.name == "broadleaf_silhouette.json"
        assert out_path.parent == tmp_path
        loaded = json.loads(out_path.read_text())
        assert loaded["prototype"] == "broadleaf"
        assert loaded["silhouette_area_m2"] == pytest.approx(
            result["silhouette_area_m2"]
        )

    def test_write_silhouette_sidecar_uses_output_dir_override(self, tmp_path, pxr_usd):
        path = tmp_path / "broadleaf_static.usda"
        _build_synthetic_static_usda(
            pxr_usd, path, "broadleaf", _SQUARE_POINTS, _SQUARE_TRIANGLES
        )
        result = measure_prototype_silhouette(path, n_orientations=4, px_size_m=1e-3)
        out_dir = tmp_path / "elsewhere"
        out_dir.mkdir()
        out_path = write_silhouette_sidecar(result, path, output_dir=out_dir)
        assert out_path == out_dir / "broadleaf_silhouette.json"
        assert out_path.exists()


class TestBatchDiscoveryAndRun:
    def test_discover_finds_only_static_files(self, tmp_path, pxr_usd):
        species_dir = tmp_path / "some_species_twig"
        species_dir.mkdir()
        _build_synthetic_static_usda(
            pxr_usd,
            species_dir / "some_species_a_static.usda",
            "some_species_a",
            _SQUARE_POINTS,
            _SQUARE_TRIANGLES,
        )
        # A skeletal sibling that discover_static_prototypes must ignore.
        (species_dir / "some_species_a_skeletal.usda").write_text("#usda 1.0\n")

        found = discover_static_prototypes(tmp_path)
        assert found == [species_dir / "some_species_a_static.usda"]

    def test_run_over_all_twigs_writes_sidecar_per_prototype(self, tmp_path, pxr_usd):
        species_dir = tmp_path / "some_species_twig"
        species_dir.mkdir()
        for name in ("some_species_a", "some_species_b"):
            _build_synthetic_static_usda(
                pxr_usd,
                species_dir / f"{name}_static.usda",
                name,
                _SQUARE_POINTS,
                _SQUARE_TRIANGLES,
            )

        results = run_over_all_twigs(tmp_path, n_orientations=4, px_size_m=1e-3)
        assert len(results) == 2
        names = {r["prototype"] for r in results}
        assert names == {"some_species_a", "some_species_b"}
        for name in names:
            assert (species_dir / f"{name}_silhouette.json").exists()


def test_default_px_size_is_finer_than_millimeter():
    # Sanity guard: DEFAULT_PX_SIZE_M is documented as 0.05mm; catch an
    # accidental unit error (e.g. mistaking meters for millimeters).
    assert 1e-6 < DEFAULT_PX_SIZE_M < 1e-3
