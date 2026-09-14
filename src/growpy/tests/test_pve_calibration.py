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
    PVECalibration,
    SpeciesCalibration,
    TreeCalibration,
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

# What was exported on 2026-09-11 and verified against Forrester. Restated here
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
        "r05_h05m": 20,
        "r05_h25m": 158,
        "r10_h05m": 19,
        "r10_h25m": 133,
        "r20_h05m": 20,
        "r20_h25m": 86,
    },
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
        assert sum(len(s.trees) for s in shipped.species.values()) == 15

    @pytest.mark.parametrize("species", sorted(SHIPPED_DENSITIES))
    def test_build_densities_are_the_shipped_ones(self, shipped, species):
        cal = shipped.for_species(species)
        resolved = {t: cal.resolve_density(t).density for t in cal.trees}
        assert resolved == SHIPPED_DENSITIES[species]

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
        assert {cal.resolve_density(t).source for t in cal.trees} == {"offline"}

    def test_fir_builds_from_its_measurements(self, shipped):
        cal = shipped.for_species("silver_fir")
        sources = {t: cal.resolve_density(t).source for t in cal.trees}
        # Only r20_h25m was finished offline; the rest are exported measurements.
        assert sources["r20_h25m"] == "offline"
        assert set(sources.values()) == {"measured", "offline"}
        assert sum(1 for s in sources.values() if s == "measured") == 5

    def test_aggregate_leaf_area_is_what_shipped(self, shipped):
        total = sum(
            cal.leaf_area_m2(tree_id)
            for cal in shipped.species.values()
            for tree_id in cal.trees
        )
        assert total == pytest.approx(815.4, abs=0.5)

    def test_the_fir_h05_trees_ship_well_under_target(self, shipped):
        # The aggregate hides them: two large fir trees over by +2.4 % and
        # +3.1 % roughly cancel three small ones short by 13-33 %. They sit near
        # the distributor's one-sample-per-branch floor, where the response to
        # density is a staircase. This pins the shortfall so it stays visible.
        def delta(species: str, tree_id: str) -> float:
            cal = shipped.for_species(species)
            placed = cal.resolve_density(tree_id).instances
            return placed / cal.tree(tree_id).target_instances - 1.0

        short = {
            t: delta("silver_fir", t) for t in ("r05_h05m", "r10_h05m", "r20_h05m")
        }
        assert all(d < -0.10 for d in short.values()), short

        on_target = [
            delta(species, tree_id)
            for species in sorted(shipped.species)
            for tree_id in sorted(shipped.for_species(species).trees)
            if not (species == "silver_fir" and tree_id.endswith("h05m"))
        ]
        assert len(on_target) == 12
        assert all(-0.021 <= d <= 0.032 for d in on_target), on_target

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

    def test_profile_pin_is_the_one_the_builder_defaults_to(self, shipped):
        assert PVEGraphSpec.profile_pin == shipped.profile_pin

    def test_only_fir_corrects_bark_aspect(self, shipped):
        assert shipped.for_species("silver_fir").bark_y_scale == 0.5
        assert shipped.for_species("european_beech").bark_y_scale is None


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

    def test_a_file_without_the_section_is_refused(self, tmp_path):
        path = tmp_path / "pve_calibration.toml"
        path.write_text("[something_else]\nx = 1\n")
        with pytest.raises(ValueError, match=r"\[pve_calibration\]"):
            load_pve_calibration(path)

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_pve_calibration(tmp_path / "absent.toml")


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
