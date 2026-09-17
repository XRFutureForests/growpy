"""Tests for growpy.tools.analyze_usda parsing functions."""

import json
from types import SimpleNamespace

import pytest

from growpy.tools.analyze_usda import (
    _find_assembly_files,
    analyze_triangle_budget,
    main,
    parse_int_array,
    parse_vec3f_array,
    print_triangle_budget,
)


class TestParseVec3fArray:
    """Tests for USD point3f[] array parsing."""

    def test_single_point(self):
        text = "point3f[] points = [(1.0, 2.0, 3.0)]"
        result = parse_vec3f_array(text)
        assert len(result) == 1
        assert result[0] == pytest.approx((1.0, 2.0, 3.0))

    def test_multiple_points(self):
        text = "[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]"
        result = parse_vec3f_array(text)
        assert len(result) == 3
        assert result[2] == pytest.approx((7.0, 8.0, 9.0))

    def test_negative_values(self):
        text = "[(-1.5, -2.5, 0.0)]"
        result = parse_vec3f_array(text)
        assert result[0] == pytest.approx((-1.5, -2.5, 0.0))

    def test_empty_string(self):
        result = parse_vec3f_array("")
        assert result == []

    def test_no_parentheses(self):
        result = parse_vec3f_array("[]")
        assert result == []

    def test_multiline_format(self):
        text = """point3f[] points = [
            (1.0, 2.0, 3.0),
            (4.0, 5.0, 6.0),
        ]"""
        result = parse_vec3f_array(text)
        assert len(result) == 2


class TestParseIntArray:
    """Tests for USD int[] array parsing."""

    def test_basic(self):
        text = "[3, 3, 3]"
        result = parse_int_array(text)
        assert result == [3, 3, 3]

    def test_with_prefix(self):
        # Note: int[] in "int[] name =" contains brackets that match first,
        # so extract_array_line is used to isolate the data line before parsing.
        text = "faceVertexCounts = [3, 3, 3]"
        result = parse_int_array(text)
        assert result == [3, 3, 3]

    def test_single_value(self):
        text = "[42]"
        result = parse_int_array(text)
        assert result == [42]

    def test_empty_array(self):
        text = "int[] arr = []"
        result = parse_int_array(text)
        assert result == []

    def test_no_brackets(self):
        result = parse_int_array("no brackets here")
        assert result == []

    def test_negative_values(self):
        text = "[-1, 0, 1]"
        result = parse_int_array(text)
        assert result == [-1, 0, 1]

    def test_whitespace_handling(self):
        text = "[  1 , 2 ,  3  ]"
        result = parse_int_array(text)
        assert result == [1, 2, 3]


# --- Triangle-budget tests (require pxr; run inside the growpy conda env) --
#
# Synthetic USD stages built with pxr directly, mirroring the prim layout
# io/usd/assembly_export.py actually produces (confirmed live against a
# real forest run's silver_fir assembly.usdc):
#   /Assembly/TwigPrototypes/<xform_name>/<child_name>/<child_name>_mesh
# with the PointInstancer's prototypes rel targeting the outer Xform, and
# the sidecar keyed by <child_name>.


@pytest.fixture
def pxr_usd():
    """Lazily import pxr so plain regex tests above don't require it."""
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
    from pxr import Usd, UsdGeom, UsdSkel, Vt

    return SimpleNamespace(Usd=Usd, UsdGeom=UsdGeom, UsdSkel=UsdSkel, Vt=Vt)


