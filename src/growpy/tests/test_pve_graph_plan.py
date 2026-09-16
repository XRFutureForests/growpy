"""Tests for the PVE graph planning path (XRFF-442).

Covers the join from a finished forest export to runnable graph scripts:
tree-id recovery, triangle-aware splitting, the coverage manifest, and the
retune-in-place script. The recurring theme is refusal -- a density is a
measurement, and a graph built at a guessed one looks entirely normal while
exporting a tree that carries the wrong leaf area.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from growpy.config.pve_calibration import (
    LadderSpec,
    WindPresets,
    load_pve_calibration,
)
from growpy.io.unreal.pve_graph_builder import (
    DEFAULT_SAPLING_WIND_SETTINGS,
    DEFAULT_TREE_WIND_SETTINGS,
    DistributorSpec,
    PVEGraphSpec,
    TreeChainSpec,
    generate_pve_retune_script,
    mask_fraction_of,
    split_by_triangles,
    write_coverage_manifest,
)
from growpy.io.unreal.pve_graph_plan import (
    discover_growth_jsons,
    graded_palette,
    mask_entries_for,
    plan_pve_graphs,
    tree_id_for,
    wind_settings_for,
)

SPECIES_TITLES = {"european_beech": "European_Beech", "silver_fir": "Silver_Fir"}


def _chain(name: str, density: int = 10) -> TreeChainSpec:
    return TreeChainSpec(
        growth_json=Path(f"{name}.json"),
        mesh_name=name,
        distributor=DistributorSpec(branch_density=density),
    )


TRACKED_TOML = Path(__file__).resolve().parents[3] / "config" / "pve_calibration.toml"


@pytest.fixture(autouse=True)
def measured_calibration(tmp_path_factory, monkeypatch):
    """The tracked file with beech and fir building from their MEASURED rows.

    Production switched both to ``build_from = "offline"`` on 2026-09-15
    (every tree solved on the distributor model, rows kept as the record).
    These tests exercise the measured path on stub growth JSONs, which the
    offline solve cannot read, so they run against the measured variant.
    """
    global MEASURED_TOML
    text = TRACKED_TOML.read_text(encoding="utf-8")
    assert text.count('build_from = "offline"') >= 2  # beech, fir (+ a comment)
    measured = tmp_path_factory.mktemp("cal") / "pve_calibration.toml"
    measured.write_text(
        text.replace('build_from = "offline"', 'build_from = "measured"'),
        encoding="utf-8",
    )
    MEASURED_TOML = measured
    monkeypatch.setattr(
        "growpy.config.pve_calibration._default_path", lambda: measured
    )
    return measured


MEASURED_TOML = TRACKED_TOML


@pytest.fixture
def forest_root(tmp_path) -> Path:
    """A synthetic export laid out the way the pipeline lays one out."""
    calibration = load_pve_calibration()
    root = tmp_path / "forest"
    for species, title in SPECIES_TITLES.items():
        for tree_id in sorted(calibration.for_species(species).trees):
            radius, height = tree_id.split("_")
            directory = root / species / radius
            directory.mkdir(parents=True, exist_ok=True)
            name = f"{title}_{radius}_{height}_d20cm_d100_growth_data.json"
            (directory / name).write_text("{}")
    return root


class TestTreeIdRecovery:
    def test_it_reads_the_radius_from_the_directory_and_height_from_the_name(self):
        path = Path(
            "out/european_beech/r05"
            "/European_Beech_r05_h15m_d10cm_d100_growth_data.json"
        )
        assert tree_id_for(path) == "r05_h15m"

    def test_a_file_not_under_a_radius_directory_has_no_id(self):
        # Standalone runs write tree_0001/, which carries no radius.
        path = Path(
            "out/european_beech/tree_0001"
            "/european_beech_h15m_d10cm_growth_data.json"
        )
        assert tree_id_for(path) is None

    def test_a_name_with_no_height_token_has_no_id(self):
        path = Path("out/european_beech/r05/European_Beech_r05_growth_data.json")
        assert tree_id_for(path) is None

    def test_it_returns_none_rather_than_a_best_guess(self):
        # A tree matched to the wrong calibration row builds at the wrong
        # density and looks entirely normal, so there is no safe fallback.
        assert tree_id_for(Path("nonsense.json")) is None


class TestDiscovery:
    def test_it_finds_every_growth_json_keyed_by_species(self, forest_root):
        found = discover_growth_jsons(forest_root)
        assert set(found) == {"european_beech", "silver_fir"}
        assert len(found["european_beech"]) == 15
        assert len(found["silver_fir"]) == 12

    def test_an_absent_root_yields_nothing(self, tmp_path):
        assert discover_growth_jsons(tmp_path / "absent") == {}

    def test_unrelated_json_is_ignored(self, forest_root):
        (forest_root / "european_beech" / "r05" / "notes.json").write_text("{}")
        assert len(discover_growth_jsons(forest_root)["european_beech"]) == 15


class TestWindTier:
    def test_five_metres_and_under_is_a_sapling(self):
        assert wind_settings_for("r08_h05m") == DEFAULT_SAPLING_WIND_SETTINGS
        assert wind_settings_for("r20_h05m") == DEFAULT_SAPLING_WIND_SETTINGS
        assert wind_settings_for("r08_h10m") == DEFAULT_TREE_WIND_SETTINGS
        assert wind_settings_for("r05_h25m") == DEFAULT_TREE_WIND_SETTINGS

    def test_a_species_override_replaces_its_own_tier_only(self):
        # XRFF-235 will give species their own PVWindSettings; the tier split
        # stays, because a 15 m tree on the sapling preset sways from the root.
        presets = WindPresets(tree="/Game/PVE/Wind/WS_Fir")
        assert wind_settings_for("r08_h15m", presets) == "/Game/PVE/Wind/WS_Fir"
        assert wind_settings_for("r08_h05m", presets) == DEFAULT_SAPLING_WIND_SETTINGS

    def test_an_id_without_a_height_is_refused(self):
        # Never a guess: the tree preset on a sapling is the silent default
        # this whole rule exists to replace.
        with pytest.raises(ValueError, match="height token"):
            wind_settings_for("tree_0001")


class TestMaskEntries:
    def test_a_fraction_the_palette_can_spell_is_realised_exactly(self):
        # 8 fir sprays: 3 masks -> 3/11; 1/3 needs 4 masks; 1/9 is one mask.
        assert mask_entries_for(3 / 11, 8) == (1, 3)
        assert mask_entries_for(1 / 3, 8) == (1, 4)
        assert mask_entries_for(1 / 9, 8) == (1, 1)
        assert mask_entries_for(0.0, 8) == (1, 0)

    def test_repeats_unlock_finer_fractions(self):
        # 1/17 = one mask over 16 real entries: every mesh twice.
        assert mask_entries_for(1 / 17, 8) == (2, 1)

    def test_an_unspellable_fraction_is_refused_with_the_nearest_ones(self):
        # Building at the nearest ratio silently would land the count off.
        with pytest.raises(ValueError, match="nearest") as err:
            mask_entries_for(0.3, 8)
        assert "repeats" in str(err.value)
        with pytest.raises(ValueError, match="mask_fraction"):
            mask_entries_for(1.0, 8)

    def test_a_masked_tree_plans_a_palette_of_its_own(self, tmp_path, forest_root):
        # XRFF-462: the calibration's mask_fraction becomes a per-chain palette
        # of the shared meshes plus masks; every other flat chain keeps None
        # (the graded fir r08/r16 chains carry a palette of their own kind).
        toml = (
            MEASURED_TOML
        ).read_text(encoding="utf-8")
        anchor = "history = [[20, 281], [21, 329]]"  # fir r05_h05m's line
        assert toml.count(anchor) == 1
        override = tmp_path / "cal.toml"
        override.write_text(
            toml.replace(
                anchor,
                anchor + "\nbuild_density = 24\nmask_fraction = 0.25",
            ),
            encoding="utf-8",
        )
        plan = plan_pve_graphs(
            tmp_path,
            forest_root,
            content_root="/Game/PVE_Test",
            calibration_path=override,
        )
        chains = {c.mesh_name: c for g in plan.graphs for c in g.chains}
        masked = chains["SK_SilverFir_r05_h05m"]
        assert masked.distributor.branch_density == 24
        assert masked.palette is not None
        assert mask_fraction_of(masked.palette) == pytest.approx(0.25)
        assert len({e.mesh for e in masked.palette if e.mesh}) == 8
        graded = {
            f"SK_SilverFir_{r}_{h}"
            for r in ("r08", "r16")
            for h in ("h05m", "h10m", "h15m")
        }
        assert all(
            c.palette is None
            for n, c in chains.items()
            if n != "SK_SilverFir_r05_h05m" and n not in graded
        )


class TestLadder:
    """XRFF-412: the Scale-graded fir ladder and its apex layer."""

    def test_targets_are_assigned_by_prototype_area_rank(self):
        # The solver writes scale_targets in ascending prototype-area order;
        # the palette lists prototypes alphabetically, so the k-th smallest
        # prototype -- not the k-th listed -- gets the k-th target.
        meshes = ("/G/SM_a", "/G/SM_b", "/G/SM_c")
        areas = (0.03, 0.005, 0.01)
        entries = graded_palette(meshes, areas, (0.1, 0.2, 0.9))
        by_mesh = {e.mesh: e.attributes.scale for e in entries}
        assert by_mesh == {"/G/SM_b": 0.1, "/G/SM_c": 0.2, "/G/SM_a": 0.9}
        assert all(not e.use_as_mask for e in entries)

    def test_a_target_count_that_does_not_match_the_palette_is_refused(self):
        with pytest.raises(ValueError, match="scale_targets has 2"):
            graded_palette(("/G/a", "/G/b", "/G/c"), (1.0, 2.0, 3.0), (0.1, 0.2))
        with pytest.raises(ValueError, match="pair up"):
            graded_palette(("/G/a", "/G/b"), (1.0,), (0.1, 0.2))

    def test_the_shipped_fir_ladder_settings(self):
        cal = load_pve_calibration().for_species("silver_fir")
        assert cal.ladder == LadderSpec(
            scale_weight=1.0,
            minimum_candidates=1,
            cutoff_threshold=0.1,
            apex=True,
            main_generation_start=2,
        )
        assert load_pve_calibration().for_species("european_beech").ladder is None

    def test_a_graded_tree_plans_a_scale_conditioned_palette_and_an_apex_layer(
        self, tmp_path, forest_root
    ):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        assert plan.skipped == ()
        chains = {c.mesh_name: c for g in plan.graphs for c in g.chains}
        chain = chains["SK_SilverFir_r08_h05m"]
        cal = load_pve_calibration().for_species("silver_fir")
        tree = cal.tree("r08_h05m")
        # Main layer: every prototype carries its target, in area order.
        assert chain.palette is not None and len(chain.palette) == 8
        assert sorted(e.attributes.scale for e in chain.palette) == sorted(
            tree.scale_targets
        )
        big = max(chain.palette, key=lambda e: e.attributes.scale)
        assert big.mesh.endswith("SM_pacific_silver_fir_foliage_ZUP")
        active = chain.distributor.conditions.active()
        assert set(active) == {"scale"} and active["scale"].weight == 1.0
        assert chain.distributor.conditions.cutoff_threshold == 0.1
        assert chain.distributor.conditions.minimum_candidates == 1
        assert chain.distributor.generation_band == (2, None)
        assert chain.distributor.branch_density == tree.build_density
        # Apex layer: one largest spray on the leader, ungraded.
        assert len(chain.layers) == 1
        apex = chain.layers[0]
        assert apex.distributor.branch_density == 1
        assert apex.distributor.generation_band == (1, 1)
        assert apex.distributor.conditions is None
        assert apex.distributor.axil_angle == chain.distributor.axil_angle
        assert [e.mesh for e in apex.palette] == [big.mesh]

    def test_a_fir_tree_without_targets_stays_flat(self, tmp_path, forest_root):
        # The legacy radii were solved for a flat palette and still build
        # that way; a species-level ladder must not refuse them.
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        chains = {c.mesh_name: c for g in plan.graphs for c in g.chains}
        legacy = chains["SK_SilverFir_r05_h25m"]
        assert legacy.palette is None
        assert legacy.distributor.conditions is None
        assert legacy.distributor.generation_band is None
        assert legacy.layers == ()

    def test_a_masked_and_graded_tree_is_refused(self, tmp_path, forest_root):
        toml = (
            MEASURED_TOML
        ).read_text(encoding="utf-8")
        anchor = 'growth_json = "Silver_Fir_r08_h05m_d06cm_full_growth_data.json"'
        assert toml.count(anchor) == 1
        override = tmp_path / "cal.toml"
        override.write_text(
            toml.replace(anchor, anchor + "\nmask_fraction = 0.25"), encoding="utf-8"
        )
        plan = plan_pve_graphs(
            tmp_path,
            forest_root,
            content_root="/Game/PVE_Test",
            calibration_path=override,
        )
        assert plan.chain_count == 26
        assert any("r08_h05m" in s and "masked and a graded" in s for s in plan.skipped)


class TestSplitByTriangles:
    def test_it_packs_under_the_cap(self):
        chains = [_chain(f"SK_{i}") for i in range(4)]
        groups = split_by_triangles(chains, lambda _c: 10, 1.0, 25.0)
        assert sum(len(g) for g in groups) == 4
        assert all(len(g) <= 2 for g in groups)

    def test_it_splits_on_triangles_not_on_chain_count(self):
        # A fir instance averages 23,292 triangles against a beech one's
        # 13,456, so equal chain counts pack 1.7x the geometry.
        chains = [_chain("SK_big"), _chain("SK_small")]
        sizes = {"SK_big": 90, "SK_small": 10}
        groups = split_by_triangles(chains, lambda c: sizes[c.mesh_name], 1.0, 100.0)
        assert len(groups) == 1
        groups = split_by_triangles(chains, lambda c: sizes[c.mesh_name], 1.0, 95.0)
        assert len(groups) == 2

    def test_largest_first_so_a_big_tree_does_not_overflow_a_full_bin(self):
        chains = [_chain("SK_a"), _chain("SK_b"), _chain("SK_huge")]
        sizes = {"SK_a": 30, "SK_b": 30, "SK_huge": 60}
        groups = split_by_triangles(chains, lambda c: sizes[c.mesh_name], 1.0, 60.0)
        assert len(groups) == 2
        assert [c.mesh_name for c in groups[0]] == ["SK_huge"]

    def test_an_oversized_chain_gets_its_own_bin_and_a_warning(self, caplog):
        # A chain is one mesh and cannot be split further, so the cap cannot be
        # honoured -- but it must not take other meshes down with it, and the
        # overage must be visible rather than looking packed.
        chains = [_chain("SK_monster"), _chain("SK_ordinary")]
        sizes = {"SK_monster": 500, "SK_ordinary": 10}
        with caplog.at_level("WARNING"):
            groups = split_by_triangles(
                chains, lambda c: sizes[c.mesh_name], 1.0, 100.0
            )
        assert [c.mesh_name for c in groups[0]] == ["SK_monster"]
        assert any("SK_monster" in r.message for r in caplog.records)

    def test_a_nonpositive_cap_is_refused(self):
        with pytest.raises(ValueError, match="cap must be positive"):
            split_by_triangles([_chain("SK_a")], lambda _c: 1, 1.0, 0)

    def test_a_nonpositive_triangle_weight_is_refused(self):
        with pytest.raises(ValueError, match="triangles_per_instance"):
            split_by_triangles([_chain("SK_a")], lambda _c: 1, 0.0, 10.0)

    def test_no_chains_yields_no_graphs(self):
        assert split_by_triangles([], lambda _c: 1, 1.0, 10.0) == []


class TestCoverageManifest:
    def _graph(self) -> PVEGraphSpec:
        return PVEGraphSpec(
            graph_name="PVG_Test",
            chains=(_chain("SK_one", 8), _chain("SK_two", 17)),
            palette_meshes=("/Game/F/SM_a",),
            bark_material="/Game/B/MI_bark",
            export_folder="/Game/Exported",
        )

    def test_it_lists_every_expected_mesh(self, tmp_path):
        path = write_coverage_manifest(tmp_path, [self._graph()])
        data = json.loads(path.read_text())
        assert data["expected_mesh_count"] == 2
        names = [m["mesh_name"] for m in data["graphs"][0]["meshes"]]
        assert names == ["SK_one", "SK_two"]

    def test_it_records_the_density_each_mesh_was_asked_for(self, tmp_path):
        # A mesh that exists is not necessarily a mesh built at the intended
        # density, so consolidation needs both.
        path = write_coverage_manifest(tmp_path, [self._graph()])
        data = json.loads(path.read_text())
        densities = {
            m["mesh_name"]: m["branch_density"] for m in data["graphs"][0]["meshes"]
        }
        assert densities == {"SK_one": 8, "SK_two": 17}

    def test_it_records_where_each_mesh_will_land(self, tmp_path):
        path = write_coverage_manifest(tmp_path, [self._graph()])
        data = json.loads(path.read_text())
        assert data["graphs"][0]["meshes"][0]["asset"] == "/Game/Exported/SK_one"


class TestRetuneScript:
    def _graph(self) -> PVEGraphSpec:
        return PVEGraphSpec(
            graph_name="PVG_Test",
            chains=(_chain("SK_one", 8),),
            palette_meshes=("/Game/F/SM_a",),
            bark_material="/Game/B/MI_bark",
            export_folder="/Game/Exported",
        )

    @pytest.fixture
    def script(self, tmp_path) -> str:
        path = generate_pve_retune_script(tmp_path, [self._graph()])
        return path.read_text(encoding="utf-8")

    def test_it_is_valid_python(self, script):
        ast.parse(script)

    def test_it_never_deletes_or_recreates_a_graph(self, script):
        # delete_asset + create_asset leaves the package pending-kill;
        # get_mutable_pcg_graph() then returns None and the builder's recovery
        # renames the asset under a _b suffix, leaving a superseded graph to be
        # clicked by mistake.
        # Call syntax, not bare names: the script's own docstring explains the
        # trap by naming the two functions.
        assert "delete_asset(" not in script
        assert "create_asset(" not in script
        assert "duplicate_asset(" not in script
        assert "save_asset(" in script

    def test_it_finds_the_export_node_by_mesh_name(self, script):
        assert "PVExportSettings" in script
        assert "SK_one" in script
        # asset_name is the property that does NOT exist -- it was the original
        # bug, and naming it here keeps it from creeping back.
        assert "asset_name" not in script

    def test_it_walks_back_to_the_distributor(self, script):
        assert "PVFoliageDistributorSettings" in script
        assert "input_pins" in script

    def test_it_reads_the_mesh_name_off_the_nested_struct(self, script):
        # PVExportSettings has no mesh_name; it lives on the nested
        # export_settings struct. Reading it off the node raises, which matches
        # zero export nodes and fails every retune. Found in a live editor.
        assert 'get_editor_property("export_settings")' in script
        assert 'get_editor_property("mesh_name")' in script

    def test_it_writes_the_struct_chain_back(self, script):
        # UE Python hands back structs BY VALUE, so setting a field mutates a
        # copy. Without these assignments the density change is silently
        # discarded -- and a read-back against the same copy still reports
        # success, which is the exact failure this project keeps hitting.
        assert 'parametric.set_editor_property("spacing_settings", spacing)' in script
        assert (
            'distributor.set_editor_property("parametric_settings", parametric)'
            in script
        )

    def test_it_verifies_by_rereading_from_the_node(self, script):
        # Not from the local copy that was just written to.
        assert "fresh = (distributor.get_editor_property" in script
        assert "did not take" in script

    def test_it_fails_loudly(self, script):
        assert "raise RuntimeError" in script


class TestPlanEndToEnd:
    def test_it_plans_every_shipped_tree(self, tmp_path, forest_root):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        assert plan.chain_count == 27
        assert plan.skipped == ()
        assert plan.script is not None
        assert plan.manifest is not None
        assert plan.retune_script is not None

    def test_the_densities_are_the_calibrated_ones(self, tmp_path, forest_root):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        built = {
            c.mesh_name: c.distributor.branch_density
            for g in plan.graphs
            for c in g.chains
        }
        assert built["SK_EuropeanBeech_r20_h15m"] == 95
        assert built["SK_SilverFir_r20_h25m"] == 86
        assert built["SK_SilverFir_r05_h25m"] == 158

    def test_each_species_relative_start_travels_with_its_densities(
        self, tmp_path, forest_root
    ):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        starts = {
            c.mesh_name.split("_")[1]: c.distributor.relative_start
            for g in plan.graphs
            for c in g.chains
        }
        assert starts["EuropeanBeech"] == 0.4
        assert starts["SilverFir"] == 0.0

    def test_only_fir_carries_the_bark_aspect_correction(self, tmp_path, forest_root):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        by_species = {g.graph_name.split("_")[1]: g.bark_y_scale for g in plan.graphs}
        assert by_species["SilverFir"] == 0.5
        assert by_species["EuropeanBeech"] is None

    def test_the_measured_twig_pose_travels_with_the_densities(
        self, tmp_path, forest_root
    ):
        # Session 7 (2026-09-14): the pose was measured on probe prisms and
        # judged inside the crown; a plan that dropped it would export sprays
        # standing on their tips again while every density looked right.
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        by_species = {
            c.mesh_name.split("_")[1]: c.distributor
            for g in plan.graphs
            for c in g.chains
        }
        fir, beech = by_species["SilverFir"], by_species["EuropeanBeech"]
        assert (fir.axil_angle, beech.axil_angle) == (30.0, 40.0)
        assert fir.jitter == ()
        assert [(j.mode, j.degrees) for j in beech.jitter] == [
            ("PITCH", 20.0),
            ("ROLL", 12.0),
            ("YAW", 8.0),
        ]
        for spec in (fir, beech):
            assert spec.phyllotaxy_formation == "DISTICHOUS"
            assert spec.reset_phyllotaxy and spec.single_bud_tip
            assert spec.auto_align_end
            assert spec.axil_angle_ramp == (1.0, 1.0)
            assert spec.aim is not None and spec.aim.dual
            assert spec.aim.blend_attribute == "WORLD_UP_DOT"
            assert spec.face is not None and spec.face.affect_tip

    def test_graphs_preserve_area_by_default(self, tmp_path, forest_root):
        # PRESERVE_AREA keeps card foliage; Voxelize (the earlier default) has
        # no voxel-size knob and erased every leaf and needle spray of the
        # 2026-09-16 run. NONE stays available for iterating on densities.
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        assert all(g.nanite_shape_preservation == "PRESERVE_AREA" for g in plan.graphs)

    def test_none_is_still_reachable_for_iteration(self, tmp_path, forest_root):
        plan = plan_pve_graphs(
            tmp_path,
            forest_root,
            content_root="/Game/PVE_Test",
            nanite_shape_preservation="NONE",
        )
        assert all(g.nanite_shape_preservation == "NONE" for g in plan.graphs)

    def test_the_h05_tier_ships_sapling_wind_and_the_rest_tree_wind(
        self, tmp_path, forest_root
    ):
        # XRFF-461 (2026-09-15). The Export node's constructor pre-fills the
        # tree preset on every node, saplings included; the plan is where the
        # tier is known, so the plan is where the split is applied.
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        by_tree = {c.mesh_name: c.wind_settings for g in plan.graphs for c in g.chains}
        assert by_tree["SK_SilverFir_r08_h05m"] == DEFAULT_SAPLING_WIND_SETTINGS
        assert by_tree["SK_EuropeanBeech_r20_h05m"] == DEFAULT_SAPLING_WIND_SETTINGS
        assert by_tree["SK_EuropeanBeech_r08_h10m"] == DEFAULT_TREE_WIND_SETTINGS
        assert by_tree["SK_SilverFir_r20_h25m"] == DEFAULT_TREE_WIND_SETTINGS
        tiers = {name.rsplit("_", 1)[1] for name in by_tree}
        assert tiers == {"h05m", "h10m", "h15m", "h25m"}
        for name, asset in by_tree.items():
            expected = (
                DEFAULT_SAPLING_WIND_SETTINGS
                if name.endswith("_h05m")
                else DEFAULT_TREE_WIND_SETTINGS
            )
            assert asset == expected, name

    def test_the_profile_pin_comes_from_the_calibration(self, tmp_path, forest_root):
        # Half a contract each: the pin and profile_mean must agree, and
        # nothing in the engine checks that they do.
        calibration = load_pve_calibration()
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        assert all(g.profile_pin == calibration.profile_pin for g in plan.graphs)

    def test_an_uncalibrated_species_is_skipped_and_reported(
        self, tmp_path, forest_root
    ):
        # Authoring a chain at a plausible-looking density would export a tree
        # carrying the wrong leaf area, visible only by measuring it.
        directory = forest_root / "wild_cherry" / "r05"
        directory.mkdir(parents=True)
        (directory / "Wild_Cherry_r05_h10m_d10cm_growth_data.json").write_text("{}")

        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        assert plan.chain_count == 27
        assert any("wild_cherry" in line for line in plan.skipped)

    def test_both_halves_land_in_one_place(self, tmp_path, forest_root):
        """The palette import and the graph authoring are two halves of one
        job, so they are emitted together rather than one being a separate CLI
        someone has to know about."""
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        assert plan.asset_script is not None
        assert plan.asset_script.parent == plan.script.parent
        assert plan.asset_script.is_file()

    def test_the_asset_script_covers_only_the_species_the_run_produced(
        self, tmp_path, forest_root
    ):
        # Not every calibrated species -- the palette a graph names is the
        # palette that graph needs.
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        text = plan.asset_script.read_text(encoding="utf-8")
        assert "european_beech" in text
        assert "silver_fir" in text
        assert "wild_cherry" not in text

    def test_the_graph_script_refuses_to_build_without_the_palette(
        self, tmp_path, forest_root
    ):
        # Run order is enforced, not documented: a graph names its palette and
        # bark by Content Browser path, and a half-authored graph left behind
        # after a mid-build failure is an asset to be clicked by mistake.
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        text = plan.script.read_text(encoding="utf-8")
        assert "def preflight()" in text
        assert "growpy_pve_assets.py" in text
        assert text.index("\npreflight()") < text.index("tools.create_asset")

    def test_the_palette_the_graph_names_is_the_palette_the_assets_import(
        self, tmp_path, forest_root
    ):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        graph_text = plan.script.read_text(encoding="utf-8")
        asset_text = plan.asset_script.read_text(encoding="utf-8")
        mesh = (
            "/Game/PVE_Test/EuropeanBeech/Foliage/european_beech_foliage_a"
            "/StaticMeshes/SM_european_beech_foliage_a"
        )
        assert mesh in graph_text
        assert mesh in asset_text

    def test_an_empty_export_authors_nothing(self, tmp_path):
        plan = plan_pve_graphs(tmp_path, tmp_path / "absent")
        assert plan.graphs == ()
        assert plan.script is None
        assert plan.asset_script is None

    def test_the_generated_script_carries_every_mesh(self, tmp_path, forest_root):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        text = plan.script.read_text(encoding="utf-8")
        for graph in plan.graphs:
            for chain in graph.chains:
                assert f"'mesh_name': '{chain.mesh_name}'" in text

    def test_the_manifest_and_the_script_agree(self, tmp_path, forest_root):
        plan = plan_pve_graphs(tmp_path, forest_root, content_root="/Game/PVE_Test")
        data = json.loads(plan.manifest.read_text())
        assert data["expected_mesh_count"] == plan.chain_count


class TestPipelineWiring:
    def test_the_new_route_is_off_by_default(self):
        from growpy.config.core import GrowPyConfig

        assert GrowPyConfig().unreal_generate_pve_graphs is False

    def test_it_is_not_the_deprecated_preset_flag(self):
        # generate_pve_presets drives the Preset Loader node, which UE 5.8
        # deprecated to a no-op; its own note warns against repurposing it.
        from growpy.config.core import GrowPyConfig

        config = GrowPyConfig()
        assert config.unreal_generate_pve_presets is not (
            config.unreal_generate_pve_graphs
        )

    def test_the_flag_reads_from_toml(self, tmp_path):
        from growpy.config.core import GrowPyConfig

        toml = tmp_path / "growpy.toml"
        toml.write_bytes(
            b"[unreal]\ngenerate_pve_graphs = true\npve_triangle_cap = 2.5e8\n"
        )
        config = GrowPyConfig.from_toml(toml, set_as_global=False)
        assert config.unreal_generate_pve_graphs is True
        assert config.unreal_pve_triangle_cap == 2.5e8

    def test_a_nonpositive_cap_is_refused(self, tmp_path):
        from growpy.config.core import GrowPyConfig

        toml = tmp_path / "growpy.toml"
        toml.write_bytes(b"[unreal]\npve_triangle_cap = 0\n")
        with pytest.raises(ValueError, match="pve_triangle_cap"):
            GrowPyConfig.from_toml(toml, set_as_global=False)

    def test_script_generation_calls_the_new_planner(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "io/unreal/script_generation.py"
        ).read_text(encoding="utf-8")
        assert "plan_pve_graphs" in source
        assert "unreal_generate_pve_graphs" in source
