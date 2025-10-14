#!/usr/bin/env python3
"""
Blender twig processor module - runs inside Blender Python environment.

This module is designed to be executed as a standalone script by Blender's Python
interpreter. It handles all Blender-specific operations for twig conversion,
including mesh processing, material setup, and export to FBX/USD formats.

CRITICAL: This module runs in Blender's Python environment, not the main conda env.
It must be self-contained and not import from growpy package (import cycles).
"""

import json
import shutil
import sys
from pathlib import Path


def _add_skeleton_to_twig_fbx(obj):
    """Add a simple single-bone skeleton to a twig for FBX export.

    Creates a single bone armature at origin for skeletal mesh export.
    All vertices are bound to this single bone.

    Args:
        obj: Blender mesh object to add skeleton to

    Returns:
        Armature object
    """
    import bpy

    try:
        # Create armature
        armature = bpy.data.armatures.new("TwigArmature")
        armature_obj = bpy.data.objects.new("TwigSkeleton", armature)
        bpy.context.collection.objects.link(armature_obj)

        # Position at origin for consistent coordinate system
        armature_obj.location = (0, 0, 0)

        # Calculate bone length from mesh bounds (prevents bone connection errors)
        # Use mesh extents to ensure bone is proportional to twig size
        mesh_bounds = [obj.dimensions[i] for i in range(3)]
        max_extent = max(mesh_bounds)
        # Bone length: 50% of max mesh extent, minimum 0.05m, maximum 0.5m
        # This ensures identical bone proportions between FBX and USD exports
        bone_length = max(0.05, min(0.5, max_extent * 0.5))

        # Enter edit mode to add bone
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Create single bone at origin with proper length
        # CRITICAL: Bone orientation must match USD skeleton for identical results
        bone = armature.edit_bones.new("Root")
        bone.head = (0, 0, 0)
        bone.tail = (0, 0, bone_length)  # Z-up orientation matches USD export

        bpy.ops.object.mode_set(mode="OBJECT")

        # Add armature modifier to mesh
        modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = armature_obj
        modifier.use_vertex_groups = True

        # Create vertex group for all vertices
        vgroup = obj.vertex_groups.new(name="Root")
        vertex_indices = [v.index for v in obj.data.vertices]
        vgroup.add(vertex_indices, 1.0, "REPLACE")  # Full weight

        return armature_obj

    except Exception as e:
        print(f"  Warning: Could not add skeleton to twig: {e}")
        return None


