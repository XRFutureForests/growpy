"""Tests for growpy.io.unreal.pve_graph_builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from growpy.io.unreal.pve_graph_builder import (
    DEFAULT_SAPLING_WIND_SETTINGS,
    DEFAULT_TREE_WIND_SETTINGS,
    ConditionInfluence,
    ConditionSpec,
    DistributorSpec,
    FoliageLayer,
    FoliageVectorSpec,
    JitterSpec,
    PaletteAttributes,
    PaletteEntry,
    PVEGraphSpec,
    TreeChainSpec,
    generate_pve_graph_builder_script,
    mask_fraction_of,
    masked_palette,
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

    def test_explicit_ramp_keys_and_blend_attribute(self):
        # A dual entry blended on WorldUpDot is how a leader keeps pointing up
        # while every other twig is flattened: AxisFlatten everywhere, crossing
        # to AxisAim-on-up only when the growth axis is already near vertical.
        spec = FoliageVectorSpec(
            kind="aim", vector1="AXIS_FLATTEN", vector2="AXIS_AIM", dual=True,
            blend_attribute="WORLD_UP_DOT",
            ramp=((0.0, 0.0), (0.9, 0.0), (1.0, 1.0)),
        )
        assert spec.ramp[1] == (0.9, 0.0)
        with pytest.raises(ValueError, match="blend_attribute"):
            FoliageVectorSpec(blend_attribute="GRAVITY")
        with pytest.raises(ValueError, match="ascending"):
            FoliageVectorSpec(ramp=((1.0, 1.0), (0.0, 0.0)))
        with pytest.raises(ValueError, match="two"):
            FoliageVectorSpec(ramp=((0.0, 1.0),))


class TestJitterSpec:
    def test_degrees_become_a_fraction_of_a_half_turn(self, tmp_path):
        # The engine's strength is multiplied by PI, so 18 deg = 0.1.
        chain = _chain("SK_x", density=3)
        dist = DistributorSpec(
            branch_density=3, jitter=(JitterSpec("PITCH", 18.0, seed=7),)
        )
        chain = TreeChainSpec(chain.growth_json, chain.mesh_name, dist)
        body = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = body.read_text(encoding="utf-8")
        assert "'mode': 'PITCH'" in body
        assert "'strength': 0.1" in body
        assert "'seed': 7" in body

    def test_rejects_bad_mode_and_range(self):
        with pytest.raises(ValueError, match="mode"):
            JitterSpec("TWIST", 10.0)
        with pytest.raises(ValueError, match="degrees"):
            JitterSpec("ROLL", 0.0)
        with pytest.raises(ValueError, match="degrees"):
            JitterSpec("ROLL", 181.0)

    def test_no_jitter_by_default(self):
        assert DistributorSpec(branch_density=3).jitter == ()


class TestDistributorSpec:
    def test_scale_ramp_defaults_flat_at_one(self):
        # The engine default ramp of 1.0 -> 0.1 places foliage at roughly a
        # tenth of natural size under a Plant basis.
        assert DistributorSpec(branch_density=17).scale_ramp == (1.0, 1.0)

    def test_auto_align_end_off_by_default(self):
        assert DistributorSpec(branch_density=17).auto_align_end is False

    def test_axil_ramp_and_single_tip_are_emitted(self):
        # The engine ramps the axil angle 0 -> 1 along the plant by default,
        # so a constant angle needs the ramp flattened; and one instance at a
        # tip is what a conifer leader wants.
        spec = DistributorSpec(branch_density=17)
        assert spec.axil_angle_ramp == (0.0, 1.0)
        assert spec.single_bud_tip is True
        flat = DistributorSpec(branch_density=17, axil_angle_ramp=(1.0, 1.0))
        assert flat.axil_angle_ramp == (1.0, 1.0)

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


class TestTreeChainSpec:
    def test_defaults_to_the_tree_wind_preset(self):
        # What the engine's own constructor would load; explicit so it is
        # visible in the plan and checked by the script's preflight.
        assert _chain().wind_settings == DEFAULT_TREE_WIND_SETTINGS
        assert DEFAULT_TREE_WIND_SETTINGS.startswith("/ProceduralVegetationEditor/")
        assert DEFAULT_SAPLING_WIND_SETTINGS != DEFAULT_TREE_WIND_SETTINGS

    def test_rejects_an_empty_wind_asset(self):
        # A null WindSettings exports bone chains with no simulation groups.
        with pytest.raises(ValueError, match="wind_settings"):
            TreeChainSpec(
                growth_json=Path("t.json"),
                mesh_name="SK_X",
                distributor=DistributorSpec(branch_density=3),
                wind_settings="",
            )


class TestPalette:
    def test_a_mask_needs_no_mesh_but_a_real_entry_does(self):
        # The palette node's own check skips masks; a [None] non-mask entry
        # fails the whole graph at execute time.
        assert PaletteEntry(mesh=None, use_as_mask=True).mesh is None
        with pytest.raises(ValueError, match="needs a mesh"):
            PaletteEntry(mesh=None)

    def test_attributes_are_unit_interval(self):
        PaletteAttributes(scale=1.0, tip=True)
        with pytest.raises(ValueError, match="height"):
            PaletteAttributes(height=1.5)

    def test_masked_palette_fraction_is_masks_over_entries(self):
        # Uniform pick over every entry, mask included: f = m / (r*k + m).
        palette = masked_palette(["/G/a", "/G/b", "/G/c"], 1)
        assert len(palette) == 4
        assert mask_fraction_of(palette) == pytest.approx(0.25)
        doubled = masked_palette(["/G/a", "/G/b", "/G/c"], 2, repeats=2)
        assert [e.mesh for e in doubled[:6]] == ["/G/a", "/G/b", "/G/c"] * 2
        assert mask_fraction_of(doubled) == pytest.approx(0.25)
        assert mask_fraction_of(masked_palette(["/G/a"], 0)) == 0.0

    def test_masked_palette_rejects_nonsense(self):
        with pytest.raises(ValueError, match="at least one mesh"):
            masked_palette([], 1)
        with pytest.raises(ValueError, match="repeats"):
            masked_palette(["/G/a"], 1, repeats=0)

    def test_a_chain_palette_of_only_masks_is_refused(self):
        # Every pick would spawn nothing and the tree would export bare.
        with pytest.raises(ValueError, match="no real entry"):
            TreeChainSpec(
                growth_json=Path("t.json"),
                mesh_name="SK_X",
                distributor=DistributorSpec(branch_density=3),
                palette=(PaletteEntry(mesh=None, use_as_mask=True),),
            )


class TestConditionSpec:
    def test_active_lists_only_the_set_conditions_in_engine_order(self):
        spec = ConditionSpec(
            tip=ConditionInfluence(),
            scale=ConditionInfluence(weight=0.863),
            minimum_candidates=2,
        )
        assert list(spec.active()) == ["scale", "tip"]
        assert ConditionSpec().active() == {}

    def test_ranges_follow_the_uproperty_clamps(self):
        with pytest.raises(ValueError, match="weight"):
            ConditionInfluence(weight=1.5)
        with pytest.raises(ValueError, match="offset"):
            ConditionInfluence(offset=-1.5)
        with pytest.raises(ValueError, match="cutoff_threshold"):
            ConditionSpec(cutoff_threshold=2.0)
        with pytest.raises(ValueError, match="minimum_candidates"):
            ConditionSpec(minimum_candidates=0)


class TestGenerationBand:
    def test_off_by_default_and_one_sided_bands_are_allowed(self):
        assert DistributorSpec(branch_density=3).generation_band is None
        assert DistributorSpec(branch_density=3, generation_band=(4, None))
        assert DistributorSpec(branch_density=3, generation_band=(None, 2))

    def test_rejects_an_empty_zero_based_or_inverted_band(self):
        # The convention is 1-based with the trunk = 1 (Epic's own graphs and
        # PVE's ComputeBudDevelopment: Generation = len(BranchParents)).
        with pytest.raises(ValueError, match="limits nothing"):
            DistributorSpec(branch_density=3, generation_band=(None, None))
        with pytest.raises(ValueError, match="1-based"):
            DistributorSpec(branch_density=3, generation_band=(0, 2))
        with pytest.raises(ValueError, match="start > end"):
            DistributorSpec(branch_density=3, generation_band=(3, 2))

    def test_the_script_sets_the_flag_and_the_bound_together(self, tmp_path):
        # StartGeneration without bLimitStartGeneration gates nothing.
        chain = _chain("SK_Fill", density=3, generation_band=(3, None))
        path = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = path.read_text(encoding="utf-8")
        assert "'generation_band': [3, None]" in body
        build = body.split("def build(spec):", 1)[1]
        assert '"limit_start_generation"' in build
        assert 'setp(spacing, "start_generation", int(gen_start))' in build
        assert '"limit_end_generation"' in build


class TestFoliageLayers:
    def test_a_layer_needs_a_real_entry(self):
        with pytest.raises(ValueError, match="real entry"):
            FoliageLayer(
                DistributorSpec(branch_density=1),
                (PaletteEntry(mesh=None, use_as_mask=True),),
            )

    def test_layers_chain_after_the_main_distributor(self, tmp_path):
        # Epic's apex: one part on the leader, density 1 on generation 1..1,
        # chained distributor -> distributor so the export sees the union.
        apex = FoliageLayer(
            DistributorSpec(branch_density=1, generation_band=(1, 1)),
            (PaletteEntry(mesh="/G/big"),),
        )
        chain = TreeChainSpec(
            growth_json=Path("t.json"),
            mesh_name="SK_Apex",
            distributor=DistributorSpec(branch_density=19, generation_band=(2, None)),
            layers=(apex,),
        )
        path = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = path.read_text(encoding="utf-8")
        compile(body, str(path), "exec")
        assert "'layers': [{'palette': [{'mesh': '/G/big'" in body
        assert "'generation_band': [1, 1]" in body
        build = body.split("def build(spec):", 1)[1]
        assert "configure_distributor(layer_settings, layer)" in build
        assert '(last_node, "Out", export_node, "In")' in build
        # 7 edges per chain plus 2 per layer (In from the previous distributor,
        # Foliage from the layer's own palette) is what the edge check expects.
        assert 'expected = 7 * len(spec["chains"]) + 2 * sum(' in build

    def test_a_chain_without_layers_keeps_the_seven_edge_shape(self, tmp_path):
        path = generate_pve_graph_builder_script(tmp_path, [_graph()])
        assert "'layers': []" in path.read_text(encoding="utf-8")


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
        assert "'single_bud_tip': True" in body
        assert "'axil_angle_ramp': '(EditorCurveData=" in body

    def test_the_wind_asset_is_set_checked_and_read_back(self, tmp_path):
        chain = TreeChainSpec(
            growth_json=Path("t.json"),
            mesh_name="SK_Sapling",
            distributor=DistributorSpec(branch_density=3),
            wind_settings=DEFAULT_SAPLING_WIND_SETTINGS,
        )
        path = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = path.read_text(encoding="utf-8")
        assert f"'wind_settings': '{DEFAULT_SAPLING_WIND_SETTINGS}'" in body
        # Preflight refuses before anything is built, and the write is read
        # back: the constructor pre-fills the TREE preset, so a dropped write
        # would otherwise pass for success on every non-sapling chain.
        preflight, build = body.split("def build(spec):", 1)
        assert 'chain["wind_settings"]' in preflight
        assert 'settings.set_editor_property("wind_settings", wind)' in build
        assert 'written.get_editor_property("wind_settings")' in build

    def test_a_masked_chain_gets_its_own_palette_node_and_conditions(self, tmp_path):
        chain = TreeChainSpec(
            growth_json=Path("t.json"),
            mesh_name="SK_Masked",
            distributor=DistributorSpec(
                branch_density=3,
                conditions=ConditionSpec(
                    scale=ConditionInfluence(weight=0.9), minimum_candidates=2
                ),
            ),
            palette=masked_palette(["/G/a", "/G/b"], 1),
        )
        path = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = path.read_text(encoding="utf-8")
        compile(body, str(path), "exec")
        assert "'use_as_mask': True" in body
        assert "'active': {'scale': {'weight': 0.9, 'offset': 0.0}}" in body
        assert "'minimum_candidates': 2" in body
        build = body.split("def build(spec):", 1)[1]
        # The shared palette stays; a chain with masks wires a node of its own.
        assert 'make_palette(graph, chain["palette"]' in build
        assert '(chain_palette, "Out", dist_node, "Foliage")' in build
        assert 'apply_conditions(dist_settings, d["conditions"])' in build
        assert "configure_distributor(dist_settings, chain)" in build

    def test_an_unmasked_chain_carries_no_palette_of_its_own(self, tmp_path):
        path = generate_pve_graph_builder_script(tmp_path, [_graph()])
        body = path.read_text(encoding="utf-8")
        assert "'palette': None" in body
        assert "'conditions': None" in body

    def test_ramp_keys_reach_the_script_in_order(self, tmp_path):
        chain = _chain("SK_x", density=3)
        dist = DistributorSpec(
            branch_density=3,
            aim=FoliageVectorSpec(
                kind="aim", vector1="AXIS_FLATTEN", vector2="AXIS_AIM", dual=True,
                blend_attribute="WORLD_UP_DOT",
                ramp=((0.0, 0.0), (0.9, 0.0), (1.0, 1.0)),
            ),
        )
        chain = TreeChainSpec(chain.growth_json, chain.mesh_name, dist)
        path = generate_pve_graph_builder_script(tmp_path, [_graph(chains=(chain,))])
        body = path.read_text(encoding="utf-8")
        assert "'blend_attribute': 'WORLD_UP_DOT'" in body
        assert (
            "(InterpMode=RCIM_Linear,Time=0.900000,Value=0.000000),"
            "(InterpMode=RCIM_Linear,Time=1.000000,Value=1.000000)"
        ) in body

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
