"""Simplified FBX export for Grove tree models and Blender twig assets.

This module provides a clean, simplified approach to exporting:
1. Tree models (mesh + skeleton + textures) as FBX
2. Twig assets from Blend files as individual FBX files

No complex USD/USDA handling, no multiple LOD levels, just high-quality single FBX exports.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import bpy
    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from .common import ensure_grove_available, gc
from .config import get_config


def export_tree_as_fbx(
    grove, 
    output_path: Path,
    species_name: str,
    include_skeleton: bool = True
) -> bool:
    """Export Grove tree model as FBX with mesh, skeleton, and materials.
    
    Args:
        grove: Grove instance with simulated trees
        output_path: Path for the FBX file
        species_name: Tree species name for material naming
        include_skeleton: Whether to include skeleton in export
        
    Returns:
        bool: Success status
    """
    if not BPY_AVAILABLE:
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
        
        # Add skeleton if requested
        if include_skeleton:
            skeletons = grove.build_skeletons()
            if skeletons:
                _add_skeleton_to_object(obj, skeletons[0], species_name)
        
        # Add simple material
        _add_simple_material(obj, species_name)
        
        # Export as FBX
        output_path.parent.mkdir(parents=True, exist_ok=True)
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
            object_types={'MESH', 'ARMATURE'},
            use_mesh_modifiers=True,
            use_mesh_modifiers_render=True,
            mesh_smooth_type='OFF',
            use_subsurf=False,
            use_mesh_edges=False,
            use_tspace=False,
            use_custom_props=False,
            add_leaf_bones=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            use_armature_deform_only=False,
            armature_nodetype='NULL',
            bake_anim=False
        )
        
        print(f"Exported tree FBX: {output_path}")
        return True
        
    except Exception as e:
        print(f"Failed to export tree FBX: {e}")
        return False


def _add_skeleton_to_object(obj: Any, skeleton: Any, species_name: str) -> None:
    """Add skeleton/armature to the tree object."""
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
        
        # Parent mesh to armature
        obj.parent = armature_obj
        obj.parent_type = 'ARMATURE_AUTO'
        
    except Exception as e:
        print(f"Failed to add skeleton: {e}")


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
    if not BPY_AVAILABLE:
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
            print(f"No mesh objects found in {blend_file_path}")
            return []

        print(f"Found {len(mesh_objects)} twig objects in {blend_file_path.name}")

        # Check materials
        materials_count = len([mat for mat in bpy.data.materials if mat])
        images_count = len([img for img in bpy.data.images if img])
        print(f"Found {materials_count} materials and {images_count} images in scene")

        output_dir.mkdir(parents=True, exist_ok=True)
        
        for obj in mesh_objects:
            try:
                # Clear selection and select only this object
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Check materials on this object
                obj_materials = [slot.material for slot in obj.material_slots if slot.material]
                print(f"Object '{obj.name}' has {len(obj_materials)} materials: {[mat.name for mat in obj_materials]}")

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
                print(f"Exported: {fbx_path}")
                
            except Exception as e:
                print(f"Failed to export {obj.name}: {e}")
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
            from .grove import create_grove
            from .tree import build_grove_with_all_attributes
            
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
            
            if export_tree_as_fbx(grove, fbx_path, species, include_skeleton=True):
                exported_files.append(fbx_path)
                
        except Exception as e:
            print(f"Failed to export {species}: {e}")
            continue
            
    return exported_files