def _add_skeleton_to_twig_usd(usd_path):
    """Add a simple single-bone skeleton to a twig USD file.

    This makes the twig compatible with skeletal mesh Nanite Assemblies in Unreal.
    Creates a single bone at origin with the mesh bound to it.
    """
    try:
        # Expose bpy's bundled USD modules (Blender 4.4+)
        import bpy

        if hasattr(bpy.utils, "expose_bundled_modules"):
            bpy.utils.expose_bundled_modules()

        from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return False

        # Find the mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            return False

        # Get mesh and parent
        mesh = UsdGeom.Mesh(mesh_prim)
        original_mesh_path = mesh_prim.GetPath()
        parent_path = original_mesh_path.GetParentPath()

        # Create SkelRoot at parent level
        skel_root_path = parent_path.AppendChild("SkelRoot")
        skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)

        # Create simple skeleton with single bone at origin
        skel_path = skel_root_path.AppendChild("Skeleton")
        skel_prim = UsdSkel.Skeleton.Define(stage, skel_path)

        # Define single joint at origin
        joints = ["Root"]
        skel_prim.CreateJointsAttr(joints)

        # Bind transforms (identity matrix at origin)
        # CRITICAL: Must match FBX skeleton coordinate system exactly
        bind_transforms = [Gf.Matrix4d().SetIdentity()]
        skel_prim.CreateBindTransformsAttr(bind_transforms)

        # Rest transforms (same as bind) - ensures identical bind pose as FBX
        skel_prim.CreateRestTransformsAttr(bind_transforms)

        # CRITICAL: Create SkelAnimation for bind pose (required for Unreal skeletal mesh recognition)
        # Even single-bone skeletons need this for UE to recognize as skeletal mesh
        anim_path = skel_root_path.AppendChild("Animation")
        anim_prim = UsdSkel.Animation.Define(stage, anim_path)

        # Set animation joints (single joint)
        anim_prim.CreateJointsAttr(joints)

        # Set identity transforms for single bone (matching number of joints)
        # USD requires these arrays to have proper dimensions
        anim_prim.CreateTranslationsAttr(Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)]))
        anim_prim.CreateRotationsAttr(
            Vt.QuatfArray([Gf.Quatf(1, 0, 0, 0)])
        )  # w, x, y, z (identity quaternion)
        anim_prim.CreateScalesAttr(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)]))

        # Bind animation to skeleton
        skel_root_binding_api = UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())
        skel_root_binding_api.CreateAnimationSourceRel().SetTargets([anim_path])

        # Create new mesh prim inside SkelRoot
        new_mesh_path = skel_root_path.AppendChild(original_mesh_path.name)
        new_mesh_prim = stage.DefinePrim(new_mesh_path, "Mesh")

        # Copy all mesh attributes
        for attr in mesh_prim.GetAttributes():
            value = attr.Get()
            if value is not None:
                new_mesh_prim.CreateAttribute(attr.GetName(), attr.GetTypeName()).Set(
                    value
                )

        # Apply skeletal binding
        skel_binding_api = UsdSkel.BindingAPI.Apply(new_mesh_prim)
        skel_binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Get vertex count
        mesh_points = mesh.GetPointsAttr().Get()
        num_verts = len(mesh_points) if mesh_points else 0

        if num_verts > 0:
            # Bind all vertices to the single root joint with full weight
            joint_indices = Vt.IntArray([0] * num_verts)
            joint_weights = Vt.FloatArray([1.0] * num_verts)

            skel_binding_api.CreateJointIndicesPrimvar(False, 1).Set(joint_indices)
            skel_binding_api.CreateJointWeightsPrimvar(False, 1).Set(joint_weights)

        # Copy ALL material bindings (direct, collection, and inherited)
        # This ensures textures are properly mapped in Unreal
        old_mat_api = UsdShade.MaterialBindingAPI(mesh_prim)

        # Try direct binding first
        mat_binding = old_mat_api.GetDirectBinding()
        if mat_binding and mat_binding.GetMaterial():
            new_mat_api = UsdShade.MaterialBindingAPI.Apply(new_mesh_prim)
            new_mat_api.Bind(mat_binding.GetMaterial())
        else:
            # Try collection binding
            for purpose in [
                UsdShade.Tokens.allPurpose,
                UsdShade.Tokens.preview,
                UsdShade.Tokens.full,
            ]:
                collection_binding = old_mat_api.GetCollectionBinding(purpose)
                if collection_binding:
                    new_mat_api = UsdShade.MaterialBindingAPI.Apply(new_mesh_prim)
                    new_mat_api.Bind(collection_binding.GetMaterial(), purpose)
                    break

        # Remove original mesh
        stage.RemovePrim(original_mesh_path)

        # Set root as default prim (NOT SkelRoot!) so materials are accessible
        # This ensures materials in /root/_materials are visible when Unreal imports
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim:
            stage.SetDefaultPrim(root_prim)

        # Save
        stage.Save()
        return True

    except Exception as e:
        print(f"  Warning: Could not add skeleton to twig {Path(usd_path).name}: {e}")
        return False


def standardize_twig_name(original_name, species_name):
    """Standardize twig naming (matches main script logic)."""
    name_lower = original_name.lower()

    metadata = {
        "original_name": original_name,
        "species": species_name,
        "type": "generic",
        "variation": None,
        "season": None,
    }

    # Detect type
    if any(kw in name_lower for kw in ["apical", "end", "long", "terminal", "tip"]):
        metadata["type"] = "apical"
    elif any(kw in name_lower for kw in ["lateral", "side", "short", "laterall"]):
        metadata["type"] = "lateral"
    elif any(kw in name_lower for kw in ["upward", "up"]):
        metadata["type"] = "upward"
    elif any(kw in name_lower for kw in ["dead", "fall", "winter", "bare"]):
        metadata["type"] = "dead"
    elif any(kw in name_lower for kw in ["summer", "spring", "green"]):
        metadata["season"] = "summer"

    # Detect variation
    for letter in ["a", "b", "c", "d", "e"]:
        if any(
            pat in name_lower
            for pat in [
                f"var{letter}",
                f"variation{letter}",
                f"twig{letter}",
                f"{letter}twig",
            ]
        ):
            metadata["variation"] = letter
            break

    # Build name
    parts = [species_name.lower().replace(" ", "_")]

    if metadata["type"] != "generic":
        parts.append(metadata["type"])

    if metadata["variation"]:
        parts.append(f"var_{metadata['variation']}")

    if metadata["season"] and metadata["season"] != metadata["type"]:
        parts.append(metadata["season"])

    return "_".join(parts), metadata


