"""Tests for growpy.io.unreal.pve_asset_script (XRFF-440).

The interesting assertions are about refusals. This step exists because an
unowned manual step rotted: a bark material stayed a USD import stub for weeks
and every beech trunk on the PVE route rendered untextured. So the tests pin the
guards -- the forbidden master, the empty palette, the missing texture, the
texture-before-material ordering -- rather than just the happy path.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from growpy.io.unreal.pve_asset_script import (
    DEFAULT_MASTER_MATERIAL,
    FOLIAGE_SAMPLES,
    PalettePrototype,
    PVEAssetPlan,
    SpeciesAssetSpec,
    build_species_asset_spec,
    generate_pve_asset_script,
)


def _spec(**overrides) -> SpeciesAssetSpec:
    defaults = {
        "species": "european_beech",
        "content_folder": "/Game/PVE/EuropeanBeech",
        "prototypes": (
            PalettePrototype("european_beech_foliage_a", Path("a_static.usda")),
            PalettePrototype("european_beech_foliage_b", Path("b_static.usda")),
        ),
        "bark_color": Path("beech_60_bark.jpg"),
        "bark_normal": Path("beech_60_bark_normal.jpg"),
    }
    defaults.update(overrides)
    return SpeciesAssetSpec(**defaults)


def _plan(**overrides) -> PVEAssetPlan:
    defaults = {"species": (_spec(),)}
    defaults.update(overrides)
    return PVEAssetPlan(**defaults)


class TestSpecResolution:
    """Resolution from the real asset tree -- counts are discovered, not typed."""

    @pytest.mark.parametrize(
        "species,expected", [("european_beech", 5), ("silver_fir", 9)]
    )
    def test_prototype_counts_come_from_disk(self, species, expected):
        spec = build_species_asset_spec(species)
        assert len(spec.prototypes) == expected

    def test_species_sharing_a_twig_resolve_to_the_same_files(self):
        # Silver fir's twig is the Pacific silver fir's, via tree_asset_lookup.
        spec = build_species_asset_spec("silver_fir")
        assert all(p.name.startswith("pacific_silver_fir") for p in spec.prototypes)

    def test_bark_textures_resolve_to_real_files(self):
        spec = build_species_asset_spec("european_beech")
        assert spec.bark_color.is_file()
        assert spec.bark_normal.is_file()
        assert spec.bark_normal.stem.endswith("_normal")

    def test_a_species_with_no_twigs_is_refused(self):
        with pytest.raises(FileNotFoundError, match="convert-twigs"):
            build_species_asset_spec("avocado")

    def test_it_works_for_a_species_never_imported_into_ue(self):
        # Acceptance: not beech/fir-specific. Norway spruce shares the fir's
        # twig and has never had PVE assets built.
        spec = build_species_asset_spec("norway_spruce")
        assert len(spec.prototypes) == 9
        assert spec.bark_material.endswith("/MI_norway_spruce_bark")

    def test_a_missing_normal_map_is_named_not_silently_skipped(self, monkeypatch):
        # A material with either map unset renders wrong, so this refuses
        # rather than building three-quarters of a trunk material.
        monkeypatch.setattr(
            "growpy.config.paths.get_bark_normal_texture_path", lambda _s: None
        )
        with pytest.raises(FileNotFoundError, match="bark normal"):
            build_species_asset_spec("european_beech")

    def test_every_dataset_species_resolves(self):
        # Silver birch used to fail here: the Grove spells its normal map
        # Birch70_normal.jpg while every other species spells it
        # <Stem>Normal.jpg, and the copy step probed only the one spelling.
        import csv

        lookup = Path(__file__).resolve().parents[3] / "config/tree_asset_lookup.csv"
        with open(lookup, newline="", encoding="utf-8") as handle:
            names = [
                row["Standardized Name"].strip()
                for row in csv.DictReader(handle)
                if row.get("Dataset", "").strip().lower() == "yes"
            ]
        assert names, "no dataset species in the lookup table"
        for name in names:
            build_species_asset_spec(name)

    def test_folder_name_can_be_overridden(self):
        spec = build_species_asset_spec("european_beech", folder_name="Beech")
        assert spec.content_folder == "/Game/Assets/Trees/Foliage/Beech"
        assert spec.materials_folder == "/Game/Assets/Trees/Materials/Beech"

    def test_the_palette_and_the_materials_are_sorted_by_type(self):
        spec = build_species_asset_spec("european_beech")
        assert spec.foliage_folder == "/Game/Assets/Trees/Foliage/european_beech"
        assert spec.bark_folder == "/Game/Assets/Trees/Materials/european_beech"

    def test_content_root_can_be_overridden(self):
        spec = build_species_asset_spec("silver_fir", content_root="/Game/PVE_Test")
        assert spec.content_folder.startswith("/Game/PVE_Test/")

    def test_foliage_maps_resolve_to_the_packed_files(self):
        # The leaves' material needs the two maps growpy-pack-pve-textures
        # writes; without them season and health never reach a leaf.
        spec = build_species_asset_spec("silver_fir")
        assert spec.foliage_color.name == "pacific_silver_fir_twig_pve_basecolor.png"
        assert spec.foliage_normal.name == "pacific_silver_fir_twig_pve_normal.png"
        assert spec.foliage_color.is_file() and spec.foliage_normal.is_file()

    @pytest.mark.parametrize(
        "species,habit",
        [
            ("silver_fir", "conifer"),
            ("scots_pine", "conifer"),
            ("european_beech", "broadleaf"),
            ("common_ash", "broadleaf"),
        ],
    )
    def test_the_growth_habit_picks_the_foliage_sample(self, species, habit):
        assert build_species_asset_spec(species).habit == habit

    def test_missing_foliage_maps_are_named_not_silently_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "pathlib.Path.is_file",
            lambda p: not p.name.endswith("_pve_basecolor.png") and p.exists(),
        )
        with pytest.raises(FileNotFoundError, match="growpy-pack-pve-textures"):
            build_species_asset_spec("european_beech")

    def test_the_foliage_material_sits_with_the_bark(self):
        spec = build_species_asset_spec("european_beech")
        assert spec.foliage_material == (
            "/Game/Assets/Trees/Materials/european_beech/MI_european_beech_foliage"
        )


class TestPaletteLayout:
    def test_mesh_path_matches_the_usd_importers_nesting(self):
        # A USD import writes <destination>/<name>/StaticMeshes/SM_<name>.
        proto = PalettePrototype("european_beech_foliage_a", Path("x.usda"))
        assert proto.mesh_path("/Game/PVE/Beech/Foliage") == (
            "/Game/PVE/Beech/Foliage/european_beech_foliage_a"
            "/StaticMeshes/SM_european_beech_foliage_a"
        )

    def test_palette_meshes_is_what_a_graph_spec_takes(self):
        from growpy.io.unreal.pve_graph_builder import (
            DistributorSpec,
            PVEGraphSpec,
            TreeChainSpec,
        )

        spec = build_species_asset_spec("european_beech")
        graph = PVEGraphSpec(
            graph_name="PVG_Beech",
            chains=(
                TreeChainSpec(
                    growth_json=Path("tree.json"),
                    mesh_name="SK_Beech",
                    distributor=DistributorSpec(branch_density=8),
                ),
            ),
            palette_meshes=spec.palette_meshes,
            bark_material=spec.bark_material,
            export_folder="/Game/Exported",
        )
        assert len(graph.palette_meshes) == 5
        # The graph instances the re-framed PARTS, never the raw imports: PVE
        # places a part with mesh +Z as the growth axis, growpy authors +X.
        assert all(m.endswith("_ZUP") for m in graph.palette_meshes)

    def test_part_sits_beside_its_import(self):
        proto = PalettePrototype("pacific_silver_fir_foliage_a", Path("x.usda"))
        assert proto.part_path("/Game/PVE/Fir/Foliage") == (
            proto.mesh_path("/Game/PVE/Fir/Foliage") + "_ZUP"
        )

    def test_bark_material_name_is_derived_from_the_species(self):
        assert _spec().bark_material.endswith("/MI_european_beech_bark")


class TestRefusals:
    def test_an_empty_palette_is_refused(self):
        with pytest.raises(ValueError, match="palette cannot be empty"):
            _spec(prototypes=())

    def test_duplicate_prototypes_are_refused(self):
        proto = PalettePrototype("dup", Path("dup_static.usda"))
        with pytest.raises(ValueError, match="duplicate prototypes"):
            _spec(prototypes=(proto, proto))

    def test_a_relative_content_folder_is_refused(self):
        with pytest.raises(ValueError, match="UE package path"):
            _spec(content_folder="PVE/Beech")

    def test_the_game_templates_master_is_refused(self):
        # Parenting to the /Game/Templates copy of MA_Foliage_Trees has
        # produced broken materials before.
        with pytest.raises(ValueError, match="/Game/Templates"):
            _plan(master_material="/Game/Templates/MA_Foliage_Trees")

    def test_factory_creation_has_no_path_without_a_clone_source(self):
        with pytest.raises(ValueError, match="known-good instance"):
            _plan(clone_sources=())

    def test_two_species_in_one_folder_are_refused(self):
        with pytest.raises(ValueError, match="share a content folder"):
            _plan(
                species=(
                    _spec(species="european_beech"),
                    _spec(species="silver_fir"),
                )
            )

    def test_an_empty_plan_is_refused(self):
        with pytest.raises(ValueError, match="no species"):
            _plan(species=())

    def test_half_a_foliage_pair_is_refused(self):
        # One map alone would leave the cloned sample's own map in the other.
        with pytest.raises(ValueError, match="pair"):
            _spec(foliage_color=Path("a_pve_basecolor.png"))

    def test_an_unknown_habit_is_refused(self):
        with pytest.raises(ValueError, match="habit"):
            _spec(habit="palm")


class TestGeneratedScript:
    @pytest.fixture
    def script(self, tmp_path) -> str:
        specs = tuple(
            build_species_asset_spec(s) for s in ("european_beech", "silver_fir")
        )
        path = generate_pve_asset_script(tmp_path, PVEAssetPlan(species=specs))
        return path.read_text(encoding="utf-8")

    def test_it_is_valid_python(self, script):
        ast.parse(script)

    def test_virtual_texture_streaming_is_set_before_the_material_is_built(
        self, script
    ):
        # MA_Foliage_Trees samples virtual textures; a non-VT texture on it
        # renders as shifting magenta. Reparenting first would have swapped an
        # untextured beech trunk for a magenta one.
        loop = script.split("for spec in PLAN[", 1)[1]
        vt = loop.index("import_bark_texture(entry, is_normal)")
        material = loop.index("build_bark_material(spec, master)")
        assert vt < material

    def test_it_clones_rather_than_factory_creating(self, script):
        assert "duplicate_asset" in script
        assert "MaterialInstanceConstantFactoryNew" not in script

    def test_it_reframes_each_prototype_into_pves_part_frame(self, script):
        # X->Z, Z->Y, Y->X as one proper rotation, refused unless the import
        # is in growpy's authoring frame, and verified by reading the part back.
        assert "unreal.Quat(-0.5, -0.5, -0.5, 0.5)" in script
        assert "origin is not at the -X end" in script
        assert "re-framed part has the wrong extents" in script
        assert "'part': '" in script and "_ZUP'" in script

    def test_it_verifies_the_clone_source_is_parented_to_the_master(self, script):
        assert "def resolve_clone_source" in script
        assert "if parent == master:" in script

    def test_it_audits_for_usd_stubs(self, script):
        # The specific failure that went unnoticed for weeks gets its own sweep.
        assert "def audit_for_usd_stubs" in script
        assert "UsdPreviewSurface" in script

    def test_it_reads_back_rather_than_assuming(self, script):
        assert "check = eal.load_asset(mi_path)" in script
        assert "get_material_instance_texture_parameter_value" in script

    def test_it_fails_loudly(self, script):
        assert "raise RuntimeError" in script

    def test_it_skips_prototypes_that_already_exist(self, script):
        assert "does_asset_exist(proto[" in script

    def test_it_carries_absolute_forward_slash_sources(self, script):
        assert "\\\\" not in script
        assert "_static.usda" in script
        assert "beech_60_bark_normal.jpg" in script

    def test_it_names_the_plugins_master_not_a_game_copy(self, script):
        assert DEFAULT_MASTER_MATERIAL in script

    def test_the_leaves_get_a_material_the_foliage_actor_reaches(self, script):
        # Season and health reach a leaf only through MA_Foliage_Trees; the USD
        # import's UsdPreviewSurface cannot see MPC_GlobalFoliageActor.
        assert "MI_european_beech_foliage" in script
        assert "MI_silver_fir_foliage" in script
        assert FOLIAGE_SAMPLES["broadleaf"] in script
        assert FOLIAGE_SAMPLES["conifer"] in script
        assert "def repoint_leaf_materials" in script

    def test_leaf_maps_come_before_the_leaf_material_and_the_leaves(self, script):
        loop = script.split("for spec in PLAN[", 1)[1]
        maps = loop.index("import_foliage_texture(entry, is_normal)")
        material = loop.index("build_foliage_material(spec, master)")
        leaves = loop.index("repoint_leaf_materials(spec)")
        assert maps < material < leaves

    def test_the_leaf_normal_keeps_its_translucency(self, script):
        # The packed Normal carries translucency in alpha, and the plugin's own
        # samples import it as Masks; TC_NORMALMAP would drop the alpha.
        body = script.split("def import_foliage_texture", 1)[1].split("\ndef ", 1)[0]
        assert "TC_MASKS" in body
        assert "TC_NORMALMAP" not in body

    def test_a_leaf_is_repaired_in_place_not_replaced(self, script):
        # Exported trees reference the palette's leaf instances by path.
        body = script.split("def repoint_leaf_materials", 1)[1].split("\ndef ", 1)[0]
        assert "clear_all_material_instance_parameters" in body
        assert "duplicate_asset" not in body
        assert "delete_asset" not in body

    def test_it_refuses_while_the_open_level_shows_trees(self, script):
        # Re-parenting the leaves with a gallery open crashed the editor on the
        # material save (2026-09-25): nothing may change before this check.
        assert "def trees_in_open_level" in script
        guard = script.index("trees = trees_in_open_level()")
        assert guard < script.index("for spec in PLAN[")
        assert "open an empty level" in script

    def test_every_prototype_reaches_the_script(self, script):
        for species, count in (("european_beech", 5), ("pacific_silver_fir", 9)):
            # once as the USD import, once as the re-framed part
            assert script.count(f"SM_{species}_foliage") == 2 * count
            assert len(re.findall(rf"SM_{species}_foliage\w*_ZUP", script)) == count

    def test_redeploying_to_the_same_path_overwrites(self, tmp_path):
        plan = PVEAssetPlan(species=(build_species_asset_spec("european_beech"),))
        first = generate_pve_asset_script(tmp_path, plan)
        second = generate_pve_asset_script(tmp_path, plan)
        assert first == second


class TestCli:
    """growpy-pve-assets: the runnable form of the step."""

    def test_named_species_write_a_script_and_succeed(self, tmp_path):
        from growpy.tools.pve_assets import main

        rc = main(["european_beech", "silver_fir", "--output-dir", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "growpy_pve_assets.py").is_file()

    def test_a_species_with_missing_sources_is_reported_in_the_exit_code(
        self, tmp_path
    ):
        # A skipped species means an untextured trunk or an empty palette, so
        # it must not look like a clean run.
        from growpy.tools.pve_assets import main

        rc = main(["european_beech", "avocado", "--output-dir", str(tmp_path)])
        assert rc == 2
        # The importable species still got a script.
        assert (tmp_path / "growpy_pve_assets.py").is_file()

    def test_no_importable_species_fails(self, tmp_path):
        from growpy.tools.pve_assets import main

        assert main(["avocado", "--output-dir", str(tmp_path)]) == 1
        assert not (tmp_path / "growpy_pve_assets.py").exists()

    def test_the_content_root_reaches_the_script(self, tmp_path):
        from growpy.tools.pve_assets import main

        main(["european_beech", "--output-dir", str(tmp_path),
              "--content-root", "/Game/PVE_Test"])
        text = (tmp_path / "growpy_pve_assets.py").read_text(encoding="utf-8")
        assert "/Game/PVE_Test/Foliage/european_beech" in text
