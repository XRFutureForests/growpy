from pathlib import Path

import bpy

twig_asset_path = (
    Path(__file__).parent.parent.parent.parent / "data" / "assets" / "twigs"
)


twig_assets = twig_asset_path.glob("**/*.blend")
for twig_asset in twig_assets:
    input_path = twig_asset
    output_path = twig_asset.with_suffix(".usda")

    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Clear existing objects in the scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.wm.open_mainfile(filepath=str(input_path), load_ui=False)
    collections = [col for col in bpy.data.collections if col.name != "Collection"]
    if len(collections) > 1:
        for col in collections:
            # Deselect all objects
            bpy.ops.object.select_all(action="DESELECT")
            # Select all objects in the collection
            for obj in col.objects:
                obj.select_set(True)
                # Set output path for this collection
                col_output_path = output_path.with_name(
                    f"{twig_asset.stem}_{col.name}_{obj.name}.usda"
                )
                bpy.ops.wm.usd_export(
                    filepath=str(col_output_path),
                    selected_objects_only=True,
                    visible_objects_only=True,
                    export_animation=False,
                    export_hair=False,
                    export_uvmaps=True,
                    export_mesh_colors=True,
                    export_normals=True,
                    export_materials=True,
                    export_armatures=False,
                    export_shapekeys=False,
                    export_subdivision="IGNORE",
                    export_textures=True,
                    relative_paths=True,
                )
                bpy.ops.object.select_all(action="DESELECT")
        # Skip the default export below
        continue
    bpy.ops.wm.usd_export(
        filepath=str(output_path),
        selected_objects_only=False,
        visible_objects_only=True,
        export_animation=False,
        export_hair=False,
        export_uvmaps=True,
        export_mesh_colors=True,
        export_normals=True,
        export_materials=True,
        export_armatures=False,
        export_shapekeys=False,
        export_subdivision="IGNORE",
        export_textures=True,
        relative_paths=True,
    )