def classify_texture_from_name(name):
    """Classify texture type from filename."""
    name_lower = name.lower()

    # Check modifiers
    if "top" in name_lower or "upper" in name_lower:
        if any(kw in name_lower for kw in ["diffuse", "albedo", "color"]):
            return "diffuse_top"
    if "bottom" in name_lower or "lower" in name_lower:
        if any(kw in name_lower for kw in ["diffuse", "albedo", "color"]):
            return "diffuse_bottom"

    # Standard types
    if any(kw in name_lower for kw in ["alpha", "opacity", "mask"]):
        return "alpha"
    if any(kw in name_lower for kw in ["normal", "norm", "bump"]):
        return "normal"
    if any(kw in name_lower for kw in ["translucent", "transmission", "sss"]):
        return "translucent"
    if any(kw in name_lower for kw in ["roughness", "rough"]):
        return "roughness"
    if any(kw in name_lower for kw in ["metallic", "metal"]):
        return "metallic"
    if "ao" in name_lower or "ambient" in name_lower:
        return "ao"

    return "diffuse"


def setup_materials_with_textures(obj, blend_dir, species_name, output_dir):
    """Setup materials with all available textures."""
    import bpy

    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]

    # Find textures
    search_dirs = [blend_dir / "textures", blend_dir, blend_dir.parent / "textures"]
    available_textures = []

    for search_dir in search_dirs:
        if not Path(search_dir).exists():
            continue
        for ext in texture_extensions:
            available_textures.extend(Path(search_dir).glob(f"*{ext}"))

    # Remove placeholders
    available_textures = [
        t
        for t in available_textures
        if not (t.stem.startswith("color_") and t.suffix == ".hdr")
    ]

    if not available_textures:
        print("      No textures found, using default material")
        return False

    # Clear existing materials
    obj.data.materials.clear()

    # Group existing materials by base name
    material_groups = {}
    existing_materials = list(bpy.data.materials)

    for texture in available_textures:
        # Find best material match
        mat_name = None
        for mat in existing_materials:
            if (
                mat.name.lower() in texture.stem.lower()
                or texture.stem.lower() in mat.name.lower()
            ):
                mat_name = mat.name
                break

        if not mat_name:
            # Create generic material name
            mat_name = species_name

        if mat_name not in material_groups:
            material_groups[mat_name] = []
        material_groups[mat_name].append(texture)

    # If no good grouping, use all textures for single material
    if not material_groups:
        material_groups[species_name] = available_textures

    # Create materials
    materials_created = 0

    for mat_name, textures in material_groups.items():
        material = bpy.data.materials.new(name=f"{species_name}_{mat_name}")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        nodes.clear()

        # Create base nodes
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (400, 0)

        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        # Classify and add textures
        texture_map = {}
        for tex in textures:
            tex_type = classify_texture_from_name(tex.stem)
            if tex_type not in texture_map:
                texture_map[tex_type] = tex

        print(f"      Material '{mat_name}': {list(texture_map.keys())}")

        # Add texture nodes
        y_offset = 300

        for tex_type, tex_path in texture_map.items():
            try:
                # CRITICAL: Copy texture to output directory for both FBX and USD
                # Then load from output directory so relative paths work correctly
                dest_tex = output_dir / tex_path.name
                if not dest_tex.exists():
                    shutil.copy2(tex_path, dest_tex)

                # Load texture from output directory (enables relative path export)
                # Both FBX and USD will reference textures in the same directory
                tex_node = nodes.new("ShaderNodeTexImage")
                tex_node.image = bpy.data.images.load(str(dest_tex.resolve()))
                # Make path relative to blend file location
                tex_node.image.filepath = f"//{dest_tex.name}"
                tex_node.location = (-400, y_offset)
                tex_node.label = tex_type.title()

                # Connect based on type
                if "diffuse" in tex_type:
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
                    if "diffuse_top" in tex_type:
                        tex_node.label = "Diffuse Top"

                elif tex_type == "alpha":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Alpha"])
                    material.blend_method = "CLIP"
                    if hasattr(material, "shadow_method"):
                        material.shadow_method = "CLIP"

                elif tex_type == "normal":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    normal_map = nodes.new("ShaderNodeNormalMap")
                    normal_map.location = (-200, y_offset - 100)
                    links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
                    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

                elif tex_type == "translucent":
                    # Transmission changed to Transmission Weight in newer Blender
                    if "Transmission" in bsdf.inputs:
                        links.new(
                            tex_node.outputs["Color"], bsdf.inputs["Transmission"]
                        )
                        bsdf.inputs["Transmission"].default_value = 0.3
                    elif "Transmission Weight" in bsdf.inputs:
                        links.new(
                            tex_node.outputs["Color"],
                            bsdf.inputs["Transmission Weight"],
                        )
                        bsdf.inputs["Transmission Weight"].default_value = 0.3

                elif tex_type == "roughness":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Roughness"])

                elif tex_type == "metallic":
                    tex_node.image.colorspace_settings.name = "Non-Color"
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Metallic"])

                elif tex_type == "ao":
                    # Multiply with base color
                    if "diffuse" in texture_map:
                        mix = nodes.new("ShaderNodeMixRGB")
                        mix.blend_type = "MULTIPLY"
                        mix.location = (-200, y_offset)
                        links.new(tex_node.outputs["Color"], mix.inputs[2])

                y_offset -= 250

            except Exception as e:
                print(f"      Warning: Could not load texture {tex_path.name}: {e}")

        # Set material properties for foliage
        # Specular changed to Specular IOR in Blender 4.x
        if "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.3
        elif "Specular IOR" in bsdf.inputs:
            bsdf.inputs["Specular IOR"].default_value = 0.5
        if "roughness" not in texture_map:
            bsdf.inputs["Roughness"].default_value = 0.7

        obj.data.materials.append(material)
        materials_created += 1

    return materials_created > 0


