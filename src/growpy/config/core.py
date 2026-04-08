"""Core configuration for GrowPy.

Central configuration loaded from growpy.toml with layered resolution:
    dataclass defaults -> growpy.toml -> CLI arguments
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_global_config: Optional["GrowPyConfig"] = None


def get_global_config() -> Optional["GrowPyConfig"]:
    """Get the currently active global config instance."""
    return _global_config


def set_global_config(config: "GrowPyConfig") -> None:
    """Set the global config instance."""
    global _global_config
    _global_config = config


def _find_toml_path() -> Optional[Path]:
    """Find growpy.toml using search order: env var -> package dir -> cwd."""
    env_path = os.environ.get("GROWPY_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        return None

    # Look in the growpy package directory (src/growpy/growpy.toml)
    package_path = Path(__file__).resolve().parent.parent / "growpy.toml"
    if package_path.exists():
        return package_path

    # Fallback: current working directory
    cwd_path = Path.cwd() / "growpy.toml"
    if cwd_path.exists():
        return cwd_path

    return None


def get_config() -> "GrowPyConfig":
    """Get config instance, auto-loading from growpy.toml if available.

    Search order for TOML file:
        1. GROWPY_CONFIG environment variable
        2. src/growpy/growpy.toml (package directory)
        3. ./growpy.toml (current working directory)

    If no TOML file is found, returns dataclass defaults.
    """
    global _global_config
    if _global_config is None:
        toml_path = _find_toml_path()
        if toml_path:
            _global_config = GrowPyConfig.from_toml(toml_path, set_as_global=False)
        else:
            _global_config = GrowPyConfig()
    return _global_config


@dataclass
class GrowPyConfig:
    """Central configuration for GrowPy tree generation.

    All CLI scripts read defaults from this config. CLI arguments
    override config values via the resolve() method.
    """

    # [general]
    random_seed: Optional[int] = 42
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
    twigs_smooth_boundary: bool = True
    twigs_smooth_iterations: int = 10
    twigs_smooth_factor: float = 0.25
    twigs_boundary_edge_mm: float = 0.01

    # [growth_models]
    growth_models_cycles: int = 25
    growth_models_seeds: int = 1
    growth_models_height_threshold: float = 0.1
    growth_models_max_cycles_without_growth: int = 10
    growth_models_timeout: int = 900

    # [forest]
    forest_quality: str = "high"
    forest_growth_cycle_limit: int = 65
    forest_smooth_iterations: int = 10
    forest_include_grove_attributes: bool = False
    forest_height_interval: float = 5.0
    forest_max_height: float = 0.0  # 0 = no limit; >0 = cap tree heights (meters)
    forest_competition_distance_increase: float = 0.0  # meters per height interval
    forest_export_trees: list = field(default_factory=list)

    # [competition] - group-based spacing and thinning
    # Dict: group_name -> {species: [...], planting_distance: float, thinning: [[h, d], ...]}
    competition_groups: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    competition_default_group: str = "slow_broadleaf"

    # Skeleton overrides - None means inherit from quality preset (CLI-only)
    forest_skeleton_length: Optional[float] = None
    forest_skeleton_reduce: Optional[float] = None
    forest_skeleton_bias: Optional[float] = None
    forest_skeleton_connected: Optional[bool] = None

    # [export]
    export_usd_format: str = "usda"  # "usda" (ASCII) or "usdc" (binary)
    export_skeletal: bool = True
    export_static: bool = False
    export_max_skeleton_joints: int = 0  # 0 = no limit; 250 = Nanite Assembly USD
    export_skip_pve_json: bool = True
    export_skip_validation: bool = True
    export_twig_density: float = 1.0
    export_youth_bias: float = 1.0
    export_density_variants: list = field(default_factory=list)
    density_variant_defs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # [unreal]
    unreal_import_to_unreal: bool = True
    unreal_project_path: str = "/Game/GrowPy"
    unreal_voxelization: bool = True

    # [twigs] - interior decimation
    twigs_interior_decimate_ratio: float = 0.5

    # [helios]
    helios_export_obj: bool = False
    helios_helios_scene: bool = False
    helios_individual_obj: bool = False
    helios_obj_up_axis: str = "y"
    helios_simplification_enabled: bool = False
    helios_simplification_ratios: dict = field(default_factory=dict)
    helios_simplification_leaf_per_species: dict = field(default_factory=dict)

    # [calibration]
    calibration_enabled: bool = True
    calibration_align_height: bool = True
    calibration_align_dbh: bool = True
    calibration_plot: bool = True
    calibration_yield_tables_dir: Path = field(
        default_factory=lambda: Path("data/input/yield_tables")
    )
    # Per-species overrides: {species_name: {site_index, flushes_per_year, ...}}
    calibration_species: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # [yield_sources]
    yield_sources_store_dir: Path = field(
        default_factory=lambda: Path("data/input/yield_tables/store")
    )
    yield_sources_preferred_region: str = ""
    yield_sources_preferred_site_index: Optional[float] = None

    # [dataset]
    dataset_competition_neighbors: int = 3

    def get_competition_group(self, species_name: str) -> Dict[str, Any]:
        """Look up the competition group config for a species.

        Resolution order:
        1. Competition Group column in tree_asset_lookup.csv
        2. Falls back to competition_default_group

        Returns the group dict with keys: planting_distance, thinning.
        """
        group_name = self.competition_default_group

        try:
            from .paths import _find_species_row

            row = _find_species_row(species_name, use_gbif=False)
            csv_group = str(row.get("Competition Group", "")).strip()
            if csv_group:
                group_name = csv_group
        except (ValueError, KeyError):
            pass

        return self.competition_groups.get(
            group_name,
            {"planting_distance": 3.0, "thinning": []},
        )

    def get_thinning_target(
        self, species_name: str, height_m: float
    ) -> Optional[float]:
        """Get the thinning target distance for a species at a given height.

        Returns the target distance in meters, or None if no thinning
        schedule entry matches the given height.
        """
        group = self.get_competition_group(species_name)
        thinning = group.get("thinning", [])
        target = None
        for trigger_h, target_d in thinning:
            if height_m >= trigger_h:
                target = target_d
        return target

    @classmethod
    def from_toml(cls, toml_path: Path, set_as_global: bool = True) -> "GrowPyConfig":
        """Create config from a TOML file.

        Only keys present in the TOML override the dataclass defaults.
        """
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        kwargs: Dict[str, Any] = {}

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
        if "smooth_boundary" in twigs:
            kwargs["twigs_smooth_boundary"] = twigs["smooth_boundary"]
        if "smooth_iterations" in twigs:
            kwargs["twigs_smooth_iterations"] = twigs["smooth_iterations"]
        if "smooth_factor" in twigs:
            kwargs["twigs_smooth_factor"] = twigs["smooth_factor"]
        if "boundary_edge_mm" in twigs:
            kwargs["twigs_boundary_edge_mm"] = twigs["boundary_edge_mm"]
        if "interior_decimate_ratio" in twigs:
            kwargs["twigs_interior_decimate_ratio"] = twigs["interior_decimate_ratio"]

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

        # [forest]
        forest = data.get("forest", {})
        if "quality" in forest:
            kwargs["forest_quality"] = forest["quality"]
        if "growth_cycle_limit" in forest:
            kwargs["forest_growth_cycle_limit"] = forest["growth_cycle_limit"]
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
        if "competition_distance_increase" in forest:
            kwargs["forest_competition_distance_increase"] = float(
                forest["competition_distance_increase"]
            )
        # [export]
        export = data.get("export", {})
        if "usd_format" in export:
            fmt = export["usd_format"].lower()
            if fmt not in ("usda", "usdc"):
                raise ValueError(
                    f"export.usd_format must be 'usda' or 'usdc', got '{fmt}'"
                )
            kwargs["export_usd_format"] = fmt
        if "skeletal" in export:
            kwargs["export_skeletal"] = export["skeletal"]
        if "static" in export:
            kwargs["export_static"] = export["static"]
        if "max_skeleton_joints" in export:
            kwargs["export_max_skeleton_joints"] = int(export["max_skeleton_joints"])
        if "skip_pve_json" in export:
            kwargs["export_skip_pve_json"] = export["skip_pve_json"]
        if "skip_validation" in export:
            kwargs["export_skip_validation"] = export["skip_validation"]
        # Backward compat: export.radial_scale -> calibration_align_dbh
        if "radial_scale" in export:
            kwargs["calibration_align_dbh"] = export["radial_scale"]
        if "twig_density" in export:
            kwargs["export_twig_density"] = export["twig_density"]
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
        simp = helios.get("simplification", {})
        if simp:
            kwargs["helios_simplification_enabled"] = simp.get("enabled", False)
            kwargs["helios_simplification_ratios"] = {
                "bark": simp.get("bark", 1.0),
                "wood": simp.get("wood", 1.0),
                "leaf": simp.get("leaf", 1.0),
                "fruit": simp.get("fruit", 1.0),
            }
            kwargs["helios_simplification_leaf_per_species"] = simp.get(
                "leaf_per_species", {}
            )

        # [calibration]
        cal = data.get("calibration", {})
        if "enabled" in cal:
            kwargs["calibration_enabled"] = cal["enabled"]
        if "align_height" in cal:
            kwargs["calibration_align_height"] = cal["align_height"]
        if "align_dbh" in cal:
            kwargs["calibration_align_dbh"] = cal["align_dbh"]
        if "plot" in cal:
            kwargs["calibration_plot"] = cal["plot"]
        if "yield_tables_dir" in cal:
            kwargs["calibration_yield_tables_dir"] = Path(cal["yield_tables_dir"])
        # [calibration.species."Species Name"] -> {site_index, flushes_per_year, ...}
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

        # [dataset]
        dataset = data.get("dataset", {})
        if "competition_neighbors" in dataset:
            n = int(dataset["competition_neighbors"])
            if n not in (3, 4, 5, 6):
                raise ValueError(
                    f"dataset.competition_neighbors must be 3, 4, 5, or 6, got {n}"
                )
            kwargs["dataset_competition_neighbors"] = n

        # [competition]
        comp = data.get("competition", {})
        if "default_group" in comp:
            kwargs["competition_default_group"] = comp["default_group"]
        comp_groups = comp.get("groups", {})
        if comp_groups:
            kwargs["competition_groups"] = {
                name: dict(cfg) for name, cfg in comp_groups.items()
            }

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
        # Mapping: CLI arg name -> config field name
        # Only override when the CLI value is not None (was explicitly provided)
        cli_mappings = {
            # [general]
            "csv_file": "csv_file",
            "csv": "csv_file",
            "output_dir": "output_dir",
            "verbose": "verbose",
            "profile": "profile",
            # [assets]
            "grove_dir": "grove_dir",
            "resize_textures": "resize_textures",
            # [twigs] - uses "smooth_iterations" from convert_twigs.py argparse
            "alpha_trim": "twigs_alpha_trim",
            "smooth_boundary": "twigs_smooth_boundary",
            "smooth_factor": "twigs_smooth_factor",
            "boundary_edge_mm": "twigs_boundary_edge_mm",
            # [growth_models]
            "cycles": "growth_models_cycles",
            "seeds": "growth_models_seeds",
            "height_threshold": "growth_models_height_threshold",
            "max_cycles_without_growth": "growth_models_max_cycles_without_growth",
            "timeout": "growth_models_timeout",
            # [forest]
            "quality": "forest_quality",
            "growth_cycle_limit": "forest_growth_cycle_limit",
            "include_grove_attributes": "forest_include_grove_attributes",
            "height_interval": "forest_height_interval",
            "max_height": "forest_max_height",
            "competition_distance_increase": "forest_competition_distance_increase",
            # [forest.skeleton]
            "skeleton_length": "forest_skeleton_length",
            "skeleton_reduce": "forest_skeleton_reduce",
            "skeleton_bias": "forest_skeleton_bias",
            "skeleton_connected": "forest_skeleton_connected",
            # [export]
            "skeletal": "export_skeletal",
            "static": "export_static",
            "skip_pve_json": "export_skip_pve_json",
            "skip_validation": "export_skip_validation",
            # [unreal]
            "import_to_unreal": "unreal_import_to_unreal",
            "unreal_project_path": "unreal_project_path",
            # [helios]
            "export_obj": "helios_export_obj",
            "helios_scene": "helios_helios_scene",
            "individual_obj": "helios_individual_obj",
            "obj_up_axis": "helios_obj_up_axis",
            # [calibration]
            "calibrate": "calibration_enabled",
            "plot": "calibration_plot",
        }

        for cli_name, config_name in cli_mappings.items():
            cli_val = getattr(args, cli_name, None)
            if cli_val is not None:
                # For bool flags from store_true, they default to False (not None),
                # so only override if True
                if isinstance(cli_val, bool):
                    if cli_val:
                        setattr(self, config_name, cli_val)
                else:
                    setattr(self, config_name, cli_val)

        # Special handling: --smooth-iterations is used by both convert_twigs.py
        # and generate_forest.py. Resolve to the correct config field based on
        # which script is calling (detected by presence of script-specific args).
        si = getattr(args, "smooth_iterations", None)
        if si is not None:
            # generate_forest.py defines --quality; convert_twigs.py does not
            if hasattr(args, "quality"):
                self.forest_smooth_iterations = si
            else:
                self.twigs_smooth_iterations = si

        # Special handling: --no-densify inverts the flag
        no_densify = getattr(args, "no_densify", None)
        if no_densify:
            self.twigs_densify = False

        # Special handling: --no-skeletal / --no-static invert flags
        if getattr(args, "no_skeletal", None):
            self.export_skeletal = False
        if getattr(args, "no_static", None):
            self.export_static = False

        # Special handling: --skeleton-connected comes as string "true"/"false" from CLI
        sc = getattr(args, "skeleton_connected", None)
        if sc is not None and isinstance(sc, str):
            self.forest_skeleton_connected = sc.lower() == "true"

        # Special handling: --export-trees is a comma-separated string from CLI
        et = getattr(args, "export_trees", None)
        if et is not None and isinstance(et, str):
            self.forest_export_trees = [int(x.strip()) for x in et.split(",")]

        return self

    @property
    def usd_ext(self) -> str:
        """File extension for USD output (e.g. '.usda' or '.usdc')."""
        return f".{self.export_usd_format}"

    def get_density_variants(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Return [(variant_name, config_dict)] when active, else empty list."""
        if not self.export_density_variants:
            return []
        result = []
        for name in self.export_density_variants:
            if name not in self.density_variant_defs:
                raise ValueError(
                    f"Density variant '{name}' not defined "
                    f"in [density_variant.{name}]"
                )
            result.append((name, self.density_variant_defs[name]))
        return result

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
