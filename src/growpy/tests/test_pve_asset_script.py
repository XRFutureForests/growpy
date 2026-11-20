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

from growpy.config.ue_layout import MATERIALS_PATH, TWIGS_PATH
from growpy.io.unreal.pve_asset_script import (
    DEFAULT_CLONE_SOURCES,
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
        # The packed _NAH map (pack-pve-textures --bark) wins over the raw one.
        assert spec.bark_normal.stem.endswith(("_bark_normal", "_bark_pve_nah"))

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
        assert spec.content_folder == f"{TWIGS_PATH}/Beech"
        assert spec.materials_folder == f"{MATERIALS_PATH}/Beech"

    def test_the_palette_and_the_materials_are_sorted_by_type(self):
        spec = build_species_asset_spec("european_beech")
        assert spec.foliage_folder == f"{TWIGS_PATH}/european_beech"
        assert spec.bark_folder == f"{MATERIALS_PATH}/european_beech"

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

    @pytest.mark.parametrize(
        "species,habit,seasons",
        [
            ("silver_fir", "conifer", False),
            ("norway_spruce", "conifer", False),
            ("european_larch", "conifer", True),
            ("european_beech", "broadleaf", True),
        ],
    )
    def test_evergreen_conifers_keep_out_of_the_season(self, species, habit, seasons):
        # Broadleaves and larch colour in autumn; spruce, fir, pine and
        # Douglas fir keep their needles green (decision 2026-10-25).
        assert _spec(species=species, habit=habit).seasons is seasons

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
            f"{MATERIALS_PATH}/european_beech/MI_european_beech_foliage"
        )


class TestPaletteLayout:
    def test_an_existing_mesh_is_used_in_place(self):
        # E116: a mesh already in PVE's frame (a MegaPlants part) is used in place
        mesh = "/Game/X/Parts/Branch_01"
        proto = PalettePrototype("mp_p00", Path("e/twig.toml"), existing=mesh)
        assert proto.mesh_path("/Game/F") == proto.part_path("/Game/F") == mesh
        with pytest.raises(ValueError, match="/Game/"):
            PalettePrototype("mp_p00", Path("e/twig.toml"), existing="X/Branch_01")

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

    def test_the_schema_folder_master_is_refused(self):
        # Parenting to the schema-folder copy of MA_Foliage_Trees has
        # produced broken materials before.
        with pytest.raises(ValueError, match="/Game/XRFF/Forest/Data"):
            _plan(master_material="/Game/XRFF/Forest/Data/MA_Foliage_Trees")

    def test_the_schema_folder_master_is_refused_for_the_bark_too(self):
        with pytest.raises(ValueError, match="/Game/XRFF/Forest/Data"):
            _plan(bark_master_material="/Game/XRFF/Forest/Data/MA_Foliage_Trees")

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
        material = loop.index("build_bark_material(spec, master, spec_master)")
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
        assert any(
            name in script
            for name in ("beech_60_bark_normal.jpg", "beech_60_bark_pve_nah.png")
        )

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
        # The switch is set from the habit, not left as the cloned sample has it.
        assert '"Seasons", fol["seasons"]' in script
        assert "'seasons': False" in script and "'seasons': True" in script

    def test_leaf_maps_come_before_the_leaf_material_and_the_leaves(self, script):
        loop = script.split("for spec in PLAN[", 1)[1]
        maps = loop.index("import_foliage_texture(entry, is_normal)")
        material = loop.index("build_foliage_material(spec, master)")
        leaves = loop.index("repoint_leaf_materials(spec)")
        assert maps < material < leaves

    def test_the_leaf_normal_keeps_its_translucency(self, script):
        # The packed Normal carries translucency in B, and the plugin's own
        # samples import it as Masks; TC_NORMALMAP keeps only R/G.
        body = script.split("def import_foliage_texture", 1)[1].split("\ndef ", 1)[0]
        assert "TC_MASKS" in body
        assert "TC_NORMALMAP" not in body

    def test_the_bark_normal_keeps_its_ambient_occlusion(self, script):
        # The trunk function reads AO from the Normal map's B (MegaPlants' _NAH
        # bark); BC5 drops B, so TC_NORMALMAP rendered every trunk black in shade.
        body = script.split("def import_bark_texture", 1)[1].split("\ndef ", 1)[0]
        assert "TC_MASKS" in body
        assert "TC_NORMALMAP" not in body

    def test_the_leaf_colour_keeps_its_coverage_at_distance(self, script):
        # Without coverage-scaled mips the averaged alpha stays above the 0.333
        # clip and distant leaf cards render as opaque squares.
        body = script.split("def import_foliage_texture", 1)[1].split("\ndef ", 1)[0]
        assert "do_scale_mips_for_alpha_coverage" in body
        assert "0.3333" in body

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

    def test_the_bark_follows_the_master_unless_the_plan_names_another(self, script):
        # Clone sources are checked against the master; the bark is parented to
        # (and read back against) the bark master.
        assert f"'bark_master_material': '{DEFAULT_MASTER_MATERIAL}'" in script
        body = script.split("def build_bark_material", 1)[1].split("\ndef ", 1)[0]
        assert "resolve_clone_source(master)" in body
        assert "eal.load_asset(bark_master)" in body
        assert "if parent != bark_master:" in body

    def test_a_named_bark_master_reaches_the_script(self, tmp_path):
        trunk = "/Game/00_XRFF/30_Forest/Materials/MA_Foliage_Trees_TrunkDBH"
        plan = PVEAssetPlan(
            species=(build_species_asset_spec("european_beech"),),
            bark_master_material=trunk,
        )
        script = generate_pve_asset_script(tmp_path, plan).read_text(encoding="utf-8")
        assert f"'bark_master_material': '{trunk}'" in script
        assert f"'master_material': '{DEFAULT_MASTER_MATERIAL}'" in script

    def test_redeploying_to_the_same_path_overwrites(self, tmp_path):
        plan = PVEAssetPlan(species=(build_species_asset_spec("european_beech"),))
        first = generate_pve_asset_script(tmp_path, plan)
        second = generate_pve_asset_script(tmp_path, plan)
        assert first == second