def _build_synthetic_assembly(
    pxr_usd,
    path,
    proto_specs=(),  # list of (xform_name, child_name, face_count)
    proto_instance_counts=(),  # instance count per proto_specs entry
    tree_skel_joints=5,
    twig_skel_joints=1,
    add_point_instancer=True,
):
    Usd = pxr_usd.Usd
    UsdGeom = pxr_usd.UsdGeom
    UsdSkel = pxr_usd.UsdSkel
    Vt = pxr_usd.Vt

    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, "/Assembly")
    stage.SetDefaultPrim(root.GetPrim())

    tree_skel = UsdSkel.Skeleton.Define(stage, "/Assembly/TreeSkeleton")
    tree_joint_names = [f"j{i}" for i in range(tree_skel_joints)]
    tree_skel.CreateJointsAttr(Vt.TokenArray(tree_joint_names))

    proto_paths = []
    if proto_specs:
        stage.DefinePrim("/Assembly/TwigPrototypes", "Scope")
        for xform_name, child_name, face_count in proto_specs:
            proto_xform = UsdGeom.Xform.Define(
                stage, f"/Assembly/TwigPrototypes/{xform_name}"
            )
            child_path = f"/Assembly/TwigPrototypes/{xform_name}/{child_name}"
            stage.DefinePrim(child_path, "Xform")
            mesh = UsdGeom.Mesh.Define(stage, f"{child_path}/{child_name}_mesh")
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * face_count))
            twig_skel_path = f"{child_path}/{child_name}_skel"
            twig_skel = UsdSkel.Skeleton.Define(stage, twig_skel_path)
            twig_joint_names = [f"tj{i}" for i in range(twig_skel_joints)]
            twig_skel.CreateJointsAttr(Vt.TokenArray(twig_joint_names))
            proto_paths.append(proto_xform.GetPrim().GetPath())

    if add_point_instancer and proto_paths:
        instancer = UsdGeom.PointInstancer.Define(stage, "/Assembly/TwigInstances")
        instancer.CreatePrototypesRel().SetTargets(proto_paths)
        proto_indices = []
        for i, count in enumerate(proto_instance_counts):
            proto_indices += [i] * count
        instancer.CreateProtoIndicesAttr(Vt.IntArray(proto_indices))
        instancer.CreatePositionsAttr(
            Vt.Vec3fArray([(0.0, 0.0, 0.0)] * len(proto_indices))
        )

    stage.GetRootLayer().Save()
    return stage


class TestAnalyzeTriangleBudget:
    def test_sidecar_preferred_over_usd_mesh_fallback(self, tmp_path, pxr_usd):
        assembly_path = tmp_path / "test_assembly.usda"
        _build_synthetic_assembly(
            pxr_usd,
            assembly_path,
            proto_specs=[
                ("protoA", "child_a", 10),  # sidecar will claim 999
                ("protoB", "child_b", 7),  # no sidecar -> USD mesh count (7)
            ],
            proto_instance_counts=[3, 2],
        )

        twigs_root = tmp_path / "twigs"
        twigs_root.mkdir()
        (twigs_root / "child_a_leaf_area.json").write_text(
            json.dumps(
                {
                    "leaf_area_m2": 0.5,
                    "leaf_faces": 999,
                    "total_faces": 999,
                    "leaf_material_indices": [0],
                }
            )
        )

        stats = analyze_triangle_budget(assembly_path, twigs_root=twigs_root)

        assert stats["twig_instances"] == 5
        assert stats["twig_instances_per_prototype"] == {"protoA": 3, "protoB": 2}
        assert stats["prototype_faces"]["protoA"] == 999
        assert stats["prototype_face_source"]["protoA"] == "sidecar"
        assert stats["prototype_faces"]["protoB"] == 7
        assert stats["prototype_face_source"]["protoB"] == "usd_mesh"
        assert stats["expanded_triangles"] == 3 * 999 + 2 * 7

        # Leaf area: only protoA contributes (has a sidecar); protoB has
        # none, so the sum is flagged incomplete rather than silently
        # under-reported as if it were the true total.
        assert stats["leaf_area_m2"] == pytest.approx(3 * 0.5)
        assert stats["leaf_area_m2_incomplete"] is True
        assert stats["leaf_area_m2_is_sanity_check_only"] is True

        # Tree skeleton only -- twig-prototype skeletons excluded from the
        # headline number but still visible in the full breakdown.
        assert stats["skeleton_joints"] == 5
        assert len(stats["skeleton_joints_by_prim"]) == 3

    def test_no_point_instancer_zero_budget(self, tmp_path, pxr_usd):
        assembly_path = tmp_path / "no_twigs_assembly.usda"
        _build_synthetic_assembly(pxr_usd, assembly_path, proto_specs=[])

        stats = analyze_triangle_budget(assembly_path, twigs_root=tmp_path / "twigs")

        assert stats["twig_instances"] == 0
        assert stats["prototype_faces"] == {}
        assert stats["expanded_triangles"] == 0
        assert stats["leaf_area_m2"] == 0.0
        assert stats["skeleton_joints"] == 5

    def test_missing_sidecar_dir_falls_back_to_usd_mesh(self, tmp_path, pxr_usd):
        assembly_path = tmp_path / "assembly.usda"
        _build_synthetic_assembly(
            pxr_usd,
            assembly_path,
            proto_specs=[("protoA", "child_a", 42)],
            proto_instance_counts=[4],
        )

        stats = analyze_triangle_budget(
            assembly_path, twigs_root=tmp_path / "does_not_exist"
        )

        assert stats["prototype_faces"]["protoA"] == 42
        assert stats["prototype_face_source"]["protoA"] == "usd_mesh"
        assert stats["expanded_triangles"] == 4 * 42
        assert stats["leaf_area_m2_incomplete"] is True

    def test_usdc_binary_format_works(self, tmp_path, pxr_usd):
        """The live pipeline default is [export] usd_format = 'usdc'."""
        assembly_path = tmp_path / "binary_assembly.usdc"
        _build_synthetic_assembly(
            pxr_usd,
            assembly_path,
            proto_specs=[("protoA", "child_a", 5)],
            proto_instance_counts=[2],
        )

        stats = analyze_triangle_budget(assembly_path, twigs_root=tmp_path / "twigs")

        assert stats["twig_instances"] == 2
        assert stats["prototype_faces"]["protoA"] == 5
        assert stats["expanded_triangles"] == 10

    def test_file_size_and_stems_ref_fields_present(self, tmp_path, pxr_usd):
        assembly_path = tmp_path / "assembly.usda"
        _build_synthetic_assembly(pxr_usd, assembly_path, proto_specs=[])
        stats = analyze_triangle_budget(assembly_path, twigs_root=tmp_path / "twigs")
        assert stats["file_size_bytes"] == assembly_path.stat().st_size
        assert isinstance(stats["stems_ref_files"], list)


