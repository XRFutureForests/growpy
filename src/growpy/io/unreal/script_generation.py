"""Single entry point for generating all Unreal Engine import/cleanup scripts.

Both ``growpy-generate-forest`` (standalone) and ``growpy-dataset-pipeline``
(step 4) call :func:`generate_unreal_scripts` so the two paths cannot drift
into producing different script sets for the same config.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from growpy.config.core import GrowPyConfig

logger = logging.getLogger(__name__)


def generate_unreal_scripts(
    output_dir: Path,
    config: "GrowPyConfig",
    *,
    include_static: bool = False,
) -> tuple[Path, Path]:
    """Generate all Unreal import/cleanup/PVE/wind/voxelize scripts.

    Call once after all species have been exported (never per-species, and
    never per parallel step-4 worker), to avoid concurrent script
    deletion/regeneration -- see ``--no-unreal-scripts`` at the CLI layer.

    Returns the (import_script, cleanup_script) paths.
    """
    from growpy.io.unreal.unreal_scripts import (
        generate_unreal_cleanup_script,
        generate_unreal_import_script,
    )
    from growpy.io.usd.assembly_export import create_combined_twig_usda

    instances_dir = output_dir / "Instances"
    if instances_dir.exists():
        combined = create_combined_twig_usda(
            instances_dir, include_static=include_static
        )
        if combined:
            logger.info("Created %d combined twig files for UE import", len(combined))

    nanite_cfg = {
        "voxelization": config.unreal_voxelization,
        "fallback_percent": config.unreal_nanite_fallback_percent,
        "fallback_target": config.unreal_nanite_fallback_target,
        "lerp_uvs": config.unreal_nanite_lerp_uvs,
    }

    import_script = generate_unreal_import_script(
        output_dir,
        config.unreal_project_path,
        include_static=include_static,
        voxelization=config.unreal_voxelization,
        nanite_cfg=nanite_cfg,
        db_path=config.unreal_db_path,
    )

    cleanup_script = generate_unreal_cleanup_script(
        output_dir,
        config.unreal_project_path,
        dry_run=True,
    )

    logger.info("Generated Unreal scripts: %s, %s", import_script, cleanup_script)

    # DynamicWind import script (runs before PVE to apply wind data first)
    if config.unreal_generate_wind_data:
        from growpy.io.unreal.wind_import_script import generate_wind_import_script

        wind_script = generate_wind_import_script(
            output_dir=output_dir / "unreal_scripts",
            forest_root=output_dir,
            import_base=config.unreal_pve_import_base,
        )
        logger.info("Generated DynamicWind import script: %s", wind_script)

    if config.unreal_generate_pve_presets:
        from growpy.io.unreal.pve_foliage_data import generate_all_foliage_data
        from growpy.io.unreal.pve_import_script import (
            build_species_twig_map,
            generate_pve_preset_import_script,
        )

        twig_map = build_species_twig_map()
        foliage_files = generate_all_foliage_data(
            output_dir,
            import_base=config.unreal_pve_import_base,
            species_twig_map=twig_map,
        )
        logger.info("Generated %d FoliageData.json files", len(foliage_files))
        pve_script = generate_pve_preset_import_script(
            output_dir=output_dir / "unreal_scripts",
            forest_root=output_dir,
            import_base=config.unreal_pve_import_base,
            species_twig_map=twig_map,
        )
        logger.info("Generated PVE preset import script: %s", pve_script)

        from growpy.io.unreal.pve_graph_script import generate_pve_graph_script

        pve_graph_script = generate_pve_graph_script(
            output_dir=output_dir / "unreal_scripts",
            forest_root=output_dir,
            import_base=config.unreal_pve_import_base,
            species_twig_map=twig_map,
        )
        logger.info("Generated PVE graph builder script: %s", pve_graph_script)

    # Nanite voxelize script (run after UE restart for best VRAM headroom)
    if config.unreal_import_to_unreal and config.unreal_voxelization:
        from growpy.io.unreal.nanite_voxelize_script import (
            generate_nanite_voxelize_script,
        )

        voxelize_script = generate_nanite_voxelize_script(
            output_dir=output_dir / "unreal_scripts",
            import_path=config.unreal_project_path,
        )
        logger.info("Generated Nanite voxelize script: %s", voxelize_script)

    return import_script, cleanup_script