class TestBarkTilePair:
    """XRFF-679: trunk and branch bark sources, MI_<species>_bark_branch."""

    @staticmethod
    def _cal(trunk, branch):
        from types import SimpleNamespace

        return SimpleNamespace(bark_trunk_source=trunk, bark_branch_source=branch)

    @pytest.fixture
    def catalog(self, tmp_path):
        path = tmp_path / "catalog.toml"
        path.write_text(
            '[materials.t]\ninstance = "/Game/B/t/MI_t"\n'
            '[materials.b]\ninstance = "/Game/B/b/MI_b"\n',
            encoding="utf-8",
        )
        return path

    def test_intake_ids_resolve_to_their_instances(self, catalog):
        from growpy.tools.pve_assets import bark_pair_sources

        assert bark_pair_sources(self._cal("t", "b"), catalog) == (
            "/Game/B/t/MI_t",
            "/Game/B/b/MI_b",
        )

    def test_an_atlas_trunk_names_its_material(self, catalog):
        from growpy.config.pve_calibration import BarkAtlasStrip
        from growpy.tools.pve_assets import bark_pair_sources

        strip = BarkAtlasStrip(
            material="/Game/MP/MI_x", u_range=(0.0, 0.7), y_scale=0.8
        )
        assert bark_pair_sources(self._cal(strip, "b"), catalog) == (
            "/Game/MP/MI_x",
            "/Game/B/b/MI_b",
        )

    def test_no_pair_means_no_sources(self, catalog):
        from growpy.tools.pve_assets import bark_pair_sources

        assert bark_pair_sources(self._cal(None, None), catalog) == ("", "")

    def test_an_unknown_intake_id_is_refused(self, catalog):
        from growpy.tools.pve_assets import bark_pair_sources

        with pytest.raises(KeyError, match="nope"):
            bark_pair_sources(self._cal("t", "nope"), catalog)

    def test_the_branch_bark_is_built_after_the_trunk_bark(self, tmp_path):
        spec = build_species_asset_spec(
            "european_beech",
            bark_source_material="/Game/B/t/MI_t",
            bark_branch_source_material="/Game/B/b/MI_b",
        )
        script = generate_pve_asset_script(
            tmp_path, PVEAssetPlan(species=(spec,))
        ).read_text(encoding="utf-8")
        ast.parse(script)
        assert "'bark_branch_source_material': '/Game/B/b/MI_b'" in script
        loop = script.split("for spec in PLAN[", 1)[1]
        trunk = loop.index("build_bark_material(spec, master, spec_master)")
        branch = loop.index("build_bark_material(branch, master, spec_master)")
        assert trunk < branch
        assert 'spec["bark_material"] + "_branch"' in loop

    def test_the_bark_zone_instances_reach_the_script(self, tmp_path):
        # Owner 2026-11-19 (pine fox bark): one MI_<species>_bark_zone_h<NN> per
        # height class, on the two-bark master, which must exist before anything runs.
        from growpy.io.unreal.pve_asset_script import DEFAULT_BARK_ZONE_MASTER

        spec = build_species_asset_spec(
            "european_beech",
            bark_source_material="/Game/B/t/MI_t",
            bark_branch_source_material="/Game/B/b/MI_b",
            bark_zone_source_material="/Game/B/u/MI_u",
            bark_zone_upper_tiling=(0.5, 1.0),
            bark_zone_heights=((20, 2.0), (25, 1.75)),
        )
        script = generate_pve_asset_script(
            tmp_path, PVEAssetPlan(species=(spec,))
        ).read_text(encoding="utf-8")
        ast.parse(script)
        assert DEFAULT_BARK_ZONE_MASTER.endswith(
            "MA_Foliage_Trees_TwoBarkBlend_TrunkDBH"
        )
        assert f"'bark_zone_master_material': '{DEFAULT_BARK_ZONE_MASTER}'" in script
        assert "'bark_zone_heights': [[20, 2.0], [25, 1.75]]" in script
        assert "'bark_zone_upper_tiling': [0.5, 1.0]" in script
        assert "'Additional Blend Ratio': 1.8" in script
        body = script.split("def build_zone_material", 1)[1].split("\ndef ", 1)[0]
        assert '"%s_zone_h%02d" % (spec["bark_material"], stage)' in body
        for param in ("Lower ", "Upper ", "Blend Height", "Upper Trunk U Tiling"):
            assert param in body
        assert "if parent != zone_master:" in body  # read back
        # the missing master stops the run before any asset is touched
        guard = script.index("bark zone master not found")
        assert guard < script.index("for spec in PLAN[")
        loop = script.split("for spec in PLAN[", 1)[1]
        assert "build_zone_material(spec, stage, blend_height, zone_master)" in loop

    def test_zone_heights_need_both_sources(self):
        with pytest.raises(ValueError, match="bark zone heights"):
            build_species_asset_spec("european_beech", bark_zone_heights=((20, 2.0),))

    def test_the_zone_tiling_follows_the_intake_tiles(self, tmp_path):
        from types import SimpleNamespace

        from growpy.tools.pve_assets import bark_zone_source

        catalog = tmp_path / "catalog.toml"
        catalog.write_text(
            '[materials.t]\ninstance = "/Game/B/t/MI_t"\ntile_size_m = [1.0, 2.0]\n'
            '[materials.u]\ninstance = "/Game/B/u/MI_u"\ntile_size_m = [2.0, 2.0]\n'
            '[materials.g]\ninstance = "/Game/B/g/MI_g"\ntile_size_m = "grove-wraps"\n',
            encoding="utf-8",
        )
        cal = SimpleNamespace(bark_trunk_source="t", bark_upper_source="u")
        # plated 1 x 2 m below, orange 2 x 2 m above: U 0.5, V 1.0 (barkzone test)
        assert bark_zone_source(cal, catalog) == ("/Game/B/u/MI_u", (0.5, 1.0))
        assert bark_zone_source(SimpleNamespace(), catalog) == ("", (1.0, 1.0))
        with pytest.raises(ValueError, match="tile_size_m"):
            bark_zone_source(
                SimpleNamespace(bark_trunk_source="t", bark_upper_source="g"), catalog
            )
        with pytest.raises(KeyError):
            bark_zone_source(
                SimpleNamespace(bark_trunk_source="t", bark_upper_source="x"), catalog
            )

    def test_a_sandbox_calibration_reaches_the_script(self, tmp_path):
        # The tile-pair test runs from a calibration copy so the catalog's
        # oak keeps its atlas until the owner switches it.
        from growpy.tools.pve_assets import main

        shipped = Path("config/pve_calibration.toml").read_text(encoding="utf-8")
        line = next(
            ln for ln in shipped.splitlines()
            if ln.startswith("bark_source_per_species.european_oak")
        )
        sandbox = tmp_path / "pve_calibration.toml"
        sandbox.write_text(
            shipped.replace(
                line,
                'bark_source_per_species.european_oak = { trunk = "fab_oak_bark", '
                'branch = "fab_chestnut_bark_oak_branch" }',
            ),
            encoding="utf-8",
        )
        rc = main(["european_oak", "--output-dir", str(tmp_path),
                   "--calibration", str(sandbox)])
        script = (tmp_path / "growpy_pve_assets.py").read_text(encoding="utf-8")
        assert rc == 0
        assert "MI_fab_chestnut_bark_oak_branch'" in script
        assert "MI_fab_oak_bark'" in script