def process_twig_file(blend_file, output_dir, formats, species_name):
    """Process a single twig blend file."""
    import bpy

    print("")
    print(f"Processing: {Path(blend_file).name}")
    print(f"Species: {species_name}")

    # Load blend file
    bpy.ops.wm.open_mainfile(filepath=str(blend_file))

    blend_path = Path(blend_file)
    blend_dir = blend_path.parent

    # Find all mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]

    if not mesh_objects:
        print("  [WARN] No mesh objects found")
        return []

    print(f"  Found {len(mesh_objects)} mesh object(s)")

    exported_files = []
    texture_manifest = {}

    for obj in mesh_objects:
        try:
            # Clear selection
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            # Standardize object name
            original_name = obj.name
            standardized_name, metadata = standardize_twig_name(
                original_name, species_name
            )

            print(f"  Processing: {original_name}")
            print(f"    -> Standardized: {standardized_name}")
            print(
                f"    -> Type: {metadata['type']}, Variation: {metadata.get('variation', 'none')}"
            )

            # Center at origin
            obj.location = (0, 0, 0)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            # Triangulate mesh to avoid tangent space export warnings
            # This ensures all polygons are triangles before export
            print(f"    -> Triangulating mesh...")
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.quads_convert_to_tris(
                quad_method="BEAUTY", ngon_method="BEAUTY"
            )
            bpy.ops.object.mode_set(mode="OBJECT")
            print(f"    -> Triangulation complete")

            # Create mount point (empty at origin for Unreal PCG attachment)
            mount_point = bpy.data.objects.new(f"{standardized_name}_mount", None)
            mount_point.location = (0, 0, 0)
            mount_point.empty_display_type = "SPHERE"
            mount_point.empty_display_size = 0.01
            bpy.context.collection.objects.link(mount_point)

            # Parent mesh to mount point for proper hierarchy
            obj.parent = mount_point

            print(f"    -> Created mount point at origin")

            # Find and setup materials with textures
            # CRITICAL: Materials are created once and shared by ALL export formats
            # This ensures identical material/texture mapping in FBX and USD
            material_setup_success = setup_materials_with_textures(
                obj, blend_dir, species_name, output_dir
            )

            if material_setup_success:
                print(f"    -> Materials: {len(obj.data.materials)} with textures")
            else:
                print(f"    -> Materials: {len(obj.data.materials)} (fallback)")

            # Select mount point and mesh for export (hierarchical export)
            bpy.ops.object.select_all(action="DESELECT")
            mount_point.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = mount_point

            # Export in requested formats
            for fmt in formats:
                if fmt in ["usd", "usda"]:
                    export_path = output_dir / f"{standardized_name}.{fmt}"
                    print(f"    -> Exporting USD: {export_path.name}")

                    bpy.ops.wm.usd_export(
                        filepath=str(export_path),
                        selected_objects_only=True,
                        export_materials=True,
                        export_textures=True,
                        export_uvmaps=True,
                        export_normals=True,
                        export_mesh_colors=True,
                        use_instancing=False,
                        evaluation_mode="RENDER",
                        generate_preview_surface=True,
                        relative_paths=True,
                        export_hair=False,
                    )

                    exported_files.append(export_path)

                    # Create skeletal variant with single-bone skeleton
                    skeletal_path = output_dir / f"{standardized_name}_skeletal.{fmt}"
                    print(f"    -> Creating skeletal variant: {skeletal_path.name}")

                    shutil.copy2(export_path, skeletal_path)

                    if _add_skeleton_to_twig_usd(skeletal_path):
                        exported_files.append(skeletal_path)
                        print(
                            f"    -> [OK] Skeletal twig created (single-bone skeleton at origin)"
                        )
                    else:
                        print(f"    -> [WARN] Could not create skeletal variant")

                elif fmt == "fbx":
                    # Export static FBX
                    export_path = output_dir / f"{standardized_name}.fbx"
                    print(f"    -> Exporting FBX: {export_path.name}")

                    bpy.ops.export_scene.fbx(
                        filepath=str(export_path),
                        use_selection=True,
                        object_types={"MESH", "EMPTY"},
                        mesh_smooth_type="FACE",
                        use_mesh_modifiers=True,
                        use_mesh_edges=False,
                        use_tspace=True,
                        use_custom_props=True,
                        add_leaf_bones=False,
                        primary_bone_axis="Y",
                        secondary_bone_axis="X",
                        path_mode="COPY",
                        embed_textures=True,
                        batch_mode="OFF",
                        axis_forward="-Z",
                        axis_up="Y",
                        global_scale=1.0,
                        apply_scale_options="FBX_SCALE_ALL",
                    )

                    exported_files.append(export_path)

                    # Create skeletal FBX variant
                    skeletal_export_path = (
                        output_dir / f"{standardized_name}_skeletal.fbx"
                    )
                    print(
                        f"    -> Creating skeletal variant: {skeletal_export_path.name}"
                    )

                    # Add skeleton to mesh
                    armature_obj = _add_skeleton_to_twig_fbx(obj)

                    if armature_obj:
                        # Select both mesh and armature for export
                        bpy.ops.object.select_all(action="DESELECT")
                        mount_point.select_set(True)
                        obj.select_set(True)
                        armature_obj.select_set(True)
                        bpy.context.view_layer.objects.active = mount_point

                        # Export with skeleton
                        bpy.ops.export_scene.fbx(
                            filepath=str(skeletal_export_path),
                            use_selection=True,
                            object_types={"MESH", "EMPTY", "ARMATURE"},
                            mesh_smooth_type="FACE",
                            use_mesh_modifiers=True,
                            use_mesh_edges=False,
                            use_tspace=True,
                            use_custom_props=True,
                            add_leaf_bones=False,
                            primary_bone_axis="Y",
                            secondary_bone_axis="X",
                            bake_anim=True,
                            bake_anim_use_all_bones=True,
                            bake_anim_use_nla_strips=False,
                            bake_anim_step=1.0,
                            bake_anim_simplify_factor=0.0,
                            path_mode="COPY",
                            embed_textures=True,
                            batch_mode="OFF",
                            axis_forward="-Z",
                            axis_up="Y",
                            global_scale=1.0,
                            apply_scale_options="FBX_SCALE_ALL",
                        )

                        exported_files.append(skeletal_export_path)
                        print(
                            f"    -> [OK] Skeletal FBX created (single-bone skeleton at origin)"
                        )

                        # Clean up armature for next iteration
                        bpy.data.objects.remove(armature_obj, do_unlink=True)

                        # Remove modifier and vertex group from mesh
                        if "Armature" in [m.name for m in obj.modifiers]:
                            obj.modifiers.remove(obj.modifiers["Armature"])
                        if "Root" in obj.vertex_groups:
                            obj.vertex_groups.remove(obj.vertex_groups["Root"])
                    else:
                        print(f"    -> [WARN] Could not create skeletal FBX variant")

            # Store metadata
            texture_manifest[standardized_name] = {
                "original_name": original_name,
                "metadata": metadata,
                "materials": (
                    [mat.name for mat in obj.data.materials]
                    if obj.data.materials
                    else []
                ),
                "export_formats": formats,
            }

            print(f"    -> [OK] Exported successfully")

        except Exception as e:
            print(f"    -> [ERROR] {e}")
            continue

    # Save manifest
    if texture_manifest:
        manifest_path = output_dir / "twig_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(texture_manifest, f, indent=2)
        print("")
        print(f"  Saved manifest: {manifest_path.name}")

    return exported_files


if __name__ == "__main__":
    blend_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    formats = sys.argv[3].split(",")
    species_name = sys.argv[4]

    output_dir.mkdir(parents=True, exist_ok=True)

    exported = process_twig_file(blend_file, output_dir, formats, species_name)

    print("")
    print(f"[OK] Processed {len(exported)} file(s)")
