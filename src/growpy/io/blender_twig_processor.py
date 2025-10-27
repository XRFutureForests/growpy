#!/usr/bin/env python3
"""
Blender twig processor module - runs inside Blender Python environment.

This module is designed to be executed as a standalone script by Blender's Python
interpreter. It handles all Blender-specific operations for twig conversion,
including mesh processing, material setup, and export to USD formats.

Uses Blender's bundled USD (pxr) module via bpy.utils.expose_bundled_modules()
to add skeletons directly during export - no post-processing needed!

Texture Handling:
    - When both top and bottom diffuse textures exist, top texture is prioritized
    - This is a simplification - proper two-sided foliage would require advanced
      material setups
"""

import json
import shutil
import sys
from pathlib import Path

# Expose Blender's bundled USD module (Blender 4.4+)
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

        USD_AVAILABLE = True
    else:
        print("Warning: bpy.utils.expose_bundled_modules() not available")
        print("  Blender 4.4+ required for bundled USD support")
        USD_AVAILABLE = False
except ImportError as e:
    print(f"Warning: Could not import USD from Blender: {e}")
    USD_AVAILABLE = False


def add_skeleton_to_usd_file(usd_path, pivot_point=(0, 0, 0), clean_export=False):
    """Add skeleton to USD file using Blender's bundled pxr module.

    Args:
        usd_path: Path to USD file
        pivot_point: Root joint position (default: origin)
        clean_export: If True, creates minimal USD without default attributes

    Returns:
        bool: True if skeleton added successfully
    """
    if not USD_AVAILABLE:
        return False

    try:
        # Open existing stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"      [WARN] Could not open USD stage: {usd_path.name}")
            return False

        # Find mesh prim
        mesh_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh_prim = prim
                break

        if not mesh_prim:
            print(f"      [WARN] No mesh found in: {usd_path.name}")
            return False

        # Verify mesh has vertices
        mesh = UsdGeom.Mesh(mesh_prim)
        points = mesh.GetPointsAttr().Get()
        if not points or len(points) == 0:
            print(f"      [WARN] Mesh has no vertices: {usd_path.name}")
            return False

        # Create skeleton root
        root_path = Sdf.Path("/Twig")
        skel_root = UsdSkel.Root.Define(stage, root_path)

        # NOTE: Do NOT apply UnrealNaniteAssemblyRootAPI here
        # Twigs are referenced into Nanite Assemblies via PointInstancer.
        # Only the assembly root should have NaniteAssemblyRootAPI.

        # Create skeleton with single root joint
        # Use "Skel" naming to match Nanite Assembly requirements
        skel_path = root_path.AppendChild("Skel")
        skel = UsdSkel.Skeleton.Define(stage, skel_path)

        # Create single root joint at pivot point
        joint_tokens = ["root"]
        world_pos = Gf.Vec3d(pivot_point[0], pivot_point[1], pivot_point[2])

        # Bind transform (world space)
        bind_transform = Gf.Matrix4d(1.0)
        bind_transform.SetTranslateOnly(world_pos)

        # Rest transform (local space, same as bind since no parent)
        rest_transform = Gf.Matrix4d(1.0)
        rest_transform.SetTranslateOnly(world_pos)

        # Set skeleton attributes
        skel.CreateJointsAttr(joint_tokens)
        skel.CreateBindTransformsAttr(Vt.Matrix4dArray([bind_transform]))
        skel.CreateRestTransformsAttr(Vt.Matrix4dArray([rest_transform]))

        # CRITICAL: Add jointIndices topology array for proper Unreal Engine skeleton parsing
        # For a single-bone skeleton, [-1] indicates the root joint has no parent
        # Without this attribute, Unreal cannot properly interpret the skeleton hierarchy
        try:
            # Try using official API first (newer USD versions)
            skel.CreateJointIndicesAttr().Set(Vt.IntArray([-1]))
        except AttributeError:
            # Fallback for older USD versions (like Blender's bundled USD)
            joint_indices_attr = skel.GetPrim().CreateAttribute(
                "jointIndices",
                Sdf.ValueTypeNames.IntArray,
                custom=False,
                variability=Sdf.VariabilityUniform,
            )
            joint_indices_attr.Set(Vt.IntArray([-1]))  # Re-parent mesh under SkelRoot
        # Use "Mesh" naming to match Nanite Assembly requirements
        new_mesh_path = root_path.AppendChild("Mesh")
        old_mesh_path = mesh_prim.GetPath()

        # Copy mesh to new location
        Sdf.CopySpec(
            stage.GetRootLayer(), old_mesh_path, stage.GetRootLayer(), new_mesh_path
        )

        # Remove old mesh
        stage.RemovePrim(old_mesh_path)

        # Get the new mesh prim
        mesh_prim = stage.GetPrimAtPath(new_mesh_path)
        mesh = UsdGeom.Mesh(mesh_prim)

        # Bind mesh to skeleton
        # For clean export, manually set apiSchemas; otherwise use BindingAPI.Apply
        if clean_export:
            # Manually add SkelBindingAPI to apiSchemas for clean export
            api_schemas = mesh_prim.GetMetadata("apiSchemas") or Sdf.TokenListOp()
            if not isinstance(api_schemas, Sdf.TokenListOp):
                api_schemas = Sdf.TokenListOp()
            api_schemas.prependedItems = ["SkelBindingAPI"]
            mesh_prim.SetMetadata("apiSchemas", api_schemas)

            # Create skeleton relationship without custom qualifier
            skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
            skel_rel.SetTargets([skel_path])
        else:
            # Standard mode with materials: use BindingAPI.Apply
            binding_api = UsdSkel.BindingAPI.Apply(mesh_prim)
            binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Set skinning data - all vertices bound to root joint
        num_points = len(points)

        # All vertices use joint 0 (root) with full weight
        joint_indices = [0] * num_points
        joint_weights = [1.0] * num_points

        # Set skinning attributes
        if clean_export:
            # Use PrimvarsAPI directly for clean export
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

            joint_indices_primvar = primvars_api.CreatePrimvar(
                "skel:jointIndices",
                Sdf.ValueTypeNames.IntArray,
                UsdGeom.Tokens.vertex,
            )
            joint_indices_primvar.Set(joint_indices)
            joint_indices_primvar.SetElementSize(1)

            joint_weights_primvar = primvars_api.CreatePrimvar(
                "skel:jointWeights",
                Sdf.ValueTypeNames.FloatArray,
                UsdGeom.Tokens.vertex,
            )
            joint_weights_primvar.Set(joint_weights)
            joint_weights_primvar.SetElementSize(1)
        else:
            # Standard mode: use BindingAPI
            binding_api.CreateJointIndicesPrimvar(False, 1).Set(joint_indices)
            binding_api.CreateJointWeightsPrimvar(False, 1).Set(joint_weights)

        # Copy materials from /root/_materials/ to /Twig/_materials/ (only if not clean export)
        if not clean_export:
            from pxr import UsdShade

            materials_prim = stage.GetPrimAtPath("/root/_materials")
            if materials_prim and materials_prim.IsValid():
                new_materials_path = root_path.AppendChild("_materials")
                materials_scope = stage.DefinePrim(new_materials_path, "Scope")

                # Copy all material definitions
                for child in materials_prim.GetChildren():
                    new_mat_path = new_materials_path.AppendChild(child.GetName())
                    # Use CopySpec to copy entire material hierarchy
                    Sdf.CopySpec(
                        stage.GetRootLayer(),
                        child.GetPath(),
                        stage.GetRootLayer(),
                        new_mat_path,
                    )

                    # Update material binding paths in shader network
                    def update_material_paths(prim_path):
                        prim = stage.GetPrimAtPath(prim_path)
                        if not prim:
                            return
                        # Update all relationships that reference old material paths
                        for rel in prim.GetRelationships():
                            targets = rel.GetTargets()
                            if targets:
                                new_targets = []
                                for target in targets:
                                    target_str = str(target)
                                    if "/root/_materials/" in target_str:
                                        new_target_str = target_str.replace(
                                            "/root/_materials/",
                                            str(new_materials_path) + "/",
                                        )
                                        new_targets.append(Sdf.Path(new_target_str))
                                    else:
                                        new_targets.append(target)
                                rel.SetTargets(new_targets)
                        # Recursively update children
                        for child_prim in prim.GetChildren():
                            update_material_paths(child_prim.GetPath())

                    update_material_paths(new_mat_path)

                # Update mesh material binding to point to new location
                mat_binding_api = UsdShade.MaterialBindingAPI(mesh_prim)
                mat_binding = mat_binding_api.GetDirectBinding()
                if mat_binding:
                    mat_path = mat_binding.GetMaterialPath()
                    if mat_path and "/root/_materials/" in str(mat_path):
                        new_mat_path_str = str(mat_path).replace(
                            "/root/_materials/", str(new_materials_path) + "/"
                        )
                        new_mat_path = Sdf.Path(new_mat_path_str)
                        mat_prim = stage.GetPrimAtPath(new_mat_path)
                        if mat_prim and mat_prim.IsValid():
                            UsdShade.MaterialBindingAPI.Apply(mesh_prim).Bind(
                                UsdShade.Material(mat_prim)
                            )

        # CRITICAL: Remove the old /root prim that Blender created
        # We've already copied everything we need (/TwigMesh and /_materials) to /Twig
        # Leaving /root in the file confuses Unreal - it should only see /Twig (SkelRoot)
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            stage.RemovePrim(root_prim.GetPath())
            print(f"      [OK] Removed old /root prim (Blender export artifact)")

        # Set Twig as default prim so it's the primary reference target
        twig_prim = stage.GetPrimAtPath("/Twig")
        if twig_prim and twig_prim.IsValid():
            stage.SetDefaultPrim(twig_prim)

        # Save stage
        stage.Save()
        return True

    except Exception as e:
        print(f"      [ERROR] Adding skeleton: {e}")
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

        # If both diffuse_top and diffuse_bottom exist, prioritize top
        if "diffuse_top" in texture_map and "diffuse_bottom" in texture_map:
            # Use only top texture
            texture_map["diffuse"] = texture_map["diffuse_top"]
            del texture_map["diffuse_bottom"]
            print(f"      Note: Using top texture only (both top/bottom found)")
        elif "diffuse_top" in texture_map:
            # Rename diffuse_top to diffuse for standard connection
            texture_map["diffuse"] = texture_map["diffuse_top"]
            del texture_map["diffuse_top"]
        elif "diffuse_bottom" in texture_map:
            # Use bottom if that's all we have
            texture_map["diffuse"] = texture_map["diffuse_bottom"]
            del texture_map["diffuse_bottom"]

        print(f"      Material '{mat_name}': {list(texture_map.keys())}")

        # Debug: Show texture file names
        for tex_type, tex_path in texture_map.items():
            print(f"        - {tex_type}: {tex_path.name}")

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
                if tex_type == "diffuse":
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

                elif tex_type == "alpha":
                    # Alpha masks: use Non-Color for proper grayscale interpretation
                    tex_node.image.colorspace_settings.name = "Non-Color"

                    # Check if alpha needs inversion by examining filename
                    # Some alpha masks use white=transparent, others use black=transparent
                    needs_invert = any(
                        keyword in tex_path.stem.lower()
                        for keyword in ["mask", "cutout"]
                    )

                    if needs_invert:
                        # Invert the alpha (white becomes transparent)
                        invert_node = nodes.new("ShaderNodeInvert")
                        invert_node.location = (-200, y_offset)
                        links.new(
                            tex_node.outputs["Color"], invert_node.inputs["Color"]
                        )
                        links.new(invert_node.outputs["Color"], bsdf.inputs["Alpha"])
                    else:
                        # Direct connection (white=opaque, black=transparent)
                        links.new(tex_node.outputs["Color"], bsdf.inputs["Alpha"])

                    # Use CLIP mode for clean alpha cutout (works well in USD)
                    # This prevents the "layer" effect you're seeing
                    material.blend_method = "CLIP"
                    material.alpha_threshold = 0.5  # Hard cutoff for clean edges
                    material.show_transparent_back = True
                    if hasattr(material, "shadow_method"):
                        material.shadow_method = "CLIP"
                    material.use_backface_culling = False

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

        # CRITICAL: Enable two-sided rendering for leaf/twig materials
        # This ensures visibility from both sides
        material.use_backface_culling = False
        material["TwoSided"] = True

        obj.data.materials.append(material)
        materials_created += 1

    return materials_created > 0


