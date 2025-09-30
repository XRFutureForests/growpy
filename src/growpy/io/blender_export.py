"""Export for Grove tree models optimized for Unreal Engine 5 Nanite."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try to import bpy at module level
# Note: bpy must be imported BEFORE other modules in some contexts due to DLL dependencies
try:
    import bpy
    BPY_AVAILABLE = True
except (ImportError, OSError):
    # bpy not available or DLL load failed - this is expected when not using Blender Python
    bpy = None
    BPY_AVAILABLE = False

from ..utils import ensure_grove_available, gc
from ..config import get_config


def _check_bpy_available():
    """Check if bpy is available at runtime."""
    return BPY_AVAILABLE


def export_tree_as_fbx(
    grove,
    output_path: Path,
    species_name: str,
    include_skeleton: bool = True,
    export_skeleton_separately: bool = False
) -> bool:
    """Export Grove tree model as FBX with mesh, skeleton, and materials.

    Args:
        grove: Grove instance with simulated trees
        output_path: Path for the FBX file
        species_name: Tree species name for material naming
        include_skeleton: Whether to include skeleton in export
        export_skeleton_separately: Export skeleton as separate FBX file

    Returns:
        bool: Success status
    """
    if not _check_bpy_available():
        print("bpy module not available - cannot export FBX")
        return False

    ensure_grove_available()

    try:
        # Clear existing scene
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

        # Build high-quality tree model
        models = grove.build_models({
            "resolution": 16,  # High resolution
            "build_end_cap": True,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "resolution_reduce": 0.8
        })

        if not models:
            print("No models generated from grove")
            return False

        model = models[0]  # Take first tree

        # Create mesh from Grove model
        mesh_name = f"{species_name}_tree_mesh"
        mesh = bpy.data.meshes.new(mesh_name)

        # Get geometry data
        points = model.get_points_flat()
        faces = [[int(i) for i in face] for face in model.faces]
        uvs = model.get_uvs_flat() if hasattr(model, 'get_uvs_flat') else []

        # Convert points to vertices
        vertices = [(points[i], points[i+1], points[i+2]) for i in range(0, len(points), 3)]

        # Create mesh
        mesh.from_pydata(vertices, [], faces)
        mesh.update()

        # Add UVs if available
        if uvs and len(uvs) >= len(faces) * 6:  # At least 2 UV coords per triangle
            mesh.uv_layers.new(name="UVMap")
            uv_layer = mesh.uv_layers.active.data
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    uv_index = loop_index * 2
                    if uv_index + 1 < len(uvs):
                        uv_layer[loop_index].uv = (uvs[uv_index], uvs[uv_index + 1])

        # Create object
        obj = bpy.data.objects.new(mesh_name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Build skeleton
        armature_obj = None
        if include_skeleton or export_skeleton_separately:
            skeletons = grove.build_skeletons()
            if skeletons:
                armature_obj = _add_skeleton_to_object(obj, skeletons[0], species_name)

        # Add simple material
        _add_simple_material(obj, species_name)

        # Export skeleton separately if requested
        if export_skeleton_separately and armature_obj:
            skeleton_path = output_path.parent / f"{output_path.stem}_skeleton.fbx"
            bpy.ops.object.select_all(action='DESELECT')
            armature_obj.select_set(True)
            bpy.context.view_layer.objects.active = armature_obj

            bpy.ops.export_scene.fbx(
                filepath=str(skeleton_path),
                check_existing=True,
                use_selection=True,
                use_active_collection=False,
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_NONE',
                use_space_transform=True,
                bake_space_transform=False,
                object_types={'ARMATURE'},
                use_mesh_modifiers=False,
                add_leaf_bones=False,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=False,
                armature_nodetype='NULL',
                bake_anim=False
            )

        # Export mesh (with or without skeleton)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        if include_skeleton and armature_obj and not export_skeleton_separately:
            armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        output_path.parent.mkdir(parents=True, exist_ok=True)
        object_types = {'MESH', 'ARMATURE'} if (include_skeleton and not export_skeleton_separately) else {'MESH'}

        # Use FBX 2020.2 for UE5 compatibility
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            check_existing=True,
            use_selection=True,
            use_active_collection=False,
            global_scale=1.0,
            apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_NONE',
            use_space_transform=True,
            bake_space_transform=False,
            object_types=object_types,
            use_mesh_modifiers=True,
            use_mesh_modifiers_render=True,
            mesh_smooth_type='FACE',  # Face smoothing for better Nanite compatibility
            use_subsurf=False,
            use_mesh_edges=False,
            use_tspace=True,  # Enable tangent space for proper normal maps in UE
            use_custom_props=False,
            add_leaf_bones=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            use_armature_deform_only=False,
            armature_nodetype='NULL',
            bake_anim=False
        )

        return True

    except Exception as e:
        print(f"Failed to export tree FBX: {e}")
        return False


def export_tree_as_usd(
    grove,
    output_path: Path,
    species_name: str,
    include_skeleton: bool = True,
    export_skeleton_separately: bool = False
) -> bool:
    """Export Grove tree model as USD for Unreal Engine 5 Nanite.

    Args:
        grove: Grove instance with simulated trees
        output_path: Path for the USD file (.usd or .usda)
        species_name: Tree species name for material naming
        include_skeleton: Whether to include skeleton in export
        export_skeleton_separately: Export skeleton as separate USD file

    Returns:
        bool: Success status
    """
    if not _check_bpy_available():
        print("bpy module not available - cannot export USD")
        return False

    ensure_grove_available()

    try:
        # Clear existing scene
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

        # Build high-quality tree model
        models = grove.build_models({
            "resolution": 16,
            "build_end_cap": True,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "resolution_reduce": 0.8
        })

        if not models:
            print("No models generated from grove")
            return False

        model = models[0]

        # Create mesh
        mesh_name = f"{species_name}_tree_mesh"
        mesh = bpy.data.meshes.new(mesh_name)

        points = model.get_points_flat()
        faces = [[int(i) for i in face] for face in model.faces]
        uvs = model.get_uvs_flat() if hasattr(model, 'get_uvs_flat') else []

        vertices = [(points[i], points[i+1], points[i+2]) for i in range(0, len(points), 3)]

        mesh.from_pydata(vertices, [], faces)
        mesh.update()

        if uvs and len(uvs) >= len(faces) * 6:
            mesh.uv_layers.new(name="UVMap")
            uv_layer = mesh.uv_layers.active.data
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    uv_index = loop_index * 2
                    if uv_index + 1 < len(uvs):
                        uv_layer[loop_index].uv = (uvs[uv_index], uvs[uv_index + 1])

        obj = bpy.data.objects.new(mesh_name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Build skeleton
        armature_obj = None
        if include_skeleton or export_skeleton_separately:
            skeletons = grove.build_skeletons()
            if skeletons:
                armature_obj = _add_skeleton_to_object(obj, skeletons[0], species_name)

        # Add material
        _add_simple_material(obj, species_name)

        # Export skeleton separately if requested
        if export_skeleton_separately and armature_obj:
            skeleton_path = output_path.parent / f"{output_path.stem}_skeleton{output_path.suffix}"
            bpy.ops.object.select_all(action='DESELECT')
            armature_obj.select_set(True)
            bpy.context.view_layer.objects.active = armature_obj

            bpy.ops.wm.usd_export(
                filepath=str(skeleton_path),
                selected_objects_only=True,
                export_animation=False,
                export_armatures=True,
                export_shapekeys=False,
                use_instancing=False,
                evaluation_mode='RENDER'
            )

        # Export mesh (with or without skeleton)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        if include_skeleton and armature_obj and not export_skeleton_separately:
            armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # USD export optimized for Nanite
        bpy.ops.wm.usd_export(
            filepath=str(output_path),
            selected_objects_only=True,
            export_animation=False,
            export_armatures=(include_skeleton and not export_skeleton_separately),
            export_shapekeys=False,
            use_instancing=False,
            evaluation_mode='RENDER',
            generate_preview_surface=True,
            export_materials=True,
            export_uvmaps=True,
            export_normals=True
        )

        return True

    except Exception as e:
        print(f"Failed to export tree USD: {e}")
        return False


def create_nanite_assembly_usd(
    tree_mesh_path: Path,
    twig_mesh_paths: List[Path],
    output_assembly_path: Path,
    species_name: str
) -> bool:
    """Create a USD Assembly file for Unreal Engine 5.7 Nanite Assemblies.

    This generates a .usda file with proper Unreal API schemas that defines
    the hierarchical assembly composition with instancing for twigs.

    Args:
        tree_mesh_path: Path to main tree mesh USD file (trunk/branches)
        twig_mesh_paths: List of paths to twig/leaf USD mesh files
        output_assembly_path: Output path for assembly USDA file
        species_name: Tree species name

    Returns:
        bool: Success status
    """
    try:
        from pxr import Usd, UsdGeom, Sdf, Gf

        # Create new stage
        stage = Usd.Stage.CreateNew(str(output_assembly_path))

        # Define root prim with NaniteAssemblyRootAPI
        root_prim = stage.DefinePrim(f"/{species_name}_Assembly", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Add Unreal Nanite Assembly metadata
        root_prim.SetMetadata("apiSchemas", ["NaniteAssemblyRootAPI"])
        root_prim.CreateAttribute("unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token).Set("staticMesh")

        # Reference main tree mesh (trunk/branches)
        trunk_prim = stage.DefinePrim(f"/{species_name}_Assembly/Trunk", "Xform")
        trunk_prim.GetReferences().AddReference(str(tree_mesh_path.resolve()))
        trunk_prim.SetMetadata("apiSchemas", ["NaniteAssemblyExternalRefAPI"])

        # Add twig instances if provided
        if twig_mesh_paths:
            twigs_group = stage.DefinePrim(f"/{species_name}_Assembly/Twigs", "Xform")

            for idx, twig_path in enumerate(twig_mesh_paths):
                twig_prim = stage.DefinePrim(
                    f"/{species_name}_Assembly/Twigs/Twig_{idx}",
                    "Xform"
                )
                twig_prim.GetReferences().AddReference(str(twig_path.resolve()))
                twig_prim.SetMetadata("apiSchemas", ["NaniteAssemblyExternalRefAPI"])

        # Save stage
        stage.GetRootLayer().Save()
        return True

    except ImportError:
        print("USD Python (pxr) not available. Install with: pip install usd-core")
        return False
    except Exception as e:
        print(f"Failed to create Nanite Assembly USD: {e}")
        return False


def _add_skeleton_to_object(obj: Any, skeleton: Any, species_name: str) -> Any:
    """Add skeleton/armature to the tree object.

    Returns:
        The armature object created
    """
    try:
        # Create armature
        armature = bpy.data.armatures.new(f"{species_name}_armature")
        armature_obj = bpy.data.objects.new(f"{species_name}_skeleton", armature)
        bpy.context.collection.objects.link(armature_obj)

        # Enter edit mode to add bones
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Add bones from skeleton data
        points = skeleton.points
        poly_lines = skeleton.poly_lines

        for i, poly_line in enumerate(poly_lines):
            if len(poly_line) < 2:
                continue

            for j in range(len(poly_line) - 1):
                bone_name = f"bone_{i}_{j}"
                bone = armature.edit_bones.new(bone_name)

                start_idx = poly_line[j]
                end_idx = poly_line[j + 1]

                if start_idx < len(points) and end_idx < len(points):
                    bone.head = points[start_idx]
                    bone.tail = points[end_idx]

        bpy.ops.object.mode_set(mode='OBJECT')

        # Add armature modifier for proper deformation (don't use parent relationship for FBX export)
        modifier = obj.modifiers.new(name="Armature", type='ARMATURE')
        modifier.object = armature_obj
        modifier.use_vertex_groups = True

        # Create vertex groups for automatic weights (optional - can be improved)
        # For now, we just ensure the armature relationship is via modifier only

        return armature_obj

    except Exception as e:
        print(f"Failed to add skeleton: {e}")
        return None


def _add_simple_material(obj: Any, species_name: str) -> None:
    """Add simple material to tree object."""
    try:
        material = bpy.data.materials.new(name=f"{species_name}_bark")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        
        # Clear default nodes
        nodes.clear()
        
        # Add basic nodes
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        
        # Set brown bark color
        bsdf_node.inputs['Base Color'].default_value = (0.4, 0.3, 0.2, 1.0)
        bsdf_node.inputs['Roughness'].default_value = 0.8
        
        # Link nodes
        links = material.node_tree.links
        links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
        
        # Assign to object
        obj.data.materials.append(material)
        
    except Exception as e:
        print(f"Failed to add material: {e}")


def export_twigs_from_blend(
    blend_file_path: Path,
    output_dir: Path
) -> List[Path]:
    """Export all twig objects from a Blend file as individual FBX files.
    
    Args:
        blend_file_path: Path to the .blend file containing twigs
        output_dir: Directory to save individual twig FBX files
        
    Returns:
        List[Path]: Paths to exported FBX files
    """
    if not _check_bpy_available():
        print("bpy module not available - cannot export twigs")
        return []

    if not blend_file_path.exists():
        print(f"Blend file not found: {blend_file_path}")
        return []

    exported_files = []

    try:
        # Clear existing data to prevent memory issues
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Load the blend file
        bpy.ops.wm.open_mainfile(filepath=str(blend_file_path))

        # Find all mesh objects
        mesh_objects = [obj for obj in bpy.context.scene.objects
                       if obj.type == 'MESH' and obj.data]

        if not mesh_objects:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        
        for obj in mesh_objects:
            try:
                # Clear selection and select only this object
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Clean object name for filename
                clean_name = "".join(c for c in obj.name if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_name = clean_name.replace(' ', '_')
                if not clean_name:
                    clean_name = f"twig_{len(exported_files)}"

                fbx_path = output_dir / f"{clean_name}.fbx"
                
                # Try advanced export first, fallback to simple if it fails
                try:
                    # Export with materials and textures
                    bpy.ops.export_scene.fbx(
                        filepath=str(fbx_path),
                        check_existing=True,
                        use_selection=True,
                        use_active_collection=False,
                        global_scale=1.0,
                        apply_unit_scale=True,
                        apply_scale_options='FBX_SCALE_NONE',
                        use_space_transform=True,
                        bake_space_transform=False,
                        object_types={'MESH'},
                        use_mesh_modifiers=True,
                        use_mesh_modifiers_render=True,
                        mesh_smooth_type='FACE',
                        use_subsurf=False,
                        use_mesh_edges=False,
                        use_tspace=True,
                        use_custom_props=False,
                        path_mode='COPY',  # Copy textures to output directory
                        embed_textures=False,  # Don't embed to avoid issues
                        bake_anim=False
                    )
                except Exception as export_error:
                    print(f"Advanced export failed for {obj.name}, trying simple export: {export_error}")
                    # Fallback to minimal export settings
                    bpy.ops.export_scene.fbx(
                        filepath=str(fbx_path),
                        use_selection=True,
                        object_types={'MESH'},
                        global_scale=1.0
                    )

                exported_files.append(fbx_path)

            except Exception as e:
                continue
                
    except Exception as e:
        print(f"Failed to process blend file {blend_file_path}: {e}")
        
    return exported_files


def batch_export_tree_fbx(
    forest_data: Any,
    output_dir: Path,
    config: Optional[Any] = None
) -> List[Path]:
    """Export multiple trees from forest data as individual FBX files.

    Args:
        forest_data: Forest simulation data with species and positions
        output_dir: Directory to save tree FBX files
        config: GrowPy configuration

    Returns:
        List[Path]: Paths to exported FBX files
    """
    if config is None:
        config = get_config()

    exported_files = []
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get unique species
    species_list = forest_data['species'].unique() if hasattr(forest_data, 'unique') else set(forest_data.get('species', []))

    for species in species_list:
        try:
            from ..core.grove import create_grove
            from ..core.tree import build_grove_with_all_attributes

            # Create grove for this species
            grove = create_grove(species)

            # Add a single tree for this species (can be extended for multiple trees)
            grove.add_new_tree(
                gc.Vector(0, 0, 0),  # Center position
                gc.Vector(0, 0, 1),  # Up direction
                0  # No delay
            )

            # Simulate growth
            grove.simulate(flushes=10)  # Reasonable growth

            # Export as FBX
            species_clean = "".join(c for c in species if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            fbx_path = output_dir / f"{species_clean}_tree.fbx"

            if export_tree_as_fbx(grove, fbx_path, species, include_skeleton=True, export_skeleton_separately=False):
                exported_files.append(fbx_path)

        except Exception as e:
            print(f"Failed to export {species}: {e}")
            continue

    return exported_files


def batch_export_tree_usd(
    forest_data: Any,
    output_dir: Path,
    config: Optional[Any] = None
) -> List[Path]:
    """Export multiple trees from forest data as individual USD files.

    Args:
        forest_data: Forest simulation data with species and positions
        output_dir: Directory to save USD files
        config: GrowPy configuration

    Returns:
        List[Path]: Paths to exported USD files
    """
    if config is None:
        config = get_config()

    exported_files = []
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get unique species
    species_list = forest_data['species'].unique() if hasattr(forest_data, 'unique') else set(forest_data.get('species', []))

    for species in species_list:
        try:
            from ..core.grove import create_grove
            from ..core.tree import build_grove_with_all_attributes

            # Create grove for this species
            grove = create_grove(species)

            # Add a single tree for this species
            grove.add_new_tree(
                gc.Vector(0, 0, 0),
                gc.Vector(0, 0, 1),
                0
            )

            # Simulate growth
            grove.simulate(flushes=10)

            # Export as USD
            species_clean = "".join(c for c in species if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            usd_path = output_dir / f"{species_clean}_tree.usda"

            if export_tree_as_usd(grove, usd_path, species, include_skeleton=True, export_skeleton_separately=False):
                exported_files.append(usd_path)

        except Exception as e:
            print(f"Failed to export {species} as USD: {e}")
            continue

    return exported_files


def batch_export_trees_for_unreal(
    forest_data: Any,
    output_dir: Path,
    config: Optional[Any] = None,
    export_fbx: bool = True,
    export_usd: bool = True,
    num_variations: int = 3
) -> Dict[str, List[Path]]:
    """Export trees with all assets needed for Unreal Engine vegetation plugin.

    Creates multiple variations of each species for procedural variation in Unreal's
    PCG (Procedural Content Generation) and Foliage systems.

    Args:
        forest_data: Forest simulation data with species and positions
        output_dir: Base directory for exports
        config: GrowPy configuration
        export_fbx: Export FBX files
        export_usd: Export USD files
        num_variations: Number of variations per species for procedural diversity

    Returns:
        Dict with 'fbx', 'usd', and 'metadata' file paths
    """
    if config is None:
        config = get_config()

    import json

    results = {
        'fbx': [],
        'usd': [],
        'metadata': []
    }

    # Create output directories
    fbx_dir = output_dir / "FBX"
    usd_dir = output_dir / "USD"
    metadata_dir = output_dir / "Metadata"

    if export_fbx:
        fbx_dir.mkdir(parents=True, exist_ok=True)
    if export_usd:
        usd_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Get unique species
    species_list = forest_data['species'].unique() if hasattr(forest_data, 'unique') else set(forest_data.get('species', []))

    for species in species_list:
        try:
            from ..core.grove import create_grove

            species_clean = "".join(c for c in species if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            species_metadata = {
                'species': species,
                'variations': [],
                'recommended_settings': {
                    'min_spacing': 3.0,
                    'max_spacing': 8.0,
                    'scale_min': 0.8,
                    'scale_max': 1.2,
                    'rotation_random': True,
                    'align_to_normal': True
                }
            }

            # Create variations with different random seeds and parameters
            for variation_idx in range(num_variations):
                grove = create_grove(species)

                # Apply variation parameters to grove settings
                # Vary: lean angle, branch density, thickness variation
                if hasattr(grove, 'tree'):
                    tree = grove.tree

                    # Variation 0: Standard tree
                    # Variation 1: Leaning tree with thinner branches
                    # Variation 2: Upright tree with thicker branches
                    # etc.

                    if variation_idx == 1:
                        # Slightly leaning, more branches
                        if hasattr(tree, 'lean'):
                            tree.lean = 0.15
                        if hasattr(tree, 'branch_density'):
                            tree.branch_density *= 1.2
                        if hasattr(tree, 'thickness_variation'):
                            tree.thickness_variation = 0.9
                    elif variation_idx == 2:
                        # More upright, thicker trunk
                        if hasattr(tree, 'lean'):
                            tree.lean = 0.05
                        if hasattr(tree, 'thickness_variation'):
                            tree.thickness_variation = 1.1

                # Add tree with unique random seed (based on variation)
                import random
                random.seed(42 + variation_idx * 100)  # Deterministic but varied

                grove.add_new_tree(
                    gc.Vector(0, 0, 0),
                    gc.Vector(0, 0, 1),
                    0
                )

                # Simulate with slight variation in growth stages
                flush_count = 10 + (variation_idx % 3)  # Vary between 10-12 flushes
                grove.simulate(flushes=flush_count)

                variation_name = f"{species_clean}_var{variation_idx + 1}"

                # Export FBX
                if export_fbx:
                    fbx_path = fbx_dir / f"{variation_name}.fbx"
                    if export_tree_as_fbx(grove, fbx_path, species, include_skeleton=True, export_skeleton_separately=False):
                        results['fbx'].append(fbx_path)

                        # Document variation characteristics
                        variation_type = "standard"
                        if variation_idx == 1:
                            variation_type = "leaning_dense"
                        elif variation_idx == 2:
                            variation_type = "upright_thick"

                        species_metadata['variations'].append({
                            'name': variation_name,
                            'fbx': str(fbx_path.relative_to(output_dir)),
                            'variation_index': variation_idx,
                            'variation_type': variation_type,
                            'growth_flushes': flush_count
                        })

                # Export USD
                if export_usd:
                    usd_path = usd_dir / f"{variation_name}.usda"
                    if export_tree_as_usd(grove, usd_path, species, include_skeleton=True, export_skeleton_separately=False):
                        results['usd'].append(usd_path)
                        if species_metadata['variations']:
                            species_metadata['variations'][-1]['usd'] = str(usd_path.relative_to(output_dir))

            # Save species metadata
            metadata_path = metadata_dir / f"{species_clean}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(species_metadata, f, indent=2)
            results['metadata'].append(metadata_path)

            print(f"Exported {species}: {num_variations} variations")

        except Exception as e:
            print(f"Failed to export {species}: {e}")
            continue

    # Create master metadata file for Unreal import
    master_metadata = {
        'format_version': '1.0',
        'export_type': 'vegetation_assets',
        'species_count': len(species_list),
        'variations_per_species': num_variations,
        'species': [
            {
                'name': sp,
                'metadata_file': f"Metadata/{sp.replace(' ', '_')}_metadata.json"
            }
            for sp in species_list
        ],
        'unreal_import_notes': {
            'fbx_import': 'Import FBX files as Static Meshes with collision',
            'usd_import': 'Import USD files for Nanite-enabled assets (UE 5.7+)',
            'foliage_setup': 'Create Foliage Type assets for each variation',
            'pcg_setup': 'Use metadata for PCG scatter point attributes'
        }
    }

    master_path = output_dir / "import_metadata.json"
    with open(master_path, 'w') as f:
        json.dump(master_metadata, f, indent=2)
    results['metadata'].append(master_path)

    return results