TRUNK_DBH = "/Game/00_XRFF/30_Forest/Materials/MA_Foliage_Trees_TrunkDBH"


class _Asset:
    """A fake UE object: a path and a parent, editor properties recorded."""

    def __init__(self, path, parent=None):
        self.path, self.parent, self.writes = path, parent, []

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]

    def get_editor_property(self, name):
        assert name == "parent"
        return self.parent

    def set_editor_property(self, name, value):
        self.writes.append((name, value))
        if name == "parent":
            self.parent = value


class _Eal:
    def __init__(self, assets):
        self.assets = dict(assets)

    def does_asset_exist(self, path):
        return path in self.assets

    def load_asset(self, path):
        return self.assets.get(path)

    def duplicate_asset(self, src, dst):
        self.assets[dst] = _Asset(dst, self.assets[src].parent)
        return self.assets[dst]

    def save_asset(self, path, only_if_is_dirty=True):
        return True


class TestBarkMasterGuard:
    """2026-11-19 (decision (a)): a plan never silently moves a bark MI's master."""

    MI = "/Game/T/Materials/european_beech/MI_european_beech_bark"

    @staticmethod
    def _build_bark_material(tmp_path, eal, allow=False):
        """The generated script's build_bark_material, run on fakes."""
        from unittest import mock

        script = generate_pve_asset_script(
            tmp_path, _plan(allow_bark_reparent=allow)
        ).read_text(encoding="utf-8")
        defs = script.split("USD_STUB = ", 1)[1].split('print("=" * 64)', 1)[0]
        plan_line = script.split("PLAN = ", 1)[1].split("\neal = ", 1)[0]
        mel = mock.MagicMock()
        mel.get_material_instance_texture_parameter_value.side_effect = lambda mi, p: (
            _Asset("/Game/T/" + p.replace(" ", ""))
        )
        ns = {"unreal": mock.MagicMock(), "eal": eal, "mel": mel, "failures": []}
        exec("PLAN = " + plan_line + "\nUSD_STUB = " + defs, ns)
        return ns["build_bark_material"]

    def _spec(self):
        return {
            "species": "european_beech",
            "bark_material": self.MI,
            "bark_color": {"asset": "/Game/T/BaseColor"},
            "bark_normal": {"asset": "/Game/T/Normal"},
            "bark_source_material": "",
            "bark_source_textures": True,
        }

    def _eal(self, mi_parent):
        plugin = _Asset(DEFAULT_MASTER_MATERIAL)
        trunk = _Asset(TRUNK_DBH)
        assets = {
            DEFAULT_MASTER_MATERIAL: plugin,
            TRUNK_DBH: trunk,
            "/Game/T/BaseColor": _Asset("/Game/T/BaseColor"),
            "/Game/T/Normal": _Asset("/Game/T/Normal"),
            DEFAULT_CLONE_SOURCES[0]: _Asset(DEFAULT_CLONE_SOURCES[0], plugin),
        }
        if mi_parent is not None:
            assets[self.MI] = _Asset(self.MI, assets[mi_parent])
        return _Eal(assets)

    def test_a_release_cannot_reparent_an_existing_mi(self, tmp_path):
        eal = self._eal(mi_parent=DEFAULT_MASTER_MATERIAL)
        build = self._build_bark_material(tmp_path, eal)
        problems = build(self._spec(), DEFAULT_MASTER_MATERIAL, TRUNK_DBH)
        assert len(problems) == 1
        assert f"_bark parent is {DEFAULT_MASTER_MATERIAL}, " in problems[0]
        assert f"plan wants {TRUNK_DBH}; reparent explicitly" in problems[0]
        assert eal.assets[self.MI].writes == []  # untouched

    def test_allow_bark_reparent_moves_it(self, tmp_path):
        eal = self._eal(mi_parent=DEFAULT_MASTER_MATERIAL)
        build = self._build_bark_material(tmp_path, eal, allow=True)
        assert build(self._spec(), DEFAULT_MASTER_MATERIAL, TRUNK_DBH) == []
        assert eal.assets[self.MI].parent.path == TRUNK_DBH

    def test_an_mi_on_its_master_or_a_new_clone_is_built(self, tmp_path):
        on_master = self._eal(mi_parent=TRUNK_DBH)
        build = self._build_bark_material(tmp_path, on_master)
        assert build(self._spec(), DEFAULT_MASTER_MATERIAL, TRUNK_DBH) == []
        new = self._eal(mi_parent=None)  # cloned from a plugin sample, then parented
        build = self._build_bark_material(tmp_path, new)
        assert build(self._spec(), DEFAULT_MASTER_MATERIAL, TRUNK_DBH) == []
        assert new.assets[self.MI].parent.path == TRUNK_DBH

    def test_each_species_carries_its_master_into_the_script(self, tmp_path):
        spec = build_species_asset_spec(
            "european_beech", bark_master_material=TRUNK_DBH
        )
        script = generate_pve_asset_script(
            tmp_path, PVEAssetPlan(species=(spec,))
        ).read_text(encoding="utf-8")
        assert f"'bark_master_material': '{TRUNK_DBH}'" in script
        assert "'allow_bark_reparent': False" in script
        loop = script.split("for spec in PLAN[", 1)[1]
        assert 'spec_master = spec["bark_master_material"] or bark_master' in loop
        # the per-species master must exist before anything is touched
        head = script.split("for spec in PLAN[", 1)[0]
        assert "species_masters" in head and "master material not found" in head

    def test_a_schema_folder_species_master_is_refused(self):
        spec = build_species_asset_spec(
            "european_beech", bark_master_material="/Game/XRFF/Forest/Data/MA_X"
        )
        with pytest.raises(ValueError, match="refusing"):
            PVEAssetPlan(species=(spec,))