def process_twig_file(
    blend_file, output_dir, formats, species_name, clean_export=False
):
    """Process a single twig blend file.

    Args:
        blend_file: Path to .blend file
        output_dir: Output directory for exported files
        formats: List of export formats
        species_name: Name of species
        clean_export: If True, creates minimal USD without materials/textures (demo mode)
    """
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

            # Note: UV coordinate fixes removed - they were breaking alpha channel
            # The texture orientation issue may be in the original texture files
            # or the way they're mapped in the original .blend files

            # Enable two-sided mesh rendering with smooth shading
            print(f"    -> Configuring mesh for two-sided rendering...")
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            # Recalculate normals to ensure they're consistent
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")

            # Note: use_auto_smooth removed in Blender 4.1+
            if hasattr(obj.data, "use_auto_smooth"):
                obj.data.use_auto_smooth = False
            for poly in obj.data.polygons:
                poly.use_smooth = True

            # Add custom properties for Unreal export
            obj["TwoSided"] = 1
            obj["DoubleSided"] = True
            obj.data["TwoSided"] = 1
            print(f"    -> Two-sided rendering configured")

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
                    # Export static mesh variant
                    export_path = output_dir / f"{standardized_name}.{fmt}"
                    print(f"    -> Exporting static USD: {export_path.name}")

                    bpy.ops.wm.usd_export(
                        filepath=str(export_path),
                        selected_objects_only=True,
                        export_materials=not clean_export,
                        export_textures=not clean_export,
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

                    # Export skeletal mesh variant
                    skel_export_path = output_dir / f"{standardized_name}_skel.{fmt}"
                    print(f"    -> Exporting skeletal USD: {skel_export_path.name}")

                    bpy.ops.wm.usd_export(
                        filepath=str(skel_export_path),
                        selected_objects_only=True,
                        export_materials=not clean_export,
                        export_textures=not clean_export,
                        export_uvmaps=True,
                        export_normals=True,
                        export_mesh_colors=True,
                        use_instancing=False,
                        evaluation_mode="RENDER",
                        generate_preview_surface=True,
                        relative_paths=True,
                        export_hair=False,
                    )

                    exported_files.append(skel_export_path)

                    # Add skeleton directly using Blender's bundled USD
                    print(f"    -> Adding skeleton to: {skel_export_path.name}")
                    if add_skeleton_to_usd_file(
                        skel_export_path,
                        pivot_point=(0.0, 0.0, 0.0),
                        clean_export=clean_export,
                    ):
                        print(f"    -> [OK] Skeleton added successfully")
                    else:
                        print(
                            f"    -> [WARN] Skeleton addition failed (will need manual step)"
                        )

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
    # Direct Python execution - standard argument parsing
    blend_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    formats = sys.argv[3].split(",")
    species_name = sys.argv[4]
    clean_export = "--clean-export" in sys.argv[5:] if len(sys.argv) > 5 else False

    output_dir.mkdir(parents=True, exist_ok=True)

    exported = process_twig_file(
        blend_file, output_dir, formats, species_name, clean_export
    )

    print("")
    print(f"[OK] Processed {len(exported)} file(s)")
