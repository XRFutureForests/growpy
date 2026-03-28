"""Core configuration for GrowPy.

Central configuration loaded from growpy.toml with layered resolution:
    dataclass defaults -> growpy.toml -> CLI arguments
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

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
    grove_dir: Path = field(default_factory=lambda: Path("src/the_grove_22"))
    resize_textures: bool = False

    # [twigs]
    twigs_path: Path = field(default_factory=lambda: Path("data/assets/twigs"))
    twigs_densify: bool = True
    twigs_alpha_trim: float = 0.5
    twigs_smooth_boundary: bool = False
    twigs_smooth_iterations: int = 3
    twigs_smooth_factor: float = 0.5
    twigs_boundary_edge_mm: float = 0.5

    # [growth_models]
    growth_models_cycles: int = 125
    growth_models_seeds: int = 1
    growth_models_height_threshold: float = 0.05
    growth_models_max_cycles_without_growth: int = 3
    growth_models_timeout: int = 300

    # [forest]
    forest_quality: str = "ultra"
    forest_growth_cycle_limit: int = 10
    forest_smooth_iterations: int = 10
    forest_include_grove_attributes: bool = False
    forest_longevity_mode: bool = False

    # [forest.skeleton] - None means inherit from quality preset
    forest_skeleton_length: Optional[float] = None
    forest_skeleton_reduce: Optional[float] = None
    forest_skeleton_bias: Optional[float] = None
    forest_skeleton_connected: Optional[bool] = None

    # [export]
    export_skip_pve_json: bool = False
    export_skip_validation: bool = False
    export_include_static: bool = False
    export_fast: bool = False
    export_mode: str = "unreal"  # "unreal" (full USD+skeleton) or "helios" (direct OBJ, no bone limit)

    # [unreal]
    unreal_import_to_unreal: bool = False
    unreal_project_path: str = "/Game/GrowPy/Trees"

    # [twigs] - interior decimation
    twigs_interior_decimate_ratio: float = 0.0

    # [helios]
    helios_export_obj: bool = False
    helios_decimate_ratio: float = 0.3
    helios_stem_decimate_ratio: float = 0.1
    helios_helios_scene: bool = False
    helios_combined_obj: bool = False
    helios_classification: bool = False

    # [helios.simplification]
    helios_simplify: bool = False
    helios_simplify_bark: float = 1.0
    helios_simplify_wood: float = 1.0
    helios_simplify_leaf: float = 1.0
    helios_simplify_fruit: float = 1.0
    # [helios.simplification.leaf_per_species] - species_clean -> ratio
    helios_simplify_leaf_per_species: Dict[str, float] = field(default_factory=dict)

    def get_leaf_ratio(self, species_clean: str) -> float:
        """Return species-specific leaf ratio, falling back to global."""
        return self.helios_simplify_leaf_per_species.get(
            species_clean, self.helios_simplify_leaf
        )

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
        if "longevity_mode" in forest:
            kwargs["forest_longevity_mode"] = forest["longevity_mode"]

        # [forest.skeleton]
        skeleton = forest.get("skeleton", {})
        if "length" in skeleton:
            kwargs["forest_skeleton_length"] = skeleton["length"]
        if "reduce" in skeleton:
            kwargs["forest_skeleton_reduce"] = skeleton["reduce"]
        if "bias" in skeleton:
            kwargs["forest_skeleton_bias"] = skeleton["bias"]
        if "connected" in skeleton:
            kwargs["forest_skeleton_connected"] = skeleton["connected"]

        # [export]
        export = data.get("export", {})
        if "skip_pve_json" in export:
            kwargs["export_skip_pve_json"] = export["skip_pve_json"]
        if "skip_validation" in export:
            kwargs["export_skip_validation"] = export["skip_validation"]
        if "include_static" in export:
            kwargs["export_include_static"] = export["include_static"]
        if "fast" in export:
            kwargs["export_fast"] = export["fast"]
        if "mode" in export:
            kwargs["export_mode"] = export["mode"]

        # [unreal]
        unreal = data.get("unreal", {})
        if "import_to_unreal" in unreal:
            kwargs["unreal_import_to_unreal"] = unreal["import_to_unreal"]
        if "project_path" in unreal:
            kwargs["unreal_project_path"] = unreal["project_path"]

        # [helios]
        helios = data.get("helios", {})
        if "export_obj" in helios:
            kwargs["helios_export_obj"] = helios["export_obj"]
        if "twig_decimate_ratio" in helios:
            kwargs["helios_decimate_ratio"] = helios["twig_decimate_ratio"]
        if "stem_decimate_ratio" in helios:
            kwargs["helios_stem_decimate_ratio"] = helios["stem_decimate_ratio"]
        if "helios_scene" in helios:
            kwargs["helios_helios_scene"] = helios["helios_scene"]
        if "combined_obj" in helios:
            kwargs["helios_combined_obj"] = helios["combined_obj"]
        if "helios_classification" in helios:
            kwargs["helios_classification"] = helios["helios_classification"]

        # [helios.simplification]
        simplification = helios.get("simplification", {})
        if "enabled" in simplification:
            kwargs["helios_simplify"] = simplification["enabled"]
        if "bark" in simplification:
            kwargs["helios_simplify_bark"] = simplification["bark"]
        if "wood" in simplification:
            kwargs["helios_simplify_wood"] = simplification["wood"]
        if "leaf" in simplification:
            kwargs["helios_simplify_leaf"] = simplification["leaf"]
        if "fruit" in simplification:
            kwargs["helios_simplify_fruit"] = simplification["fruit"]
        leaf_per_species = simplification.get("leaf_per_species", {})
        if leaf_per_species:
            kwargs["helios_simplify_leaf_per_species"] = {
                k: float(v) for k, v in leaf_per_species.items()
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
            "output_dir": "output_dir",
            "verbose": "verbose",
            "profile": "profile",
            # [assets]
            "grove_dir": "grove_dir",
            "resize_textures": "resize_textures",
            # [twigs]
            "alpha_trim": "twigs_alpha_trim",
            "smooth_boundary": "twigs_smooth_boundary",
            "smooth_iterations": "twigs_smooth_iterations",
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
            "smooth_iterations": "forest_smooth_iterations",
            "include_grove_attributes": "forest_include_grove_attributes",
            "longevity_mode": "forest_longevity_mode",
            # [forest.skeleton]
            "skeleton_length": "forest_skeleton_length",
            "skeleton_reduce": "forest_skeleton_reduce",
            "skeleton_bias": "forest_skeleton_bias",
            "skeleton_connected": "forest_skeleton_connected",
            # [export]
            "skip_pve_json": "export_skip_pve_json",
            "skip_validation": "export_skip_validation",
            "include_static": "export_include_static",
            "fast": "export_fast",
            "export_mode": "export_mode",
            # [unreal]
            "import_to_unreal": "unreal_import_to_unreal",
            "unreal_project_path": "unreal_project_path",
            # [helios]
            "export_obj": "helios_export_obj",
            "twig_decimate_ratio": "helios_decimate_ratio",
            "stem_decimate_ratio": "helios_stem_decimate_ratio",
            "helios_scene": "helios_helios_scene",
            "combined_obj": "helios_combined_obj",
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

        # Special handling: --no-densify inverts the flag
        no_densify = getattr(args, "no_densify", None)
        if no_densify:
            self.twigs_densify = False

        # Special handling: --skeleton-connected comes as string "true"/"false" from CLI
        sc = getattr(args, "skeleton_connected", None)
        if sc is not None and isinstance(sc, str):
            self.forest_skeleton_connected = sc.lower() == "true"

        return self

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