class TestPrintTriangleBudget:
    def test_prints_without_crashing(self, tmp_path, pxr_usd, capsys):
        assembly_path = tmp_path / "assembly.usda"
        _build_synthetic_assembly(
            pxr_usd,
            assembly_path,
            proto_specs=[("protoA", "child_a", 3)],
            proto_instance_counts=[1],
        )
        stats = analyze_triangle_budget(assembly_path, twigs_root=tmp_path / "twigs")
        print_triangle_budget(stats)
        out = capsys.readouterr().out
        assert "Expanded triangles" in out
        assert "NOT a gate" in out


class TestFindAssemblyFiles:
    def test_single_assembly_file(self, tmp_path):
        f = tmp_path / "tree_assembly.usda"
        f.write_text("")
        assert _find_assembly_files(f) == [f]

    def test_single_non_assembly_file_excluded(self, tmp_path):
        f = tmp_path / "tree_stems.usda"
        f.write_text("")
        assert _find_assembly_files(f) == []

    def test_directory_finds_both_extensions_recursively(self, tmp_path):
        (tmp_path / "a_assembly.usda").write_text("")
        (tmp_path / "b_assembly.usdc").write_text("")
        (tmp_path / "c_stems.usda").write_text("")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "d_assembly.usdc").write_text("")

        found = {p.name for p in _find_assembly_files(tmp_path)}
        assert found == {"a_assembly.usda", "b_assembly.usdc", "d_assembly.usdc"}

    def test_nonexistent_path_returns_empty(self, tmp_path):
        assert _find_assembly_files(tmp_path / "nope") == []


class TestMainTriangleBudgetCli:
    def test_triangle_budget_flag_writes_json(self, tmp_path, pxr_usd, monkeypatch):
        assembly_path = tmp_path / "cli_assembly.usda"
        _build_synthetic_assembly(
            pxr_usd,
            assembly_path,
            proto_specs=[("protoA", "child_a", 6)],
            proto_instance_counts=[2],
        )
        json_out = tmp_path / "budget.json"
        twigs_root = tmp_path / "twigs"

        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-analyze-usda",
                str(assembly_path),
                "--triangle-budget",
                "--json",
                str(json_out),
                "--twigs-dir",
                str(twigs_root),
            ],
        )
        rc = main()
        assert rc == 0
        records = json.loads(json_out.read_text())
        assert len(records) == 1
        assert records[0]["expanded_triangles"] == 12

    def test_triangle_budget_no_assembly_found_returns_error(
        self, tmp_path, monkeypatch
    ):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(
            "sys.argv", ["growpy-analyze-usda", str(empty_dir), "--triangle-budget"]
        )
        rc = main()
        assert rc == 1
