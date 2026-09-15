"""Tests for growpy.config.pve_calibration and the tracked calibration file.

Half of these guard the *data* rather than the code: the fifteen densities in
``config/pve_calibration.toml`` each cost an Export click in the live editor, so
a silent edit to them is the expensive failure this file exists to catch.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from growpy.config.pve_calibration import (
    LadderSpec,
    PVECalibration,
    SpeciesCalibration,
    TreeCalibration,
    TwigJitter,
    TwigPose,
    WindPresets,
    load_pve_calibration,
)
from growpy.io.unreal.pve_graph_builder import (
    DistributorSpec,
    FoliageVectorSpec,
    PVEGraphSpec,
    TreeChainSpec,
    generate_pve_graph_builder_script,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
CALIBRATION_TOML = CONFIG_DIR / "pve_calibration.toml"

# What was exported on 2026-09-11 and verified against Forrester, with the three
# fir h05 trees re-solved one density step up and re-measured on 2026-09-15
# (XRFF-462: 20/19/20 -> 21/22/23). Restated here
# rather than read from the file so an edit to either has to be deliberate.
SHIPPED_DENSITIES = {
    "european_beech": {
        "r05_h05m": 8,
        "r05_h10m": 17,
        "r05_h15m": 40,
        "r10_h05m": 10,
        "r10_h10m": 29,
        "r10_h15m": 66,
        "r20_h05m": 12,
        "r20_h10m": 39,
        "r20_h15m": 95,
    },
    "silver_fir": {
        "r05_h05m": 21,
        "r05_h25m": 158,
        "r10_h05m": 22,
        "r10_h25m": 133,
        "r20_h05m": 23,
        "r20_h25m": 86,
    },
}

# The r08/r16 trees, solved OFFLINE with the validated distributor model
# against Forrester and not yet measured by an Export click. Beech: the
# 2026-09-14 run. Fir: the run as REGENERATED 2026-09-15 by the surround
# sweep, solved for the Scale-graded ladder (XRFF-412: main layer gen >= 2
# plus one apex spray, so build_instances = main + 1).
OFFLINE_R08_R16_DENSITIES = {
    "european_beech": {
        "r08_h05m": 10,
        "r08_h10m": 24,
        "r08_h15m": 59,
        "r16_h05m": 11,
        "r16_h10m": 36,
        "r16_h15m": 96,
    },
    "silver_fir": {
        "r08_h05m": 19,
        "r08_h10m": 30,
        "r08_h15m": 47,
        "r16_h05m": 20,
        "r16_h10m": 29,
        "r16_h15m": 46,
    },
}

# What the ladder solve of 2026-09-15 placed on the six fir trees: (main
# instances + 1 apex, expected leaf area per instance under the grading).
FIR_LADDER_BUILDS = {
    "r08_h05m": (270, 0.01944615),
    "r08_h10m": (552, 0.01978260),
    "r08_h15m": (1520, 0.02000940),
    "r16_h05m": (435, 0.02005515),
    "r16_h10m": (837, 0.01923569),
    "r16_h15m": (1908, 0.02047263),
}


@pytest.fixture(scope="module")
def shipped() -> PVECalibration:
    return load_pve_calibration(CALIBRATION_TOML)


def _tree(**kwargs) -> TreeCalibration:
    defaults = {
        "tree_id": "r05_h05m",
        "growth_json": "beech_r05_h05m_f006.json",
        "fraction": 0.06,
        "branches": 321,
        "points": 4093,
        "target_m2": 6.32,
        "target_instances": 399,
        "history": ((17, 394),),
        "history_relative_start": 0.0,
    }
    defaults.update(kwargs)
    return TreeCalibration(**defaults)


def _species(**kwargs) -> SpeciesCalibration:
    defaults = {
        "species": "test_species",
        "relative_start": 0.0,
        "fraction": 0.06,
        "prototype_leaf_area_m2": 0.0158,
        "palette_flat_mean_triangles": 13456.4,
        "history_relative_start": 0.0,
        "trees": {"r05_h05m": _tree()},
    }
    defaults.update(kwargs)
    return SpeciesCalibration(**defaults)


class TestShippedCalibration:
    def test_the_file_is_tracked_and_loads(self, shipped):
        assert CALIBRATION_TOML.is_file()
        assert set(shipped.species) == {"european_beech", "silver_fir"}
        assert sum(len(s.trees) for s in shipped.species.values()) == 27

    @pytest.mark.parametrize("species", sorted(SHIPPED_DENSITIES))
    def test_build_densities_are_the_shipped_ones(self, shipped, species):
        cal = shipped.for_species(species)
        resolved = {t: cal.resolve_density(t).density for t in cal.trees}
        assert resolved == {
            **SHIPPED_DENSITIES[species],
            **OFFLINE_R08_R16_DENSITIES[species],
        }

    def test_beech_runs_on_the_outer_span_and_fir_does_not(self, shipped):
        # Beech adopted relative_start 0.4 to keep leaves off primary limbs;
        # fir could not, because its branch count already exceeds its target.
        assert shipped.for_species("european_beech").relative_start == 0.4
        assert shipped.for_species("silver_fir").relative_start == 0.0

    def test_beech_densities_were_re_solved_not_reused(self, shipped):
        # Its history is at relative_start 0.0 and the species builds at 0.4,
        # so every beech tree must carry an explicit build_density.
        cal = shipped.for_species("european_beech")
        assert cal.history_relative_start == 0.0
        assert all(t.build_density is not None for t in cal.trees.values())
        sources = {t: cal.resolve_density(t).source for t in cal.trees}
        assert {sources[t] for t in SHIPPED_DENSITIES["european_beech"]} == {"offline"}
        # The r08/r16 set was solved offline too, but its one-pair history IS
        # the 0.4 export, so it builds from a measurement.
        assert {sources[t] for t in OFFLINE_R08_R16_DENSITIES["european_beech"]} == {
            "measured"
        }

    def test_fir_builds_from_its_measurements(self, shipped):
        cal = shipped.for_species("silver_fir")
        sources = {t: cal.resolve_density(t).source for t in cal.trees}
        # Five shipped on 2026-09-11 are exported measurements; r20_h25m was
        # finished offline. Of the six r08/r16 ladder trees (solved on the
        # regenerated run -- their 2026-09-14 clicks measured trees that no
        # longer exist) two were clicked on PVG_Ladder_Probe and landed exact.
        assert sources["r20_h25m"] == "offline"
        assert set(sources.values()) == {"measured", "offline"}
        assert sum(1 for s in sources.values() if s == "measured") == 7
        clicked = {"r08_h05m": ((19, 270),), "r08_h15m": ((47, 1520),)}
        for tree_id in OFFLINE_R08_R16_DENSITIES["silver_fir"]:
            tree = cal.tree(tree_id)
            if tree_id in clicked:
                assert sources[tree_id] == "measured", tree_id
                assert tree.history == clicked[tree_id], tree_id
                assert tree.build_instances == tree.history[-1][1], tree_id
            else:
                assert sources[tree_id] == "offline", tree_id
                assert tree.history == (), tree_id

    def test_aggregate_leaf_area_is_what_shipped(self, shipped):
        total = sum(
            cal.leaf_area_m2(tree_id)
            for species, cal in shipped.species.items()
            for tree_id in SHIPPED_DENSITIES[species]
        )
        # 815.4 m2 as shipped on 2026-09-11; +7.6 m2 from the three fir h05
        # re-solves of 2026-09-15 (+48, +157, +171 instances at 0.0201 m2).
        assert total == pytest.approx(823.0, abs=0.5)

    def test_the_offline_r08_r16_set_lands_on_its_targets(self, shipped):
        # Solved, not measured: the model that solved them reproduces 13 of 14
        # logged exports exactly, so the aggregate should sit on Forrester
        # until a click says otherwise. Beech 302.5 m2 against 302.0; fir
        # (ladder, per-instance areas) 110.5 against 111.9.
        placed = target = 0.0
        for species, cal in shipped.species.items():
            for tree_id in OFFLINE_R08_R16_DENSITIES[species]:
                placed += cal.leaf_area_m2(tree_id)
                target += cal.tree(tree_id).target_m2
        assert placed / target == pytest.approx(1.0, abs=0.005)

    def test_the_fir_ladder_rows_are_the_solved_ones(self, shipped):
        # XRFF-412 (2026-09-15). Eight targets per tree in ascending
        # prototype-area order, at the tree's own placement-radius quantiles;
        # the per-instance area replaces the species' flat mean in
        # leaf_area_m2(). Restated so an edit has to be deliberate.
        cal = shipped.for_species("silver_fir")
        for tree_id, (instances, per_instance) in FIR_LADDER_BUILDS.items():
            tree = cal.tree(tree_id)
            assert tree.build_instances == instances, tree_id
            assert tree.instance_leaf_area_m2 == pytest.approx(per_instance), tree_id
            assert tree.scale_targets is not None and len(tree.scale_targets) == 8
            assert list(tree.scale_targets) == sorted(tree.scale_targets)
            assert 0.0 < tree.scale_targets[0] < tree.scale_targets[-1] < 0.1
            assert cal.leaf_area_m2(tree_id) == pytest.approx(instances * per_instance)
            assert tree.growth_json.endswith("_full_growth_data.json")
        # The legacy fir radii stay flat and use the species mean.
        for tree_id in SHIPPED_DENSITIES["silver_fir"]:
            assert cal.tree(tree_id).scale_targets is None, tree_id
            assert cal.tree(tree_id).instance_leaf_area_m2 is None, tree_id

    def test_every_shipped_tree_is_within_five_percent_of_target(self, shipped):
        # Until 2026-09-15 the aggregate hid three fir h05 trees short by
        # 13-33 %: one density step short on the distributor's staircase, where
        # a branch whose loop count is 1 contributes nothing at relative_start
        # 0.0. XRFF-462 re-solved them on the validated model and the click
        # landed exactly (329 / 463 / 560). This pins every tree inside +-5 %.
        def delta(species: str, tree_id: str) -> float:
            cal = shipped.for_species(species)
            placed = cal.resolve_density(tree_id).instances
            return placed / cal.tree(tree_id).target_instances - 1.0

        fir_h05 = {
            t: delta("silver_fir", t) for t in ("r05_h05m", "r10_h05m", "r20_h05m")
        }
        assert fir_h05 == pytest.approx(
            {"r05_h05m": 0.0123, "r10_h05m": 0.0221, "r20_h05m": -0.0278}, abs=0.0005
        )

        on_target = [
            delta(species, tree_id)
            for species in sorted(shipped.species)
            for tree_id in sorted(SHIPPED_DENSITIES[species])
        ]
        assert len(on_target) == 15
        assert all(-0.03 <= d <= 0.032 for d in on_target), on_target

        # The offline r08/r16 set is finer: the worst is fir r16_h05m at
        # -3.5 %, again the staircase near the floor.
        offline = [
            delta(species, tree_id)
            for species in sorted(shipped.species)
            for tree_id in sorted(OFFLINE_R08_R16_DENSITIES[species])
        ]
        assert len(offline) == 12
        assert all(-0.04 <= d <= 0.03 for d in offline), offline

    def test_every_tree_records_the_instances_its_density_places(self, shipped):
        for cal in shipped.species.values():
            for tree_id in cal.trees:
                assert cal.resolve_density(tree_id).instances is not None

    def test_the_two_species_spell_the_same_fraction_differently(self, shipped):
        # The reason filenames are recorded rather than derived.
        beech = shipped.for_species("european_beech").tree("r05_h05m")
        fir = shipped.for_species("silver_fir").tree("r05_h05m")
        assert beech.fraction == fir.fraction == 0.06
        assert "_f006" in beech.growth_json
        assert "_f060" in fir.growth_json

    def test_profile_mean_agrees_with_unreal_toml(self, shipped):
        # Half a contract each: a graph meshed on a profile whose mean differs
        # from the one growpy divided radii by produces plausible-looking
        # trunks of the wrong diameter, and nothing in the engine notices.
        with open(CONFIG_DIR / "unreal.toml", "rb") as handle:
            unreal = tomllib.load(handle)
        declared = unreal["unreal"]["growth_data_json"]["profile_mean"]
        assert shipped.profile_mean == declared

    def test_loading_the_config_dir_does_not_warn_about_this_section(self, caplog):
        # It is read by name rather than through the merge, so GrowPyConfig
        # does not own it -- but it is still a legitimate section, and being
        # reported as a probable typo on every run is noise. Seen in a live UE
        # run on 2026-09-14.
        import logging

        from growpy.config.core import GrowPyConfig

        with caplog.at_level(logging.WARNING):
            GrowPyConfig.from_toml(CONFIG_DIR, set_as_global=False)
        assert not [
            r for r in caplog.records if "pve_calibration" in r.message
        ], "the tracked calibration section is reported as a typo"

    def test_profile_pin_is_the_one_the_builder_defaults_to(self, shipped):
        assert PVEGraphSpec.profile_pin == shipped.profile_pin

    def test_only_fir_corrects_bark_aspect(self, shipped):
        assert shipped.for_species("silver_fir").bark_y_scale == 0.5
        assert shipped.for_species("european_beech").bark_y_scale is None

    def test_the_measured_twig_pose_ships(self, shipped):
        # Session 7 (2026-09-14): axil 30/40 measured on probe prisms, beech
        # jitter judged in the crown. Restated so an edit has to be deliberate.
        fir = shipped.for_species("silver_fir").pose
        beech = shipped.for_species("european_beech").pose
        assert (fir.reset_phyllotaxy, fir.axil_angle, fir.jitter) == (True, 30.0, ())
        assert (beech.reset_phyllotaxy, beech.axil_angle) == (True, 40.0)
        assert [(j.mode, j.degrees, j.seed) for j in beech.jitter] == [
            ("PITCH", 20.0, 11),
            ("ROLL", 12.0, 12),
            ("YAW", 8.0, 13),
        ]

    def test_a_species_without_a_pose_section_gets_the_default(self):
        assert _species().pose == TwigPose()

    def test_only_fir_ships_a_ladder(self, shipped):
        assert shipped.for_species("silver_fir").ladder == LadderSpec(
            scale_weight=1.0,
            minimum_candidates=1,
            cutoff_threshold=0.1,
            apex=True,
            main_generation_start=2,
        )
        assert shipped.for_species("european_beech").ladder is None
        assert _species().ladder is None


class TestDensityResolution:
    def test_solved_density_is_never_built_from(self):
        # It is the solver's recommendation and is not guaranteed to be on the
        # same growth JSON as the history; a stale one landed +47 % out.
        tree = _tree(history=((17, 394),), solved_density=99)
        assert tree.resolve_density(0.0).density == 17

    def test_build_density_wins_over_history(self):
        tree = _tree(history=((17, 394),), build_density=8, build_instances=391)
        resolved = tree.resolve_density(0.4)
        assert resolved.density == 8
        assert resolved.instances == 391

    def test_history_measured_at_another_relative_start_is_refused(self):
        # A non-zero relative_start keeps the branch-root sample 0.0 discards,
        # so it adds one instance per branch and the densities differ.
        tree = _tree(history=((17, 394),), history_relative_start=0.0)
        with pytest.raises(ValueError, match="interchangeable"):
            tree.resolve_density(0.4)

    def test_a_tree_with_neither_is_refused(self):
        tree = _tree(history=(), solved_density=17)
        with pytest.raises(ValueError, match="nothing to build it from"):
            tree.resolve_density(0.0)

    def test_the_last_history_pair_is_the_one_used(self):
        tree = _tree(history=((16, 357), (20, 523), (17, 394)))
        assert tree.resolve_density(0.0).density == 17

    def test_resolved_density_converts_to_int(self):
        assert int(_tree().resolve_density(0.0)) == 17


class TestGrowthJsonResolution:
    def test_resolves_the_recorded_name_under_a_caller_root(self, tmp_path):
        (tmp_path / "beech_r05_h05m_f006.json").write_text("{}")
        cal = _species()
        assert cal.resolve_growth_json(tmp_path, "r05_h05m").name == (
            "beech_r05_h05m_f006.json"
        )

    def test_a_missing_file_raises_rather_than_silently_globbing(self, tmp_path):
        # A glob on the tree id alone matches four files for fir r05_h05m.
        (tmp_path / "beech_r05_h05m_f060.json").write_text("{}")
        with pytest.raises(FileNotFoundError, match="r05_h05m"):
            _species().resolve_growth_json(tmp_path, "r05_h05m")

    def test_an_unknown_tree_lists_the_known_ones(self):
        with pytest.raises(KeyError, match="r05_h05m"):
            _species().tree("r99_h99m")


class TestValidation:
    def test_a_future_schema_version_is_refused(self):
        with pytest.raises(ValueError, match="schema_version"):
            PVECalibration(
                schema_version=99,
                profile_mean=0.8215,
                profile_pin="plantProfile_8",
                species={},
            )

    def test_an_unknown_build_source_is_refused(self):
        with pytest.raises(ValueError, match="build_density_source"):
            _tree(build_density=8, build_density_source="guessed")

    def test_a_species_with_no_trees_is_refused(self):
        with pytest.raises(ValueError, match="no calibrated trees"):
            _species(trees={})

    def test_a_tree_with_no_growth_json_is_refused(self):
        with pytest.raises(ValueError, match="names no growth JSON"):
            _tree(growth_json="")

    def test_a_masked_tree_needs_its_own_build_density(self):
        # A history pair is an unmasked measurement; masking changes the
        # spawned count, so it cannot stand in for a masked build.
        with pytest.raises(ValueError, match="mask_fraction"):
            _tree(mask_fraction=0.25)
        masked = _tree(mask_fraction=0.25, build_density=24, build_instances=318)
        assert masked.resolve_density(0.0).instances == 318
        with pytest.raises(ValueError, match="mask_fraction"):
            _tree(mask_fraction=1.0, build_density=24)
        assert _tree().mask_fraction == 0.0

    def test_a_graded_tree_needs_its_own_build_density(self):
        # A graded palette changes the area per instance, so a history pair
        # solved for the flat palette cannot stand in for it.
        with pytest.raises(ValueError, match="scale_targets"):
            _tree(scale_targets=(0.1, 0.5))
        with pytest.raises(ValueError, match="scale_targets"):
            _tree(scale_targets=(0.1, 1.5), build_density=20, build_instances=300)
        with pytest.raises(ValueError, match="instance_leaf_area_m2"):
            _tree(instance_leaf_area_m2=0.0)
        graded = _tree(
            scale_targets=(0.1, 0.5),
            build_density=20,
            build_instances=300,
            instance_leaf_area_m2=0.02,
        )
        assert graded.resolve_density(0.0).instances == 300
        assert _species(trees={"r05_h05m": graded}).leaf_area_m2(
            "r05_h05m"
        ) == pytest.approx(6.0)

    def test_ladder_settings_are_bounded(self):
        with pytest.raises(ValueError, match="scale_weight"):
            LadderSpec(scale_weight=0.0)
        with pytest.raises(ValueError, match="minimum_candidates"):
            LadderSpec(minimum_candidates=0)
        with pytest.raises(ValueError, match="cutoff_threshold"):
            LadderSpec(cutoff_threshold=1.5)
        with pytest.raises(ValueError, match="1-based"):
            LadderSpec(main_generation_start=0)

    def test_an_unknown_jitter_mode_is_refused(self):
        with pytest.raises(ValueError, match="mode"):
            TwigJitter(mode="TILT", degrees=5.0)

    def test_a_jitter_outside_the_half_turn_is_refused(self):
        with pytest.raises(ValueError, match="degrees"):
            TwigJitter(mode="ROLL", degrees=0.0)
        with pytest.raises(ValueError, match="degrees"):
            TwigJitter(mode="ROLL", degrees=181.0)

    def test_a_file_without_the_section_is_refused(self, tmp_path):
        path = tmp_path / "pve_calibration.toml"
        path.write_text("[something_else]\nx = 1\n")
        with pytest.raises(ValueError, match=r"\[pve_calibration\]"):
            load_pve_calibration(path)

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_pve_calibration(tmp_path / "absent.toml")


class TestWindPresets:
    def test_a_species_without_a_wind_section_defers_to_the_plugin_presets(self):
        # None per tier: the plan supplies DefaultSapling/DefaultTreeWindSettings.
        assert _species().wind == WindPresets()
        assert _species().wind.tree is None and _species().wind.sapling is None

    def test_no_shipped_species_overrides_the_plugin_presets_yet(self, shipped):
        # XRFF-235 is where a per-species asset would land. Until then a wind
        # block in the tracked file would be a silent change to every export.
        for species in shipped.species.values():
            assert species.wind == WindPresets(), species.species

    def test_an_override_is_read_per_tier(self, tmp_path):
        path = tmp_path / "pve_calibration.toml"
        path.write_text(
            CALIBRATION_TOML.read_text(encoding="utf-8")
            + "\n[pve_calibration.species.silver_fir.wind]\n"
            + 'tree = "/Game/PVE/Wind/WS_Fir"\n',
            encoding="utf-8",
        )
        wind = load_pve_calibration(path).for_species("silver_fir").wind
        assert wind == WindPresets(tree="/Game/PVE/Wind/WS_Fir", sapling=None)

    def test_a_bare_asset_name_is_refused(self):
        # The builder loads it by package path; a bare name resolves to nothing
        # and the preflight would fail a whole run over a typo here.
        with pytest.raises(ValueError, match="package path"):
            WindPresets(sapling="WS_Sapling")


class TestRoundTripToGeneratedScript:
    """config -> graph spec -> generated UE script, densities intact."""

    def _graphs(self, shipped, tmp_path) -> list[PVEGraphSpec]:
        graphs = []
        for species, prefix in (("european_beech", "Beech"), ("silver_fir", "Fir")):
            cal = shipped.for_species(species)
            chains = tuple(
                TreeChainSpec(
                    growth_json=tmp_path / cal.tree(tree_id).growth_json,
                    mesh_name=f"SK_Ship_{prefix}_{tree_id}",
                    distributor=DistributorSpec(
                        branch_density=cal.resolve_density(tree_id).density,
                        relative_start=cal.relative_start,
                        phyllotaxy_formation=cal.phyllotaxy_formation,
                        scale_ramp=(1.0, 1.0),
                        face=FoliageVectorSpec(kind="face", vector2="AXIS_AIM"),
                        auto_align_end=False,
                    ),
                )
                for tree_id in sorted(cal.trees)
            )
            graphs.append(
                PVEGraphSpec(
                    graph_name=f"PVG_{prefix}_Ship",
                    chains=chains,
                    palette_meshes=("/Game/Foliage/SM_twig_a",),
                    bark_material=f"/Game/Bark/MI_{species}_bark",
                    bark_y_scale=cal.bark_y_scale,
                    export_folder=f"/Game/Exported/{prefix}",
                )
            )
        return graphs

    def test_every_shipped_density_reaches_the_generated_script(
        self, shipped, tmp_path
    ):
        script = generate_pve_graph_builder_script(
            tmp_path, self._graphs(shipped, tmp_path)
        )
        text = script.read_text(encoding="utf-8")
        for species, prefix in (("european_beech", "Beech"), ("silver_fir", "Fir")):
            for tree_id, density in SHIPPED_DENSITIES[species].items():
                mesh = f"SK_Ship_{prefix}_{tree_id}"
                chunk = text.split(f"'mesh_name': '{mesh}'", 1)[1][:400]
                assert f"'branch_density': {density}" in chunk, mesh

    def test_the_relative_start_travels_with_the_densities(self, shipped, tmp_path):
        script = generate_pve_graph_builder_script(
            tmp_path, self._graphs(shipped, tmp_path)
        )
        text = script.read_text(encoding="utf-8")
        beech = text.split("PVG_Beech_Ship", 1)[1].split("PVG_Fir_Ship", 1)[0]
        assert "'relative_start': 0.4" in beech
        assert "'relative_start': 0.0" not in beech

    def test_the_fir_bark_aspect_correction_survives(self, shipped, tmp_path):
        script = generate_pve_graph_builder_script(
            tmp_path, self._graphs(shipped, tmp_path)
        )
        text = script.read_text(encoding="utf-8")
        fir = text.split("PVG_Fir_Ship", 1)[1]
        assert "'bark_y_scale': 0.5" in fir