class TestCli:
    """growpy-pve-assets: the runnable form of the step."""

    def test_the_calibration_master_or_an_explicit_override_reaches_the_script(
        self, tmp_path
    ):
        from growpy.tools.pve_assets import main

        main(["european_beech", "--output-dir", str(tmp_path)])
        text = (tmp_path / "growpy_pve_assets.py").read_text(encoding="utf-8")
        assert f"'bark_master_material': '{TRUNK_DBH}'" in text
        other = "/Game/Test/MA_Other"
        main(["european_beech", "--output-dir", str(tmp_path),
              "--bark-master-material", other, "--allow-bark-reparent"])  # fmt: skip
        text = (tmp_path / "growpy_pve_assets.py").read_text(encoding="utf-8")
        assert f"'bark_master_material': '{other}'" in text
        assert f"'bark_master_material': '{TRUNK_DBH}'" not in text
        assert "'allow_bark_reparent': True" in text

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
        assert "/Game/PVE_Test/Twigs/european_beech" in text


class TestCompoundPaletteExistingParts:
    """Pine 1.2: a compound palette may name parts already in the project."""

    def _manifest(self, tmp_path, monkeypatch, entries):
        import json

        import growpy.config.paths as paths
        from growpy.io.unreal import pve_asset_script as pas

        assets = tmp_path / "assets"
        (assets / "compound_parts").mkdir(parents=True)
        (assets / "compound_parts" / "scots_pine_pve_palette.json").write_text(
            json.dumps({"prototypes": entries})
        )
        monkeypatch.setattr(paths, "get_assets_directory", lambda: assets)
        monkeypatch.setattr(paths, "get_project_root", lambda: tmp_path)
        return pas

    def test_an_existing_part_is_used_in_place(self, tmp_path, monkeypatch):
        entry = tmp_path / "data/input/twigs/scots_pine__mp_x/twig.toml"
        entry.parent.mkdir(parents=True)
        entry.write_text("")
        pas = self._manifest(
            tmp_path,
            monkeypatch,
            [
                {
                    "name": "scots_pine_mp_p00",
                    "entry": "data/input/twigs/scots_pine__mp_x/twig.toml",
                    "existing": "/Game/Generated/Trees/Foliage/scots_pine/MP/Twig_03",
                }
            ],
        )
        (proto,) = pas._compound_prototypes("scots_pine")
        assert proto.existing == "/Game/Generated/Trees/Foliage/scots_pine/MP/Twig_03"
        assert proto.source == entry
        assert proto.mesh_path("/Game/x") == proto.existing

    def test_a_missing_twig_entry_fails_loudly(self, tmp_path, monkeypatch):
        pas = self._manifest(
            tmp_path,
            monkeypatch,
            [
                {
                    "name": "p",
                    "entry": "data/input/twigs/nope/twig.toml",
                    "existing": "/Game/A",
                }
            ],
        )
        with pytest.raises(FileNotFoundError, match="twig catalog entry missing"):
            pas._compound_prototypes("scots_pine")
