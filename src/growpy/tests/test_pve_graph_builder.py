"""Tests for growpy.io.unreal.pve_graph_builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from growpy.io.unreal.pve_graph_builder import (
    DistributorSpec,
    FoliageVectorSpec,
    PVEGraphSpec,
    TreeChainSpec,
    generate_pve_graph_builder_script,
)


def _chain(name: str = "SK_Test", **kwargs) -> TreeChainSpec:
    return TreeChainSpec(
        growth_json=Path("data/tmp/tree.json"),
        mesh_name=name,
        distributor=DistributorSpec(branch_density=kwargs.pop("density", 17), **kwargs),
    )


def _graph(**kwargs) -> PVEGraphSpec:
    defaults = {
        "graph_name": "PVG_Test",
        "chains": (_chain(),),
        "palette_meshes": ("/Game/Foliage/SM_twig_a",),
        "bark_material": "/Game/Bark/MI_bark",
        "export_folder": "/Game/Exported",
    }
    defaults.update(kwargs)
    return PVEGraphSpec(**defaults)


class TestFoliageVectorSpec:
    def test_defaults_to_the_live_slot(self):
        spec = FoliageVectorSpec()
        assert spec.vector2 == "AXIS_AIM"
        assert spec.vector1 is None
        assert spec.dual is False

    def test_vector1_without_dual_is_rejected(self):
        # With duals off the distributor evaluates Vector2 only, so naming
        # Vector1 is a silent no-op in the engine.
        with pytest.raises(ValueError, match="only evaluated when dual"):
            FoliageVectorSpec(vector1="AXIS_FLATTEN")

    def test_vector1_with_dual_is_allowed(self):
        spec = FoliageVectorSpec(vector1="AXIS_FLATTEN", dual=True)
        assert spec.vector1 == "AXIS_FLATTEN"

    def test_aim_and_face_have_different_enums(self):
        FoliageVectorSpec(kind="aim", vector2="BRANCH_UP_FLATTEN")
        # BRANCH_UP_FLATTEN is an aim-only vector type.
        with pytest.raises(ValueError, match="not one of"):
            FoliageVectorSpec(kind="face", vector2="BRANCH_UP_FLATTEN")
        # APICAL is a face-only vector type.
        with pytest.raises(ValueError, match="not one of"):
            FoliageVectorSpec(kind="aim", vector2="APICAL")

    def test_rejects_bad_kind_strength_and_axis(self):
        with pytest.raises(ValueError, match="kind must be"):
            FoliageVectorSpec(kind="roll")
        with pytest.raises(ValueError, match="strength"):
            FoliageVectorSpec(strength=1.5)
        with pytest.raises(ValueError, match="non-zero 3-vector"):
            FoliageVectorSpec(axis=(0.0, 0.0, 0.0))

    def test_tips_obey_by_default(self):
        # The engine default skips tip instances, which are a majority of a
        # small tree's foliage.
        assert FoliageVectorSpec().affect_tip is True


class TestDistributorSpec:
    def test_scale_ramp_defaults_flat_at_one(self):
        # The engine default ramp of 1.0 -> 0.1 places foliage at roughly a
        # tenth of natural size under a Plant basis.
        assert DistributorSpec(branch_density=17).scale_ramp == (1.0, 1.0)

    def test_auto_align_end_off_by_default(self):
        assert DistributorSpec(branch_density=17).auto_align_end is False

    def test_face_defaults_to_axis_aim(self):
        # AxisAim on world up lays sprays flat; AxisFlatten stands them on edge.
        spec = DistributorSpec(branch_density=17)
        assert spec.face is not None
        assert spec.face.vector2 == "AXIS_AIM"
        assert spec.aim is None

    @pytest.mark.parametrize("density", [0, -1])
    def test_rejects_non_positive_density(self, density):
        with pytest.raises(ValueError, match="branch_density"):
            DistributorSpec(branch_density=density)

    def test_rejects_unknown_enums(self):
        with pytest.raises(ValueError, match="spacing_basis"):
            DistributorSpec(branch_density=1, spacing_basis="TREE")
        with pytest.raises(ValueError, match="phyllotaxy_type"):
            DistributorSpec(branch_density=1, phyllotaxy_type="PECTINATE")
        with pytest.raises(ValueError, match="phyllotaxy_formation"):
            DistributorSpec(branch_density=1, phyllotaxy_formation="SPIRAL")

    def test_rejects_bad_relative_range_and_ramp(self):
        with pytest.raises(ValueError, match="relative_start"):
            DistributorSpec(branch_density=1, relative_start=0.8, relative_end=0.2)
        with pytest.raises(ValueError, match="scale_ramp"):
            DistributorSpec(branch_density=1, scale_ramp=(1.0, 0.0))

    def test_rejects_swapped_vector_kinds(self):
        with pytest.raises(ValueError, match="face spec"):
            DistributorSpec(
                branch_density=1,
                face=FoliageVectorSpec(kind="aim", vector2="AXIS_AIM"),
            )
        with pytest.raises(ValueError, match="aim spec"):
            DistributorSpec(
                branch_density=1,
                aim=FoliageVectorSpec(kind="face", vector2="AXIS_AIM"),
            )


class TestPVEGraphSpec:
    def test_rejects_empty_chains_and_palette(self):
        with pytest.raises(ValueError, match="no chains"):
            _graph(chains=())
        with pytest.raises(ValueError, match="empty foliage palette"):
            _graph(palette_meshes=())

    def test_rejects_duplicate_mesh_names(self):
        # Two chains exporting the same name silently overwrite each other.
        with pytest.raises(ValueError, match="duplicate mesh names"):
            _graph(chains=(_chain("SK_A"), _chain("SK_A")))

    def test_rejects_unknown_nanite_shape(self):
        with pytest.raises(ValueError, match="nanite_shape_preservation"):
            _graph(nanite_shape_preservation="SMOOTH")


class TestGenerateScript:
    def test_writes_a_runnable_script(self, tmp_path):
        path = generate_pve_graph_builder_script(tmp_path, [_graph()])
        assert path.exists()
        body = path.read_text(encoding="utf-8")
        compile(body, str(path), "exec")  # syntactically valid Python
        assert "PVGrowthDataJsonImporterSettings" in body
        assert "PVPresetLoaderSettings" not in body  # the deprecated 5.8 no-op

    def test_embeds_chain_settings(self, tmp_path):
        path = generate_pve_graph_builder_script(
            tmp_path, [_graph(chains=(_chain("SK_Beech_r05", density=42),))]
        )
        body = path.read_text(encoding="utf-8")
        assert "SK_Beech_r05" in body
        assert "'branch_density': 42" in body

    def test_ramp_is_serialised_for_the_native_importer(self, tmp_path):
        # EditorCurveData has no EditAnywhere, so it is only reachable through
        # import_text with UE's native struct syntax.
        path = generate_pve_graph_builder_script(tmp_path, [_graph()])
        body = path.read_text(encoding="utf-8")
        assert "EditorCurveData=(Keys=(" in body
        assert "InterpMode=RCIM_Linear,Time=0.000000,Value=1.000000" in body

    def test_growth_json_path_is_absolute_and_forward_slashed(self, tmp_path):
        json_path = tmp_path / "sub" / "tree.json"
        chain = TreeChainSpec(
            growth_json=json_path,
            mesh_name="SK_X",
            distributor=DistributorSpec(branch_density=3),
        )
        path = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = path.read_text(encoding="utf-8")
        assert str(json_path.resolve()).replace("\\", "/") in body
        assert "\\\\" not in body.split("'growth_json'")[1][:200]

    def test_rejects_empty_and_duplicate_graphs(self, tmp_path):
        with pytest.raises(ValueError, match="no graphs"):
            generate_pve_graph_builder_script(tmp_path, [])
        with pytest.raises(ValueError, match="duplicate graph names"):
            generate_pve_graph_builder_script(tmp_path, [_graph(), _graph()])

    def test_creates_missing_output_dir(self, tmp_path):
        target = tmp_path / "nested" / "scripts"
        path = generate_pve_graph_builder_script(target, [_graph()])
        assert path.parent == target
