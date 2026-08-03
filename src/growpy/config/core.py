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
        "icons": "export_icons",
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
        "export_twig_density_conifer": "internal tuning, no CLI need identified",
        "export_twig_density_broadleaf": "internal tuning, no CLI need identified",
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
        "calibration_yield_tables_dir": "environment-level path, config-only",
        "calibration_species": "nested dict structure, config-only by design",
        "yield_sources_store_dir": "environment-level path, config-only by design",
        "yield_sources_preferred_region": "scenario-level setting, config-only",
        "yield_sources_preferred_site_index": "scenario-level setting, config-only",
        "surround_radii": "scenario-level setting, config-only by design",
        "surround_density": "scenario-level setting, config-only by design",
        "surround_height": "scenario-level setting, config-only by design",
        "surround_grow": "scenario-level setting, config-only by design",
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
    twigs_alpha_trim: float = 0.75
    twigs_boundary_edge_mm: float = 0.5

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
    # per-instance twig placement math bypass USD.
    export_mode: str = "unreal"
    export_skeletal: bool = True
    export_static: bool = False
    # Preview PNGs, export-control PNGs, and front/side/top icon PNGs are
    # generated once per tree (not per density variant). Both default true so
    # the current always-on behavior is unchanged -- see XRFF-290.
    export_previews: bool = True
    export_icons: bool = True
    export_max_skeleton_joints: int = 0  # 0 = no limit; 250 = Nanite Assembly USD
    export_max_assembly_instances: int = (
        0  # 0 = no limit; cap twig instances per assembly
    )
    export_skip_validation: bool = True
    # Base twig density multiplier. None (default) = auto-select by species
    # growth habit via export_twig_density_conifer / export_twig_density_broadleaf
    # (see tree_asset_lookup.csv Competition Group). Set explicitly in TOML to
    # override uniformly for all species, restoring the old single-value behavior.
    export_twig_density: float | None = None
    export_twig_density_conifer: float = 1.0
    export_twig_density_broadleaf: float = 2.5
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
    unreal_pve_import_base: str = "/Game/Assets/TheGrove"
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
    calibration_yield_tables_dir: Path = field(
        default_factory=lambda: Path("data/input/yield_tables")
    )
    # Per-species overrides: {species_name: {site_index, flushes_per_year, ...}}
    calibration_species: dict[str, dict[str, Any]] = field(default_factory=dict)

    # [yield_sources]
    yield_sources_store_dir: Path = field(
        default_factory=lambda: Path("data/input/yield_tables/store")
    )
    yield_sources_preferred_region: str = ""
    yield_sources_preferred_site_index: float | None = None

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
        if "alpha_trim" in twigs:
            kwargs["twigs_alpha_trim"] = twigs["alpha_trim"]
        if "boundary_edge_mm" in twigs:
            kwargs["twigs_boundary_edge_mm"] = twigs["boundary_edge_mm"]
        if "interior_edge_mm" in twigs:
            kwargs["twigs_interior_edge_mm"] = twigs["interior_edge_mm"]
        if "interior_boundary_rings" in twigs:
            kwargs["twigs_interior_boundary_rings"] = twigs["interior_boundary_rings"]

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
            if mode not in ("unreal", "helios"):
                raise ValueError(
                    f"export.mode must be 'unreal' or 'helios', got '{mode}'"
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
        if "icons" in export:
            kwargs["export_icons"] = bool(export["icons"])
        # Deprecated alias: export.radial_scale -> export_dbh_from_allometry
        if "radial_scale" in export:
            kwargs["export_dbh_from_allometry"] = export["radial_scale"]
        if "twig_density" in export:
            kwargs["export_twig_density"] = float(export["twig_density"])
        if "twig_density_conifer" in export:
            kwargs["export_twig_density_conifer"] = float(export["twig_density_conifer"])
        if "twig_density_broadleaf" in export:
            kwargs["export_twig_density_broadleaf"] = float(
                export["twig_density_broadleaf"]
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
        if "pve_import_base" in unreal:
            kwargs["unreal_pve_import_base"] = str(unreal["pve_import_base"])
        if "editor_exe" in unreal:
            kwargs["unreal_editor_exe"] = str(unreal["editor_exe"])
        if "uproject" in unreal:
            kwargs["unreal_uproject"] = str(unreal["uproject"])

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
        if "yield_tables_dir" in cal:
            kwargs["calibration_yield_tables_dir"] = Path(cal["yield_tables_dir"])
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
        if "preferred_region" in ys:
            kwargs["yield_sources_preferred_region"] = ys["preferred_region"]
        if "preferred_site_index" in ys:
            val = float(ys["preferred_site_index"])
            kwargs["yield_sources_preferred_site_index"] = val if val > 0 else None
        # [surround] - single-tree competition shell (replaces multi-tree clusters).
        # radii: 0 = no surround (open-grown baseline); >0 = shell distance (m).
        # A tree's surround_radius value picks which configured radius applies.
        surr = data.get("surround", {})
        if "radii" in surr:
            radii = {float(r) for r in surr["radii"]}
            radii.add(0.0)
            kwargs["surround_radii"] = sorted(radii)
        if "density" in surr:
            kwargs["surround_density"] = float(surr["density"])
        if "height" in surr:
            kwargs["surround_height"] = float(surr["height"])
        if "grow" in surr:
            kwargs["surround_grow"] = bool(surr["grow"])

        # Warn about unrecognized top-level sections (usually a typo in the TOML);
        # such sections are otherwise silently ignored and defaults are used.
        _known_sections = {
            "general", "assets", "twigs", "growth_models", "forest", "export",
            "density_variant", "unreal", "helios", "calibration", "yield_sources",
            "surround", "quality",
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
                    f"Density variant '{name}' not defined "
                    f"in [density_variant.{name}]"
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

    def get_twig_density_base(self, species: str) -> float:
        """Resolve the base twig-density multiplier for a species.

        An explicit ``export_twig_density`` (set via [export] twig_density in
        TOML) overrides everything uniformly, for back-compat with a single
        global knob. Otherwise the species' growth habit (conifer/broadleaf,
        from tree_asset_lookup.csv's Competition Group column) picks between
        export_twig_density_conifer and export_twig_density_broadleaf.
        Species without a resolvable growth habit fall back to the conifer
        value (the more conservative default).
        """
        if self.export_twig_density is not None:
            return self.export_twig_density

        from .paths import get_species_growth_habit

        habit = get_species_growth_habit(species)
        if habit == "broadleaf":
            return self.export_twig_density_broadleaf
        return self.export_twig_density_conifer

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
