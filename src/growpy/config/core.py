"""Core configuration for GrowPy.

Central configuration loaded from TOML files with layered resolution:
    dataclass defaults -> config/*.toml -> CLI arguments

All TOML files in the resolved config directory are loaded in sorted order
and deep-merged. Filenames are for humans (e.g. general.toml, assets.toml,
twigs.toml, growth_models.toml, forest.toml, quality.toml, unreal.toml,
helios.toml, competition.toml) -- the loader does not care about naming.

To seed a fresh project with a starter config/ directory, run
``growpy-init-config``.
"""

import logging
import os
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Optional

logger = logging.getLogger(__name__)

_global_config: Optional["GrowPyConfig"] = None


def get_global_config() -> Optional["GrowPyConfig"]:
    """Get the currently active global config instance."""
    return _global_config


def set_global_config(config: "GrowPyConfig") -> None:
    """Set the global config instance."""
    global _global_config
    _global_config = config


def _editable_install_root() -> Path:
    """Repo root assuming editable install: src/growpy/config/core.py -> 4 up."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _find_config_dir() -> Path | None:
    """Find the directory holding *.toml config files.

    Search order:
        1. GROWPY_CONFIG env var (accepts a directory OR a file inside one)
        2. ./config/ in the current working directory
        3. <editable-install-root>/config/
    """
    env_path = os.environ.get("GROWPY_CONFIG")
    if env_path:
        p = Path(env_path)
        if not p.exists():
            return None
        return p if p.is_dir() else p.parent

    cwd_dir = Path.cwd() / "config"
    if cwd_dir.is_dir():
        return cwd_dir

    install_dir = _editable_install_root() / "config"
    if install_dir.is_dir():
        return install_dir

    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_toml_data(toml_path: Path) -> dict:
    """Deep-merge every *.toml in the same directory as ``toml_path``.

    Accepts either a file inside the config dir or the config dir itself.
    Files are merged in sorted order so results are deterministic.
    """
    cfg_dir = toml_path if toml_path.is_dir() else toml_path.parent
    data: dict = {}
    for sibling in sorted(cfg_dir.glob("*.toml")):
        with open(sibling, "rb") as f:
            data = _deep_merge(data, tomllib.load(f))
    return data


def get_config() -> "GrowPyConfig":
    """Get config instance, auto-loading the ``config/`` directory if present.

    Search order for the config directory:
        1. GROWPY_CONFIG environment variable (directory or any file inside one)
        2. ./config/ (current working directory)
        3. <editable-install-root>/config/

    If no config directory is found, returns dataclass defaults.
    """
    global _global_config
    if _global_config is None:
        cfg_dir = _find_config_dir()
        if cfg_dir:
            _global_config = GrowPyConfig.from_toml(cfg_dir, set_as_global=False)
        else:
            _global_config = GrowPyConfig()
    return _global_config


@dataclass
class GrowPyConfig:
    """Central configuration for GrowPy tree generation.

    All CLI scripts read defaults from this config. CLI arguments
    override config values via the resolve() method.
    """

    # CLI arg name -> config field name, used by resolve() below. Hoisted to a
    # class attribute (rather than a resolve()-local dict) so tests can assert
    # every key is backed by a real CLI parser and every value either has an
    # entry here or is on the TOML_ONLY_FIELDS allowlist (see test_config.py) --
    # the drift this stops recurring is documented in XRFF-292.
    CLI_MAPPINGS: ClassVar[dict[str, str]] = {
        # [general]
        "csv_file": "csv_file",
        "csv": "csv_file",
        "output_dir": "output_dir",
        "verbose": "verbose",
        "profile": "profile",
        # [assets]
        "grove_dir": "grove_dir",
        "resize_textures": "resize_textures",
        # [twigs]
        "alpha_trim": "twigs_alpha_trim",
        "boundary_edge_mm": "twigs_boundary_edge_mm",
        "interior_edge_mm": "twigs_interior_edge_mm",
        "densify": "twigs_densify",
        # [growth_models]
        "cycles": "growth_models_cycles",
        "seeds": "growth_models_seeds",
        "height_threshold": "growth_models_height_threshold",
        "max_cycles_without_growth": "growth_models_max_cycles_without_growth",
        "timeout": "growth_models_timeout",
        "growth_models_max_height": "growth_models_max_height",
        # [forest]
        "quality": "forest_quality",
        "growth_cycle_limit": "forest_growth_cycle_limit",
        "plateau_cycles": "forest_plateau_cycles",
        "include_grove_attributes": "forest_include_grove_attributes",
        "height_interval": "forest_height_interval",
        "max_height": "forest_max_height",
        # [forest.skeleton]
        "skeleton_length": "forest_skeleton_length",
        "skeleton_reduce": "forest_skeleton_reduce",
        "skeleton_bias": "forest_skeleton_bias",
        "skeleton_connected": "forest_skeleton_connected",
        # [export]
        "skeletal": "export_skeletal",
        "static": "export_static",
        "skip_validation": "export_skip_validation",
        "previews": "export_previews",
        "export_control": "export_control_images",
        "icons": "export_icons",
        "icon_components": "export_icon_components",
        # [unreal]
        "import_to_unreal": "unreal_import_to_unreal",
        "unreal_project_path": "unreal_project_path",
        "pve": "unreal_generate_pve_presets",
        "wind": "unreal_generate_wind_data",
        # [helios]
        "export_obj": "helios_export_obj",
        "helios_scene": "helios_helios_scene",
        "individual_obj": "helios_individual_obj",
        "obj_up_axis": "helios_obj_up_axis",
        "classification": "helios_classification",
        # [calibration]
        "calibrate": "calibration_enabled",
    }

    # GrowPyConfig fields that from_toml() can set but that intentionally have
    # no CLI override (no `resolve()` mapping). Every field from_toml() can
    # populate must appear either here or as a CLI_MAPPINGS value -- enforced
    # by test_config.py::test_toml_settable_fields_have_mapping_or_are_allowlisted.
    TOML_ONLY_FIELDS: ClassVar[dict[str, str]] = {
        "random_seed": "determinism seed, not meant to vary per invocation",
        "twigs_path": "path override via CLI positional arg, outside resolve()",
        "custom_twigs_dir": "internal override, no CLI need identified",
        "twigs_interior_boundary_rings": "fine-tuning param, no CLI need identified",
        "forest_smooth_iterations": "CLI-settable via the smooth_iterations "
        "special-case in resolve(), not this dict",
        "forest_export_trees": "CLI-settable via the export_trees special-case "
        "in resolve(), not this dict",
        "export_usd_format": "CLI override deferred to XRFF-277 (path/format epic)",
        "export_mode": "scenario-level choice (unreal vs helios pipeline), config-only",
        "export_max_skeleton_joints": "internal tuning, no CLI need identified",
        "export_max_assembly_instances": "internal tuning, no CLI need identified",
        "export_dbh_from_allometry": "internal tuning, no CLI need identified",
        "export_twig_density": "internal tuning, no CLI need identified",
        "export_twig_density_per_species": "nested dict structure, config-only by design",
        "quality_build_cutoff_thickness_per_species": (
            "nested dict structure, config-only by design: each entry records a "
            "measured cutoff sweep for that species, which belongs beside the "
            "measurement in config, not on a command line"
        ),
        "surround_grow_per_species": "nested dict structure, config-only by design",
        "surround_density_per_species": "nested dict structure, config-only by design",
        "export_twig_reattach_threshold": "internal tuning, no CLI need identified",
        "export_twig_recovery": "internal toggle, no CLI need identified",
        "export_external_refs": "internal toggle, no CLI need identified",
        "twigs_planar_angle": "internal tuning, no CLI need identified",
        "twigs_planar_angle_per_twig": "nested dict structure, config-only by design",
        "twigs_boundary_edge_mm_per_twig": "nested dict structure, "
        "config-only by design",
        "twigs_compound_boundary_edge_mm": "conversion profile, selected by "
        "output role rather than by CLI",
        "twigs_compound_planar_angle": "conversion profile, selected by "
        "output role rather than by CLI",
        "twigs_compound_alpha_trim": "conversion profile, selected by "
        "output role rather than by CLI",
        "twigs_compound_interior_edge_mm": "conversion profile, selected by "
        "output role rather than by CLI",
        "export_twig_min_spacing_ratio": "internal tuning, no CLI need identified",
        "export_youth_bias": "internal tuning, no CLI need identified",
        "export_density_variants": "scenario-level choice, config-only by design",
        "density_variant_defs": "nested dict structure, config-only by design",
        "unreal_voxelization": "internal toggle, no CLI need identified",
        # "unreal_generate_wind_data" removed: now CLI-mapped via --wind (XRFF-293).
        "unreal_nanite_fallback_percent": "internal tuning, no CLI need identified",
        "unreal_nanite_lerp_uvs": "internal toggle, no CLI need identified",
        "unreal_nanite_fallback_target": "internal tuning, no CLI need identified",
        "unreal_db_path": "environment-level path, config-only by design",
        # "unreal_generate_pve_presets" removed: now CLI-mapped via --pve (XRFF-293).
        "unreal_pve_import_base": "environment-level path, config-only by design",
        "unreal_editor_exe": "environment-level path, config-only by design",
        "unreal_uproject": "environment-level path, config-only by design",
        "helios_simplification_enabled": "internal toggle, no CLI need identified",
        "helios_simplification_ratios": "nested dict structure, config-only",
        "helios_simplification_per_species": "nested dict, config-only",
        "calibration_align_height": "internal tuning, no CLI need identified",
        "calibration_plot": "dead CLI mapping removed in XRFF-292; config-only",
        "calibration_species": "nested dict structure, config-only by design",
        "yield_sources_store_dir": "environment-level path, config-only by design",
        "yield_sources_yield_tables_dir": "environment-level path, config-only",
        "yield_sources_preferred_region": "scenario-level setting, config-only",
        "yield_sources_preferred_site_index": "scenario-level setting, config-only",
        "yield_sources_documents": "nested dict of source paths, config-only",
        "surround_radii": "scenario-level setting, config-only by design",
        "surround_density": "scenario-level setting, config-only by design",
        "surround_height": "scenario-level setting, config-only by design",
        "surround_grow": "scenario-level setting, config-only by design",
        "forest_quality_above_height": (
            "dataset-shape setting, config-only: it pairs with a threshold and "
            "is set per production pass, not per invocation"
        ),
        "forest_quality_above_height_threshold": (
            "dataset-shape setting, config-only; see forest_quality_above_height"
        ),
    }

    # Keys a [density_variant.*] dict may override from the active quality
    # preset (config/quality.toml). Anything else is almost certainly a typo,
    # since it would silently do nothing -- see get_density_variants() (XRFF-288).
    DENSITY_VARIANT_KEYS: ClassVar[frozenset[str]] = frozenset(
        {"twig_density", "build_cutoff_age", "build_cutoff_thickness"}
    )

    # [general]
    random_seed: int | None = 42
    csv_file: Path = field(default_factory=lambda: Path("data/input/test.csv"))
    output_dir: Path = field(default_factory=lambda: Path("data/output/forest"))
    verbose: bool = False
    profile: bool = False

    # [assets]
    grove_dir: Path = field(default_factory=lambda: Path("src/the_grove_23"))
    resize_textures: bool = False

    # [twigs]
    twigs_path: Path = field(default_factory=lambda: Path("data/assets/twigs"))
    custom_twigs_dir: Path = field(
        default_factory=lambda: Path("data/input/custom_twigs")
    )
    twigs_densify: bool = True
    # Max angle (degrees) between adjacent faces still counted as coplanar when
    # generalising a twig after the alpha contour cut. Densification only
    # exists to give that cut fine edges to carve; afterwards the flat interior
    # carries no shape and dissolving it back costs nothing visually. Boundary
    # edges have a single adjacent face and are never dissolve candidates, so
    # the carved outline is preserved exactly. Result is re-triangulated.
    # 0 disables the pass.
    twigs_planar_angle: float = 1.0
    # Per-twig overrides of twigs_planar_angle, keyed on the twig OBJECT name as
    # printed by the "Planar dissolve:" log line (e.g. "OneLeavedAshSideTwig").
    # Twigs whose leaves meet at shallow angles lose a little edge fidelity at
    # the global setting and want a smaller value; needle twigs tolerate more.
    twigs_planar_angle_per_twig: dict[str, float] = field(default_factory=dict)
    # Per-twig overrides of twigs_boundary_edge_mm, keyed on the same twig
    # OBJECT name. The densification target is absolute so that one asset's
    # variants come out at a consistent density, but MAX_DENSIFY_FACES caps
    # each object independently -- so when the target is too fine for the
    # largest variant to reach, the small ones subdivide far past it and end up
    # heavier per unit leaf area than the whole spray (XRFF-412).
    twigs_boundary_edge_mm_per_twig: dict[str, float] = field(default_factory=dict)
    # NOTE: Grove's own seed twig_density is INERT in the core API -- measured
    # on a 20-cycle Douglas fir, 1.0 / 0.25 / 0.0 all yield 11,606 living twigs
    # (0.0 does not even disable them). It is a Blender-addon-only setting, so
    # crown density cannot be reduced at the source; the only working lever is
    # post-hoc thinning via export_twig_density below.
    twigs_alpha_trim: float = 0.75
    twigs_boundary_edge_mm: float = 0.5
    # Compound-part conversion profile (XRFF-359). The settings above were
    # tuned for a single small twig seen close up, which costs 7,565 faces on
    # one exported beech twig. A compound part carries a whole subtree's worth
    # of them -- measured on a 25-cycle beech at cut 0.030, the mean part
    # carries 19 twigs and the largest 361, i.e. 144k and 2.73M faces -- and
    # each leaf is much smaller on screen there, so the fidelity is wasted.
    # None means "fall back to the close-range value", so the compound profile
    # defaults to current behaviour until it is set.
    twigs_compound_boundary_edge_mm: float | None = None
    twigs_compound_planar_angle: float | None = None
    twigs_compound_alpha_trim: float | None = None
    twigs_compound_interior_edge_mm: float | None = None

    # [growth_models]
    growth_models_cycles: int = 25
    growth_models_seeds: int = 1
    growth_models_height_threshold: float = 0.1
    growth_models_max_cycles_without_growth: int = 10
    growth_models_timeout: int = 900
    # Target height (m) for calibration's Pass 1/Pass 2 simulations. 0 = no
    # target (default; run to the yield table's natural age range). Distinct
    # from forest_max_height (step 4 export cap) -- set independently so a
    # quick-testing export height cap doesn't silently truncate calibration.
    growth_models_max_height: float = 0.0

    # [forest]
    forest_quality: str = "high"
    # Alternate quality preset for tall milestone stages, and the height (m) at
    # or above which it applies. "" disables it and every stage uses
    # forest_quality. Exists because mesh cost scales with tree size far faster
    # than perceived detail: an open-grown silver fir meshes to 4.5M points at
    # h10, 7.0M at h15 and ~23M projected at h25 -- a 1.07 GB stems file at h15
    # alone, and the h25 export exhausts a 63.5 GB host.
    forest_quality_above_height: str = ""
    forest_quality_above_height_threshold: float = 0.0
    forest_growth_cycle_limit: int = 65
    forest_plateau_cycles: int = 10
    forest_smooth_iterations: int = 10
    forest_include_grove_attributes: bool = False
    forest_height_interval: float = 5.0
    forest_max_height: float = 0.0  # 0 = no limit; >0 = cap tree heights (meters)
    forest_export_trees: list = field(default_factory=list)

    # [surround] - single-tree light-competition shell (Grove's Surround feature).
    # Alternative to the multi-tree competition clusters: instead of simulating
    # neighbour trees, Grove shades the central tree against a statistical shell,
    # which is far cheaper. A tree's surround_radius value (0 = none, >0 = shell
    # distance in meters) picks which of these configured radii applies.
    surround_radii: list = field(default_factory=lambda: [0.0])
    surround_density: float = 0.7
    surround_height: float = 5.0
    surround_grow: bool = True

    # Skeleton overrides - None means inherit from quality preset (CLI-only)
    forest_skeleton_length: float | None = None
    forest_skeleton_reduce: float | None = None
    forest_skeleton_bias: float | None = None
    forest_skeleton_connected: bool | None = None

    # [export]
    export_usd_format: str = "usda"  # "usda" (ASCII) or "usdc" (binary)
    # "unreal" runs the full USD/Nanite/PVE pipeline. "helios" writes OBJ
    # directly from the Grove model per tree, skipping USD/skeleton/PVE/Unreal
    # script generation entirely for that tree (see pipelines/forest_stages.py
    # export_obj_direct). Twig prototype meshes still come from the small,
    # pre-existing per-species twig USD assets -- only the trunk and the
    # per-instance twig placement math bypass USD. "icons_only" skips USD/
    # Nanite/wind/PVE/previews/export-control entirely and writes just the
    # icon PNGs (branches + twigs, separate and merged) straight from the
    # Grove model -- see export_icons_only. For parameter tuning / visual
    # debugging runs where the mesh itself is not needed.
    export_mode: str = "unreal"
    export_skeletal: bool = True
    export_static: bool = False
    # Per-tree PNGs, generated once per tree rather than per density variant
    # (XRFF-290). Only the icons are a dataset deliverable: dataset_overview.md
    # and dataset_overview.csv are built from them. The preview (branch
    # architecture from the skeleton polylines) and the export-control render
    # (mesh edges + skeleton joints, read back from the exported USD) are
    # visual QA aids that nothing downstream consumes, and together they are
    # ~27% of a full dataset run -- the export-control alone is 15.4%. Both
    # default off; enable per run with --previews / --export-control when
    # inspecting a specific tree.
    export_icons: bool = True
    export_previews: bool = False
    export_control_images: bool = False
    # Per-view branches/twigsonly/skeleton/merged component files alongside
    # the plain/twigs icon pair (see io/usd/preview.py generate_icon_image).
    # Off by default, same reasoning as export_previews/export_control_images
    # above: a QA aid nothing downstream reads, and it roughly quadruples the
    # icons stage's per-tree image count. Only meaningful when export_icons
    # is also on.
    export_icon_components: bool = False
    export_max_skeleton_joints: int = 0  # 0 = no limit; 250 = Nanite Assembly USD
    export_max_assembly_instances: int = (
        0  # 0 = no limit; cap twig instances per assembly
    )
    export_skip_validation: bool = True
    # Crown density multiplier relative to Grove's NATURAL twig density.
    # 1.0 = exactly what Grove grew. Twigs deleted by build_cutoff_thickness are
    # restored by recovery (see core.twig.recover_cutoff_twig_placements), so
    # this is a purely artistic knob and no longer has to compensate for the
    # cutoff. The per-tree CSV twig_density column multiplies with it.
    #
    # It replaced export_twig_density_conifer / export_twig_density_broadleaf,
    # which were hand-set compensation guesses. Measured cutoff losses vary far
    # more within a growth habit than between habits (oak 2.09x vs beech 5.43x;
    # spruce 1.04x vs pine 2.20x) and also move with tree age and cutoff, so no
    # per-habit constant could track them.
    export_twig_density: float = 1.0
    # Per-species override of export_twig_density, keyed on standardized name
    # (e.g. "douglas_fir"). Required rather than optional: the density needed to
    # match literature leaf area spans ~60x across the dataset because it tracks
    # each species' twig prototype size, not Grove's placement. See
    # get_twig_density_base().
    export_twig_density_per_species: dict[str, float] = field(default_factory=dict)
    # Per-species override for the quality preset's build_cutoff_thickness, in
    # metres. A preset name conflates render resolution with structural detail
    # (see quality.toml, XRFF-404), and species differ in how thin their fine
    # branches are, so one global floor cannot serve them all.
    #
    # Measured on silver_birch h15m r00 (2026-09-08), sweeping the cutoff while
    # holding everything else:
    #     0.0040  38.12 m2 wood,   888 twigs   <- the low preset's floor
    #     0.0025 102.57 m2 wood, 3,455 twigs   (x2.69 wood, x3.89 twigs)
    #     0.0000 105.64 m2 wood, 3,474 twigs   (+3% wood, +0.5% twigs)
    # Essentially all of birch's fine branching sits between 2.5 and 4 mm, and
    # the 4 mm floor cut straight through it -- taking the twig attachment
    # points with it, which is why birch measured 0.27 of its Forrester leaf
    # area and why no twig_density could have fixed it. Going below 2.5 mm buys
    # almost nothing and costs triangles, so this is a floor to lower per
    # species, not to remove.
    #
    # Both metrics above are resolution-independent (surface area is geometry,
    # twig count is attachment points), so this override is the structural half
    # of the preset and can be set without moving to a finer tessellation.
    quality_build_cutoff_thickness_per_species: dict[str, float] = field(
        default_factory=dict
    )
    # Per-species override for the surround shell tracking the tree. Conifers
    # and broadleaves respond so differently to a growing shell that one global
    # value cannot serve both: measured 2026-08-25 at r08, grow = true takes
    # european_oak to a realistic crown (0.52 of open-grown at density 0.4-0.5)
    # but reduces norway_spruce to a bottlebrush at EVERY density down to 0.2
    # (crown 0.22-0.39 of open, foliage hugging the stem, no conical taper) --
    # its monopodial architecture (add_only_on_end 1.0) collapses laterally
    # under sustained shade instead of narrowing. Conifers therefore keep
    # grow = false; broadleaves get true.
    surround_grow_per_species: dict[str, bool] = field(default_factory=dict)
    # Per-species shell density, for when one global value cannot serve the
    # set. The motivating case was measured BEFORE surround_grow_per_species
    # existed: at density 0.45 european_beech carried a 27.5 m crown at r08 --
    # wider than the widest beech in a 5,666-tree field dataset (19.7 m, Sharma
    # et al. 2017, Silva Fennica 51(5):1740) -- while at 0.75 it came in near
    # 14.5 m, and european_oak became a whip above ~0.5.
    #
    # The grow split fixed that case on its own: re-measured on the 2026-08-28
    # run (growpy-crown-metrics, h25m), beech is 29.8 m at r00 and 8.9 m at
    # r08, so the override table is empty. Kept because the knob is the right
    # place to correct a single species against published
    # crown-diameter/height ratios (spruce 0.22, beech 0.30) without moving the
    # global for everyone.
    surround_density_per_species: dict[str, float] = field(default_factory=dict)


    # Distance (m) beyond which a twig orphaned by the cutoff is pulled back
    # onto the surviving surface instead of left where Grove placed it.
    export_twig_reattach_threshold: float = 0.01
    # Restore the twigs build_cutoff_thickness deleted. False exports Grove's
    # surviving placements untouched, which is the reference for judging
    # whether compensation over- or under-fills the crown: with it off the
    # crown sits below Grove's true (cutoff-free) density, with it on it
    # approaches that density from underneath.
    export_twig_recovery: bool = True
    export_external_refs: bool = False
    # Reject a recovered twig once it lands closer than this fraction of the
    # tree's own median living-twig spacing to an already-placed twig, so
    # branches cut close together don't stack compensation twigs on top of
    # each other. 0 disables the guard.
    export_twig_min_spacing_ratio: float = 0.5
    export_youth_bias: float = 1.0
    export_density_variants: list = field(default_factory=list)
    density_variant_defs: dict[str, dict[str, Any]] = field(default_factory=dict)

    # [unreal]
    unreal_import_to_unreal: bool = True
    unreal_project_path: str = "/Game/GrowPy"
    unreal_voxelization: bool = True
    unreal_generate_wind_data: bool = True
    unreal_nanite_fallback_percent: float = 0.01
    unreal_nanite_fallback_target: str = "percent_triangles"
    unreal_nanite_lerp_uvs: bool = True
    unreal_db_path: str = "/Game/Assets/TheGrove"
    unreal_generate_pve_presets: bool = True
    # Content Browser base for the wind/PVE post-import scripts. Empty means
    # "follow unreal_project_path", which is what you want: assemblies import to
    # project_path, so wind data and PVE presets have to look for them there.
    # Set explicitly only to deliberately split them across two paths.
    unreal_pve_import_base: str = ""
    unreal_editor_exe: str = ""  # ue_exec auto-restart watchdog; empty = not configured
    unreal_uproject: str = ""  # ue_exec auto-restart watchdog; empty = not configured

    # [twigs] - interior decimation
    twigs_interior_edge_mm: float = 0.0
    twigs_interior_boundary_rings: int = 1

    # [helios]
    helios_export_obj: bool = False
    helios_helios_scene: bool = False
    helios_individual_obj: bool = False
    helios_obj_up_axis: str = "y"
    helios_classification: bool = False
    helios_simplification_enabled: bool = False
    helios_simplification_ratios: dict = field(default_factory=dict)
    helios_simplification_per_species: dict = field(default_factory=dict)

    # [calibration] -- growth-pacing calibration against yield tables.
    # Off by default: it costs two Grove passes per species and only matters
    # when several real trees are co-simulated in one grove (the CSV -> plot
    # path). Dataset production grows trees to height milestones, where pacing
    # does not affect the result.
    calibration_enabled: bool = False
    calibration_align_height: bool = True
    # DBH realisation at export. Independent of calibration: its input is the
    # height-DBH allometry artifact, which needs no simulation.
    export_dbh_from_allometry: bool = True
    calibration_plot: bool = True
    # Per-species overrides: {species_name: {site_index, flushes_per_year, ...}}
    calibration_species: dict[str, dict[str, Any]] = field(default_factory=dict)

    # [yield_sources]
    yield_sources_yield_tables_dir: Path = field(
        default_factory=lambda: Path("data/input/yield_tables")
    )
    yield_sources_store_dir: Path = field(
        default_factory=lambda: Path("data/input/yield_tables/store")
    )
    yield_sources_preferred_region: str = ""
    yield_sources_preferred_site_index: float | None = None
    # Per-provider source document for the yield-table providers that parse a
    # local file (PDF or XLSX). Keyed on the pylometree provider name, because
    # every PDF provider reads the same "pdf_path" key and so must be handed its
    # own config -- see _ingest_yield_tables in cli/create_growth_models.py.
    yield_sources_documents: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # An unset pve_import_base follows project_path. Before this, it carried
        # its own default, so any config that set project_path away from that
        # default silently sent the wind and PVE scripts to a path with no
        # assemblies in it -- no warning, no error, just assets that import fine
        # and then fail every wind/PVE check downstream.
        if not self.unreal_pve_import_base:
            self.unreal_pve_import_base = self.unreal_project_path

    # Conversion knobs shared by both twig profiles, in (config field, TOML key)
    # form. The compound profile mirrors each one with a `compound_` prefix.
    _TWIG_PROFILE_KEYS: ClassVar[tuple[str, ...]] = (
        "boundary_edge_mm",
        "planar_angle",
        "alpha_trim",
        "interior_edge_mm",
    )

    def get_twig_conversion_profile(
        self, role: str = "twig", explicit: Iterable[str] | None = None
    ) -> dict[str, float]:
        """Conversion settings for one output role (XRFF-359).

        Two roles share one pipeline:

        * ``"twig"`` -- a single small twig seen close up, the settings the
          dataset has always used.
        * ``"compound"`` -- a twig destined to be welded into a compound
          foliage part, where it is one of ~19 in the same mesh and much
          smaller on screen, so the close-range fidelity is wasted.

        Any compound key left unset falls back to its close-range value, so
        adding the role changes nothing until the profile is configured.

        Args:
            role: Which profile to resolve.
            explicit: Keys the caller set on the command line. `resolve()` has
                already written those onto the base fields, and a TOML compound
                value must not silently beat a flag the user typed -- every
                other flag in this CLI wins over TOML.
        """
        if role not in ("twig", "compound"):
            raise ValueError(
                f"unknown twig conversion role {role!r}; expected 'twig' or 'compound'"
            )

        typed = set(explicit or ())
        profile = {}
        for key in self._TWIG_PROFILE_KEYS:
            base = getattr(self, f"twigs_{key}")
            if role == "compound" and key not in typed:
                override = getattr(self, f"twigs_compound_{key}")
                if override is not None:
                    base = override
            profile[key] = base
        return profile

    @classmethod
    def from_toml(cls, toml_path: Path, set_as_global: bool = True) -> "GrowPyConfig":
        """Create config from a TOML file or directory.

        If ``toml_path`` is a directory, every ``*.toml`` inside is loaded in
        sorted order and deep-merged. If it's a file, every ``*.toml`` in the
        file's parent directory is loaded the same way. Only keys present in
        the merged result override dataclass defaults.
        """
        data = _load_toml_data(toml_path)

        kwargs: dict[str, Any] = {}

        # [general]
        general = data.get("general", {})
        if "random_seed" in general:
            kwargs["random_seed"] = general["random_seed"]
        if "csv_file" in general:
            kwargs["csv_file"] = Path(general["csv_file"])
        if "output_dir" in general:
            kwargs["output_dir"] = Path(general["output_dir"])
        if "verbose" in general:
            kwargs["verbose"] = general["verbose"]
        if "profile" in general:
            kwargs["profile"] = general["profile"]

        # [assets]
        assets = data.get("assets", {})
        if "grove_dir" in assets:
            kwargs["grove_dir"] = Path(assets["grove_dir"])
        if "resize_textures" in assets:
            kwargs["resize_textures"] = assets["resize_textures"]

        # [twigs]
        twigs = data.get("twigs", {})
        if "path" in twigs:
            kwargs["twigs_path"] = Path(twigs["path"])
        if "custom_twigs_dir" in twigs:
            kwargs["custom_twigs_dir"] = Path(twigs["custom_twigs_dir"])
        if "densify" in twigs:
            kwargs["twigs_densify"] = twigs["densify"]
        if "planar_angle" in twigs:
            kwargs["twigs_planar_angle"] = float(twigs["planar_angle"])
        if "planar_angle_per_twig" in twigs:
            kwargs["twigs_planar_angle_per_twig"] = {
                str(k): float(v) for k, v in twigs["planar_angle_per_twig"].items()
            }
        if "boundary_edge_mm_per_twig" in twigs:
            kwargs["twigs_boundary_edge_mm_per_twig"] = {
                str(k): float(v) for k, v in twigs["boundary_edge_mm_per_twig"].items()
            }
        if "alpha_trim" in twigs:
            kwargs["twigs_alpha_trim"] = twigs["alpha_trim"]
        if "boundary_edge_mm" in twigs:
            kwargs["twigs_boundary_edge_mm"] = twigs["boundary_edge_mm"]
        if "interior_edge_mm" in twigs:
            kwargs["twigs_interior_edge_mm"] = twigs["interior_edge_mm"]
        if "interior_boundary_rings" in twigs:
            kwargs["twigs_interior_boundary_rings"] = twigs["interior_boundary_rings"]
        # Compound-part conversion profile (XRFF-359); absent keys stay None
        # and fall back to the close-range values above.
        #
        # Spelled out rather than looped: test_config's drift guard
        # (test_toml_settable_fields_have_mapping_or_are_allowlisted) walks this
        # function's AST and only sees kwargs keys that are literal strings, so a
        # loop would make these four invisible to it and the TOML_ONLY_FIELDS
        # entries above inert.
        if "compound_boundary_edge_mm" in twigs:
            kwargs["twigs_compound_boundary_edge_mm"] = float(
                twigs["compound_boundary_edge_mm"]
            )
        if "compound_planar_angle" in twigs:
            kwargs["twigs_compound_planar_angle"] = float(twigs["compound_planar_angle"])
        if "compound_alpha_trim" in twigs:
            kwargs["twigs_compound_alpha_trim"] = float(twigs["compound_alpha_trim"])
        if "compound_interior_edge_mm" in twigs:
            kwargs["twigs_compound_interior_edge_mm"] = float(
                twigs["compound_interior_edge_mm"]
            )

        # [growth_models]
        gm = data.get("growth_models", {})
        if "cycles" in gm:
            kwargs["growth_models_cycles"] = gm["cycles"]
        if "seeds" in gm:
            kwargs["growth_models_seeds"] = gm["seeds"]
        if "height_threshold" in gm:
            kwargs["growth_models_height_threshold"] = gm["height_threshold"]
        if "max_cycles_without_growth" in gm:
            kwargs["growth_models_max_cycles_without_growth"] = gm[
                "max_cycles_without_growth"
            ]
        if "timeout" in gm:
            kwargs["growth_models_timeout"] = gm["timeout"]
        if "max_height" in gm:
            kwargs["growth_models_max_height"] = float(gm["max_height"])

        # [forest]
        forest = data.get("forest", {})
        if "quality" in forest:
            kwargs["forest_quality"] = forest["quality"]
        if "quality_above_height" in forest:
            kwargs["forest_quality_above_height"] = forest["quality_above_height"]
        if "quality_above_height_threshold" in forest:
            kwargs["forest_quality_above_height_threshold"] = float(
                forest["quality_above_height_threshold"]
            )
        if "growth_cycle_limit" in forest:
            kwargs["forest_growth_cycle_limit"] = forest["growth_cycle_limit"]
        if "plateau_cycles" in forest:
            kwargs["forest_plateau_cycles"] = forest["plateau_cycles"]
        if "smooth_iterations" in forest:
            kwargs["forest_smooth_iterations"] = forest["smooth_iterations"]
        if "include_grove_attributes" in forest:
            kwargs["forest_include_grove_attributes"] = forest[
                "include_grove_attributes"
            ]
        if "height_interval" in forest:
            kwargs["forest_height_interval"] = float(forest["height_interval"])
        if "max_height" in forest:
            kwargs["forest_max_height"] = float(forest["max_height"])
        # [export]
        export = data.get("export", {})
        if "usd_format" in export:
            fmt = export["usd_format"].lower()
            if fmt not in ("usda", "usdc"):
                raise ValueError(
                    f"export.usd_format must be 'usda' or 'usdc', got '{fmt}'"
                )
            kwargs["export_usd_format"] = fmt
        if "mode" in export:
            mode = export["mode"].lower()
            if mode not in ("unreal", "helios", "icons_only"):
                raise ValueError(
                    f"export.mode must be 'unreal', 'helios', or 'icons_only', "
                    f"got '{mode}'"
                )
            kwargs["export_mode"] = mode
        if "skeletal" in export:
            kwargs["export_skeletal"] = export["skeletal"]
        if "static" in export:
            kwargs["export_static"] = export["static"]
        if "max_skeleton_joints" in export:
            kwargs["export_max_skeleton_joints"] = int(export["max_skeleton_joints"])
        if "max_assembly_instances" in export:
            kwargs["export_max_assembly_instances"] = int(
                export["max_assembly_instances"]
            )
        if "skip_validation" in export:
            kwargs["export_skip_validation"] = export["skip_validation"]
        if "previews" in export:
            kwargs["export_previews"] = bool(export["previews"])
        if "export_control" in export:
            kwargs["export_control_images"] = bool(export["export_control"])
        if "icons" in export:
            kwargs["export_icons"] = bool(export["icons"])
        if "icon_components" in export:
            kwargs["export_icon_components"] = bool(export["icon_components"])
        # Deprecated alias: export.radial_scale -> export_dbh_from_allometry
        if "radial_scale" in export:
            kwargs["export_dbh_from_allometry"] = export["radial_scale"]
        if "twig_density" in export:
            kwargs["export_twig_density"] = float(export["twig_density"])
        if "build_cutoff_thickness_per_species" in export:
            kwargs["quality_build_cutoff_thickness_per_species"] = {
                str(k): float(v)
                for k, v in export["build_cutoff_thickness_per_species"].items()
            }
        if "twig_density_per_species" in export:
            kwargs["export_twig_density_per_species"] = {
                str(k): float(v) for k, v in export["twig_density_per_species"].items()
            }
        if "twig_reattach_threshold" in export:
            kwargs["export_twig_reattach_threshold"] = float(
                export["twig_reattach_threshold"]
            )
        if "twig_recovery" in export:
            kwargs["export_twig_recovery"] = bool(export["twig_recovery"])
        if "external_refs" in export:
            kwargs["export_external_refs"] = bool(export["external_refs"])
        if "twig_min_spacing_ratio" in export:
            kwargs["export_twig_min_spacing_ratio"] = float(
                export["twig_min_spacing_ratio"]
            )
        for _retired in ("twig_density_conifer", "twig_density_broadleaf"):
            if _retired in export:
                raise ValueError(
                    f"[export] {_retired} was retired: it was a hand-set guess at "
                    "how many twigs build_cutoff_thickness deletes, and the real "
                    "loss varies more within a growth habit than between habits. "
                    "Those twigs are now recovered from Grove directly. Use "
                    "[export] twig_density as a plain multiplier on natural "
                    "density (1.0 = as grown)."
                )
        if "youth_bias" in export:
            kwargs["export_youth_bias"] = export["youth_bias"]
        if "export_trees" in export:
            kwargs["forest_export_trees"] = export["export_trees"]
        if "density_variants" in export:
            kwargs["export_density_variants"] = export["density_variants"]

        # [density_variant.*] sections
        dv_section = data.get("density_variant", {})
        if dv_section:
            kwargs["density_variant_defs"] = {
                name: dict(cfg) for name, cfg in dv_section.items()
            }

        # [unreal]
        unreal = data.get("unreal", {})
        if "import_to_unreal" in unreal:
            kwargs["unreal_import_to_unreal"] = unreal["import_to_unreal"]
        if "project_path" in unreal:
            kwargs["unreal_project_path"] = unreal["project_path"]
        if "voxelization" in unreal:
            kwargs["unreal_voxelization"] = unreal["voxelization"]
        if "generate_wind_data" in unreal:
            kwargs["unreal_generate_wind_data"] = bool(unreal["generate_wind_data"])
        if "nanite_fallback_percent" in unreal:
            kwargs["unreal_nanite_fallback_percent"] = float(
                unreal["nanite_fallback_percent"]
            )
        if "nanite_lerp_uvs" in unreal:
            kwargs["unreal_nanite_lerp_uvs"] = unreal["nanite_lerp_uvs"]
        if "nanite_fallback_target" in unreal:
            kwargs["unreal_nanite_fallback_target"] = str(
                unreal["nanite_fallback_target"]
            ).lower()
        if "db_path" in unreal:
            kwargs["unreal_db_path"] = str(unreal["db_path"])
        if "generate_pve_presets" in unreal:
            kwargs["unreal_generate_pve_presets"] = bool(unreal["generate_pve_presets"])
            if kwargs["unreal_generate_pve_presets"]:
                # UPVPresetLoaderSettings is UCLASS(meta=(DeprecatedNode, ...))
                # on UE 5.8 and "produces no output", so the recipe JSON, the
                # preset DataAssets and the graphs wired to them are all built
                # for nothing. Warn rather than fail: UE 5.7 projects still work.
                logger.warning(
                    "[unreal] generate_pve_presets = true, but the PVE Preset "
                    "Loader node is deprecated and produces no output on UE 5.8+. "
                    "The current PVE route is [unreal.growth_data_json], which "
                    "emits a skeleton for the Growth Data JSON Importer instead."
                )
        if "pve_import_base" in unreal:
            kwargs["unreal_pve_import_base"] = str(unreal["pve_import_base"])
        watchdog = unreal.get("watchdog", {})
        if "editor_exe" in watchdog:
            kwargs["unreal_editor_exe"] = str(watchdog["editor_exe"])
        if "uproject" in watchdog:
            kwargs["unreal_uproject"] = str(watchdog["uproject"])

        # [helios]
        helios = data.get("helios", {})
        if "export_obj" in helios:
            kwargs["helios_export_obj"] = helios["export_obj"]
        if "helios_scene" in helios:
            kwargs["helios_helios_scene"] = helios["helios_scene"]
        if "individual_obj" in helios:
            kwargs["helios_individual_obj"] = helios["individual_obj"]
        if "obj_up_axis" in helios:
            kwargs["helios_obj_up_axis"] = helios["obj_up_axis"]
        if "classification" in helios:
            kwargs["helios_classification"] = bool(helios["classification"])
        simp = helios.get("simplification", {})
        if simp:
            kwargs["helios_simplification_enabled"] = simp.get("enabled", False)
            kwargs["helios_simplification_ratios"] = {
                "bark": simp.get("bark", 1.0),
                "wood": simp.get("wood", 1.0),
                "leaf": simp.get("leaf", 1.0),
                "fruit": simp.get("fruit", 1.0),
            }
            if "leaf_per_species" in simp:
                logger.warning(
                    "[helios.simplification.leaf_per_species] is renamed to "
                    "[helios.simplification.per_species.<species>] (covers "
                    "bark/wood/leaf/fruit, not just leaf); the leaf_per_species "
                    "key is ignored"
                )
            per_species = simp.get("per_species", {})
            if per_species:
                kwargs["helios_simplification_per_species"] = {
                    species: {k: float(v) for k, v in overrides.items()}
                    for species, overrides in per_species.items()
                }

        # [calibration]
        cal = data.get("calibration", {})
        if "enabled" in cal:
            kwargs["calibration_enabled"] = cal["enabled"]
        if "align_height" in cal:
            kwargs["calibration_align_height"] = cal["align_height"]
        if "plot" in cal:
            kwargs["calibration_plot"] = cal["plot"]
        if "align_dbh" in cal:
            # Deprecated alias: DBH realisation no longer belongs to calibration.
            kwargs["export_dbh_from_allometry"] = cal["align_dbh"]
        cal_species = cal.get("species", {})
        if cal_species:
            kwargs["calibration_species"] = {
                name: dict(cfg) for name, cfg in cal_species.items()
            }

        # [yield_sources]
        ys = data.get("yield_sources", {})
        if "store_dir" in ys:
            kwargs["yield_sources_store_dir"] = Path(ys["store_dir"])
        if "yield_tables_dir" in ys:
            kwargs["yield_sources_yield_tables_dir"] = Path(ys["yield_tables_dir"])
        if "preferred_region" in ys:
            kwargs["yield_sources_preferred_region"] = ys["preferred_region"]
        if "preferred_site_index" in ys:
            val = float(ys["preferred_site_index"])
            kwargs["yield_sources_preferred_site_index"] = val if val > 0 else None
        if "documents" in ys:
            kwargs["yield_sources_documents"] = {
                str(name): str(path) for name, path in ys["documents"].items()
            }
        # [surround] - single-tree competition shell (replaces multi-tree clusters).
        # radii: 0 = no surround (open-grown baseline); >0 = shell distance (m).
        # A tree's surround_radius value picks which configured radius applies.
        surr = data.get("surround", {})
        if "radii" in surr:
            # Take the list literally. This used to force 0.0 into every
            # configured set to guarantee an open-grown baseline, which made it
            # impossible to build one radius on its own: `radii = [5.0]` silently
            # became [0.0, 5.0]. That matters because generate_forest_stages
            # wipes each radius subdirectory before writing, so a run intended to
            # add r05 also DELETED an existing, complete r00 and regenerated it
            # under whatever config that run happened to carry. Observed
            # 2026-08-23: a shaded pass destroyed 15 finished r00 stage-cells,
            # and because it rewrote them the assembly count kept climbing while
            # data was being lost. Callers that want the baseline list 0.0.
            kwargs["surround_radii"] = sorted({float(r) for r in surr["radii"]})
        if "density" in surr:
            kwargs["surround_density"] = float(surr["density"])
        if "height" in surr:
            kwargs["surround_height"] = float(surr["height"])
        if "grow" in surr:
            kwargs["surround_grow"] = bool(surr["grow"])
        if "density_per_species" in surr:
            kwargs["surround_density_per_species"] = {
                str(k): float(v) for k, v in surr["density_per_species"].items()
            }
        if "grow_per_species" in surr:
            kwargs["surround_grow_per_species"] = {
                str(k): bool(v) for k, v in surr["grow_per_species"].items()
            }

        # Warn about unrecognized top-level sections (usually a typo in the TOML);
        # such sections are otherwise silently ignored and defaults are used.
        _known_sections = {
            "general",
            "assets",
            "twigs",
            "growth_models",
            "forest",
            "export",
            "density_variant",
            "unreal",
            "helios",
            "calibration",
            "yield_sources",
            "surround",
            "quality",
        }
        for _section in data:
            if _section not in _known_sections:
                logger.warning(
                    "Unrecognized config section [%s] in %s ignored (check for a typo)",
                    _section,
                    toml_path,
                )

        instance = cls(**kwargs)
        if set_as_global:
            set_global_config(instance)
        return instance

    def resolve(self, args: Any) -> "GrowPyConfig":
        """Merge CLI arguments over config values.

        Non-None CLI values override config. Returns self for chaining.
        Used by CLI scripts after argparse to layer CLI args over TOML config.

        Args:
            args: argparse.Namespace with CLI arguments.
                  Attribute names should match the CLI arg names (with underscores).
        """
        # Mapping: CLI arg name -> config field name (see CLI_MAPPINGS above).
        # Only override when the CLI value is not None (was explicitly provided)
        cli_mappings = self.CLI_MAPPINGS

        for cli_name, config_name in cli_mappings.items():
            cli_val = getattr(args, cli_name, None)
            if cli_val is not None:
                setattr(self, config_name, cli_val)

        # Special handling: --smooth-iterations comes from generate_forest.py
        # (convert_twigs.py no longer defines it — twigs have no smoothing step)
        si = getattr(args, "smooth_iterations", None)
        if si is not None:
            self.forest_smooth_iterations = si

        # Special handling: --export-trees is a comma-separated string from CLI
        et = getattr(args, "export_trees", None)
        if et is not None and isinstance(et, str):
            self.forest_export_trees = [int(x.strip()) for x in et.split(",")]

        return self

    @property
    def usd_ext(self) -> str:
        """File extension for USD output (e.g. '.usda' or '.usdc')."""
        return f".{self.export_usd_format}"

    def get_density_variants(self) -> list[tuple[str, dict[str, Any]]]:
        """Return [(variant_name, config_dict)] when active, else empty list.

        Each variant dict may only override keys in DENSITY_VARIANT_KEYS; an
        unknown key raises rather than silently doing nothing.
        """
        if not self.export_density_variants:
            return []
        result = []
        for name in self.export_density_variants:
            if name not in self.density_variant_defs:
                raise ValueError(
                    f"Density variant '{name}' not defined in [density_variant.{name}]"
                )
            vcfg = self.density_variant_defs[name]
            unknown = set(vcfg) - self.DENSITY_VARIANT_KEYS
            if unknown:
                raise ValueError(
                    f"Density variant '{name}' has unknown key(s) "
                    f"{sorted(unknown)}; valid overrides are "
                    f"{sorted(self.DENSITY_VARIANT_KEYS)}"
                )
            result.append((name, vcfg))
        return result

    def get_surround_density(self, species: str) -> float:
        """Shell density for this species, falling back to [surround] density."""
        from growpy.utils.naming import standardize_species_name

        if self.surround_density_per_species:
            key = standardize_species_name(species)
            if key in self.surround_density_per_species:
                return self.surround_density_per_species[key]
        return self.surround_density

    def get_surround_grow(self, species: str) -> bool:
        """Whether the surround shell tracks this species' height.

        Resolves ``[surround.grow_per_species]`` first, falling back to the
        global ``[surround] grow``. Accepts a common name ("Silver fir") or a
        standardized one ("silver_fir").
        """
        from growpy.utils.naming import standardize_species_name

        if self.surround_grow_per_species:
            key = standardize_species_name(species)
            if key in self.surround_grow_per_species:
                return self.surround_grow_per_species[key]
        return self.surround_grow

    def get_twig_density_base(self, species: str) -> float:
        """Return the crown-density multiplier relative to natural density.

        Resolves ``[export.twig_density_per_species]`` first, falling back to
        the global ``[export] twig_density``. Per-species values are required,
        not a nicety: measured 2026-08-06, the density each species needs to
        hit its literature leaf area spans ~60x (douglas_fir 0.016 vs
        common_ash 0.96), because it is dominated by how much leaf area that
        species' twig prototype carries -- 0.109 m2 for the shared fir spray
        against 0.023 m2 for ash -- not by Grove's placement. A single global
        constant is therefore wrong for almost every species at once.

        Accepts either a common name ("Silver fir") or an already-standardized
        one ("silver_fir"); both resolve to the same entry.
        """
        from growpy.utils.naming import standardize_species_name

        if self.export_twig_density_per_species:
            key = standardize_species_name(species)
            if key in self.export_twig_density_per_species:
                return self.export_twig_density_per_species[key]
        return self.export_twig_density

    def get_simplification_ratios(self, species_clean: str) -> dict[str, float]:
        """Return Helios OBJ simplification ratios for a species.

        Per-species overrides from [helios.simplification.per_species.<species>]
        are merged over the global bark/wood/leaf/fruit defaults. Unknown
        species or omitted materials fall back to the global values.
        """
        ratios = dict(self.helios_simplification_ratios)
        ratios.update(self.helios_simplification_per_species.get(species_clean, {}))
        return ratios

    # Delegator methods to module-level functions
    def get_preset_path(self, species: str) -> Path:
        """Get preset path for species."""
        from .paths import get_preset_path

        return get_preset_path(species)

    def get_growth_model_path(self, species: str) -> Path:
        """Get growth model path for species."""
        from .paths import get_growth_model_path

        return get_growth_model_path(species)

    @staticmethod
    def get_twig_files_by_type(species: str):
        """Get twig files organized by type."""
        from .paths import get_twig_files_by_type

        return get_twig_files_by_type(species)
