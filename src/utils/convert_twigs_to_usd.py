"""
Convert Grove twig .blend files to USD format with instancing support.

This utility converts all Grove twig .blend files to USD format with proper materials,
textures, and instancing prototypes. This is a one-time conversion process that
dramatically improves twig instancing performance during FBX export.

Usage:
    python src/utils/convert_twigs_to_usd.py --twigs_dir src/the_grove_22/twigs --output_dir data/twigs
Requirements:
    - Blender with bpy module
    - USD Python bindings (pxr module)
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import bpy
    import bmesh
    from mathutils import Vector as BlenderVector
    BLENDER_AVAILABLE = True
    logger.info("Blender (bpy) module imported successfully")
except ImportError as e:
    BLENDER_AVAILABLE = False
    logger.error(f"Blender (bpy) module not available: {e}")

try:
    from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt
    USD_AVAILABLE = True
    logger.info("USD (pxr) module imported successfully")
except ImportError as e:
    USD_AVAILABLE = False
    logger.error(f"USD (pxr) module not available: {e}")


class TwigToUSDConverter:
    """Converts Grove twig .blend files to USD prototypes."""
    
    # Supported texture types mapping - comprehensive patterns found in Grove twigs
    TEXTURE_MAPPING = {
        'diffuse': [
            'Diffuse.jpg', '_diffuse.png', '_diffuse.jpg',
            'Bottom.png', 'Top.png', 
            'FallBottom.png', 'FallTop.png',
            'SummerBottom.png', 'SummerTop.png',
            '.png', '.jpg'  # For single texture files like Bottlebrush.png
        ],
        'normal': [
            'Normal.jpg', '_normal.png', '_normals.png', '_normal.jpg',
            'TopNormal.png', 'TopBump.png', 'Bump.png',
            'FallBump.png', 'SummerBump.png'
        ],
        'alpha': [
            'Alpha.jpg', '_alpha.png', '_alpha.jpg', '_opacity.png',
            '_alpha_incuding_petioles.png'  # Special case for Hackberry
        ],
        'translucent': [
            'Translucent.jpg', '_translucent.png', '_translucent.jpg'
        ],
        'roughness': ['Roughness.jpg', '_roughness.png'],
        'metallic': ['Metallic.jpg', '_metallic.png']
    }
    
    def __init__(self, twigs_dir: Path, output_dir: Path):
        """
        Initialize the converter.
        
        Args:
            twigs_dir: Directory containing twig .blend files
            output_dir: Directory to save USD prototypes
        """
        self.twigs_dir = Path(twigs_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        self.prototypes_dir = self.output_dir / "prototypes"
        self.materials_dir = self.output_dir / "materials" 
        self.textures_dir = self.output_dir / "textures"
        
        for dir_path in [self.prototypes_dir, self.materials_dir, self.textures_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # Conversion results tracking
        self.conversion_results = {}
        
    def find_twig_directories(self) -> List[Path]:
        """
        Find all twig directories containing .blend files.
        
        Returns:
            List of twig directory paths
        """
        twig_dirs = []
        
        if not self.twigs_dir.exists():
            logger.error(f"Twigs directory not found: {self.twigs_dir}")
            return []
            
        for item in self.twigs_dir.iterdir():
            if item.is_dir():
                # Look for .blend files in this directory
                blend_files = list(item.glob("*.blend"))
                if blend_files:
                    twig_dirs.append(item)
                    
        logger.info(f"Found {len(twig_dirs)} twig directories")
        return twig_dirs
        
    def find_textures_for_twig(self, twig_dir: Path, species_name: str) -> Dict[str, Path]:
        """
        Find texture files for a twig species using comprehensive pattern matching.
        
        Args:
            twig_dir: Twig directory path
            species_name: Species name for texture matching
            
        Returns:
            Dictionary mapping texture type to file path
        """
        textures = {}
        texture_dir = twig_dir / "textures"
        
        # Check both main directory and textures subdirectory
        search_dirs = [twig_dir, texture_dir] if texture_dir.exists() else [twig_dir]
        
        # Extract base species name variations for better matching
        base_names = [
            species_name,  # Original: EuropeanBeech
            species_name.replace('Twig', '').replace('twig', ''),  # Remove Twig: EuropeanBeech
            twig_dir.name.replace('Twig', '').replace('twig', ''),  # From directory: EuropeanBeech
        ]
        
        # Add common shortened forms (e.g., EuropeanBeech -> Beech)
        for name in base_names.copy():
            if 'European' in name:
                base_names.append(name.replace('European', ''))
            if 'Japanese' in name:
                base_names.append(name.replace('Japanese', ''))
            if 'Common' in name:
                base_names.append(name.replace('Common', ''))
                
        for search_dir in search_dirs:
            for texture_type, patterns in self.TEXTURE_MAPPING.items():
                if texture_type in textures:
                    continue  # Already found
                    
                for pattern in patterns:
                    # Handle single texture files (e.g., Bottlebrush.png, EucalyptusGlobulus.png)
                    if pattern in ['.png', '.jpg']:
                        for ext in ['.png', '.jpg']:
                            for base_name in base_names:
                                # Try various combinations
                                possible_names = [
                                    f"{base_name}{ext}",
                                    f"{twig_dir.name.replace('Twig', '')}{ext}",
                                    # Special cases found in actual data
                                    f"EucalyptusGlobulus{ext}",  # BlueGumTwig
                                    f"Bottlebrush{ext}",        # BottlebrushTwig
                                    f"JapaneseCherry{ext}",     # JapaneseCherryTwig
                                    f"SaucerMagnolia{ext}",     # SaucerMagnoliaTwig
                                    f"ScotsPine{ext}",          # ScotsPineTwig
                                ]
                                
                                for name in possible_names:
                                    texture_path = search_dir / name
                                    if texture_path.exists():
                                        textures[texture_type] = texture_path
                                        break
                                if texture_type in textures:
                                    break
                            if texture_type in textures:
                                break
                        continue
                        
                    # Try different naming conventions for specific patterns
                    possible_names = []
                    
                    for base_name in base_names:
                        # Direct concatenation (BeechDiffuse.jpg)
                        possible_names.append(f"{base_name}{pattern}")
                        
                        # With species prefix (EuropeanBeechDiffuse.jpg - less common)
                        possible_names.append(f"{twig_dir.name.replace('Twig', '')}{pattern}")
                        
                        # Pattern without prefix (Bottom.png, Top.png, etc.)
                        possible_names.append(pattern.lstrip('_'))
                        
                        # Scientific name patterns (found in some twigs)
                        possible_names.extend([
                            f"AlnusGlutinosaLaciniata{pattern}",  # CutLeavedAlderTwig
                            f"SalixCaprea{pattern}",             # GoatWillowTwig
                            f"CeltisOccidentalis{pattern}",      # HackberryTwig
                            f"CorylusAvellana{pattern}",         # HazelTwig
                            f"AcerPalmatumAtropurpureum{pattern}", # JapeneseMapleAtropurpureumTwig
                            f"QuercusPalustris{pattern}",        # PinOakTwig
                            f"MagnoliaXSoulangeana{pattern}",    # SaucerMagnoliaSummerTwig
                            f"MalusSylvestris{pattern}",         # WildAppleTwig
                        ])
                        
                        # Handle seasonal variations
                        if 'Fall' in twig_dir.name:
                            possible_names.extend([
                                f"{base_name}Fall{pattern}",
                                f"{base_name.replace('Fall', '')}Fall{pattern}",
                            ])
                        if 'Summer' in twig_dir.name:
                            possible_names.extend([
                                f"{base_name}Summer{pattern}",
                                f"{base_name.replace('Summer', '')}Summer{pattern}",
                            ])
                    
                    # Check all possible names
                    for name in possible_names:
                        texture_path = search_dir / name
                        if texture_path.exists():
                            textures[texture_type] = texture_path
                            break
                    
                    if texture_type in textures:
                        break
                            
        logger.debug(f"Found {len(textures)} textures for {species_name}: {list(textures.keys())}")
        return textures
        
    def clear_blender_scene(self):
        """Clear all objects from Blender scene."""
        if not BLENDER_AVAILABLE:
            return
            
        try:
            # Select and delete all objects
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)
            
            # Clean up mesh data
            for mesh in bpy.data.meshes:
                bpy.data.meshes.remove(mesh)
                
            # Clean up materials  
            for material in bpy.data.materials:
                bpy.data.materials.remove(material)
                
            # Clean up textures
            for texture in bpy.data.textures:
                bpy.data.textures.remove(texture)
                
        except Exception as e:
            logger.warning(f"Error clearing Blender scene: {e}")
            
    def load_twig_from_blend(self, blend_path: Path) -> Optional[Tuple[str, Dict]]:
        """
        Load twig geometry and data from .blend file.
        
        Args:
            blend_path: Path to .blend file
            
        Returns:
            Tuple of (object_name, geometry_data) or None if failed
        """
        if not BLENDER_AVAILABLE:
            logger.error("Blender not available for .blend file loading")
            return None
            
        logger.info(f"Loading twig from: {blend_path.name}")
        start_time = time.time()
        
        try:
            # Clear scene first
            self.clear_blender_scene()
            
            # Simple approach: Just open the blend file directly 
            absolute_blend_path = str(blend_path.resolve())
            
            # Open blend file (this replaces current scene completely)
            bpy.ops.wm.open_mainfile(filepath=absolute_blend_path, load_ui=False)
            
            # Find the best mesh object (by vertex count)
            best_object = None
            max_vertices = 0
            
            for obj in bpy.data.objects:
                if obj and obj.type == 'MESH' and obj.data and len(obj.data.vertices) > 0:
                    vertex_count = len(obj.data.vertices)
                    if vertex_count > max_vertices:
                        max_vertices = vertex_count
                        best_object = obj
                        
            if not best_object:
                logger.warning(f"No mesh objects found in {blend_path.name}")
                return None
                
            # Make sure object is selected and active
            bpy.context.view_layer.objects.active = best_object
            best_object.select_set(True)
            
            # Create a bmesh instance to process the mesh data
            bm = bmesh.new()
            bm.from_mesh(best_object.data)
            
            # Triangulate the mesh to ensure consistent face structure
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            
            # Update the mesh
            bm.to_mesh(best_object.data)
            
            # Extract geometry data from bmesh (keep original scale - 20cm is correct for twigs)
            vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
            faces = [[f.verts[i].index for i in range(len(f.verts))] for f in bm.faces]
            normals = [(v.normal.x, v.normal.y, v.normal.z) for v in bm.verts]
            
            # Extract UVs if available
            uvs = []
            if bm.loops.layers.uv:
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    uvs = []
                    for face in bm.faces:
                        for loop in face.loops:
                            uv = loop[uv_layer].uv
                            uvs.append((uv.x, uv.y))
            
            bm.free()  # Clean up bmesh
            
            geometry_data = {
                'vertices': vertices,
                'faces': faces, 
                'normals': normals,
                'uvs': uvs,
                'vertex_count': len(vertices),
                'face_count': len(faces),
                'name': best_object.name
            }
            
            load_time = time.time() - start_time
            logger.info(f"Loaded twig '{best_object.name}': {len(vertices)} verts, {len(faces)} faces in {load_time:.2f}s")
            
            return (best_object.name, geometry_data)
            
        except Exception as e:
            load_time = time.time() - start_time
            logger.error(f"Failed to load {blend_path.name} after {load_time:.2f}s: {e}")
            return None
            
    def copy_texture_files(self, textures: Dict[str, Path], species_name: str) -> Dict[str, str]:
        """
        Copy texture files to output directory and return relative paths.
        
        Args:
            textures: Dictionary of texture type to source path
            species_name: Species name for naming
            
        Returns:
            Dictionary of texture type to relative USD path
        """
        copied_textures = {}
        
        for texture_type, source_path in textures.items():
            if not source_path.exists():
                continue
                
            # Create destination filename
            suffix = source_path.suffix
            dest_filename = f"{species_name}_{texture_type}{suffix}"
            dest_path = self.textures_dir / dest_filename
            
            try:
                # Copy file
                import shutil
                shutil.copy2(source_path, dest_path)
                
                # Store relative path for USD references (use textures/ for Blender compatibility)
                rel_path = f"textures/{dest_filename}"
                copied_textures[texture_type] = rel_path
                
                logger.debug(f"Copied texture: {source_path.name} -> {dest_filename}")
                
            except Exception as e:
                logger.warning(f"Failed to copy texture {source_path}: {e}")
                
        return copied_textures
        
    def create_usd_material(self, species_name: str, textures: Dict[str, str]) -> str:
        """
        Create USD material with textures.
        
        Args:
            species_name: Species name for material
            textures: Dictionary of texture type to USD path
            
        Returns:
            Path to created material USD file
        """
        if not USD_AVAILABLE:
            logger.error("USD not available for material creation")
            return ""
            
        material_path = self.materials_dir / f"{species_name}_material.usda"
        
        try:
            # Create USD stage
            stage = Usd.Stage.CreateNew(str(material_path))
            
            # Create material
            material_prim_path = f"/Materials/{species_name}_Material"
            material_prim = UsdShade.Material.Define(stage, material_prim_path)
            
            # Create shader
            shader_path = f"{material_prim_path}/Shader"
            shader = UsdShade.Shader.Define(stage, shader_path)
            shader.CreateIdAttr("UsdPreviewSurface")
            
            # Connect shader to material
            material_prim.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            
            # Set up textures
            if 'diffuse' in textures:
                # Create texture reader
                tex_path = f"{material_prim_path}/DiffuseTexture"
                tex_reader = UsdShade.Shader.Define(stage, tex_path)
                tex_reader.CreateIdAttr("UsdUVTexture")
                tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(textures['diffuse'])
                
                # Connect to shader
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    tex_reader.ConnectableAPI(), "rgb")
                    
            if 'normal' in textures:
                # Create normal texture reader
                normal_path = f"{material_prim_path}/NormalTexture"
                normal_reader = UsdShade.Shader.Define(stage, normal_path)
                normal_reader.CreateIdAttr("UsdUVTexture")
                normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(textures['normal'])
                
                # Connect to shader normal
                shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(
                    normal_reader.ConnectableAPI(), "rgb")
                    
            if 'alpha' in textures:
                # Create opacity texture reader
                alpha_path = f"{material_prim_path}/AlphaTexture"
                alpha_reader = UsdShade.Shader.Define(stage, alpha_path)
                alpha_reader.CreateIdAttr("UsdUVTexture")
                alpha_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(textures['alpha'])
                
                # Connect to shader opacity
                shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).ConnectToSource(
                    alpha_reader.ConnectableAPI(), "a")
                    
            # Set material properties
            if 'roughness' not in textures:
                shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)
            if 'metallic' not in textures:
                shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                
            # Save stage
            stage.Save()
            
            logger.info(f"Created USD material: {material_path.name}")
            return str(material_path)
            
        except Exception as e:
            logger.error(f"Failed to create USD material for {species_name}: {e}")
            return ""
            
    def create_usd_prototype(self, species_name: str, geometry_data: Dict, 
                           material_path: str) -> str:
        """
        Create USD prototype from geometry data.
        
        Args:
            species_name: Species name for prototype
            geometry_data: Geometry data from Blender
            material_path: Path to USD material file
            
        Returns:
            Path to created prototype USD file
        """
        if not USD_AVAILABLE:
            logger.error("USD not available for prototype creation")
            return ""
            
        prototype_path = self.prototypes_dir / f"{species_name}_prototype.usda"
        
        try:
            # Create USD stage
            stage = Usd.Stage.CreateNew(str(prototype_path))
            
            # Create root prim
            root_prim_path = f"/{species_name}_Prototype"
            root_prim = stage.DefinePrim(root_prim_path)
            stage.SetDefaultPrim(root_prim)
            
            # Create mesh
            mesh_path = f"{root_prim_path}/Mesh"
            mesh_prim = UsdGeom.Mesh.Define(stage, mesh_path)
            
            # Set geometry data
            vertices = geometry_data['vertices']
            faces = geometry_data['faces']
            
            # Convert to USD format
            points = Vt.Vec3fArray([Gf.Vec3f(v[0], v[1], v[2]) for v in vertices])
            face_vertex_indices = Vt.IntArray([idx for face in faces for idx in face])
            face_vertex_counts = Vt.IntArray([len(face) for face in faces])
            
            mesh_prim.CreatePointsAttr().Set(points)
            mesh_prim.CreateFaceVertexIndicesAttr().Set(face_vertex_indices) 
            mesh_prim.CreateFaceVertexCountsAttr().Set(face_vertex_counts)
            
            # Set normals if available
            if geometry_data['normals']:
                normals = Vt.Vec3fArray([Gf.Vec3f(n[0], n[1], n[2]) for n in geometry_data['normals']])
                mesh_prim.CreateNormalsAttr().Set(normals)
                mesh_prim.SetNormalsInterpolation("vertex")
                
            # Set UVs if available
            if geometry_data['uvs']:
                uvs = Vt.Vec2fArray([Gf.Vec2f(uv[0], uv[1]) for uv in geometry_data['uvs']])
                primvar = UsdGeom.PrimvarsAPI(mesh_prim).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray)
                primvar.Set(uvs)
                primvar.SetInterpolation("vertex")
                
            # Bind material if available (optional - don't fail if this doesn't work)
            if material_path and Path(material_path).exists():
                try:
                    # Reference the material using relative path
                    material_ref_path = f"../materials/{Path(material_path).name}"
                    stage.GetRootLayer().subLayerPaths.append(material_ref_path)
                    
                    # Bind material to mesh
                    binding_api = UsdShade.MaterialBindingAPI(mesh_prim)
                    material_prim_path = f"/Materials/{species_name}_Material"
                    material = UsdShade.Material(stage.GetPrimAtPath(material_prim_path))
                    binding_api.Bind(material)
                    
                    logger.debug(f"Successfully bound material for {species_name}")
                except Exception as e:
                    logger.warning(f"Failed to bind material for {species_name}: {e}. Continuing without material.")
                
            # Set metadata
            root_prim.SetMetadata("kind", "component")
            root_prim.SetDocumentation(f"Grove twig prototype for {species_name}")
            
            # Save stage
            stage.Save()
            
            logger.info(f"Created USD prototype: {prototype_path.name}")
            return str(prototype_path)
            
        except Exception as e:
            logger.error(f"Failed to create USD prototype for {species_name}: {e}")
            return ""
            
    def convert_twig_directory(self, twig_dir: Path) -> bool:
        """
        Convert a single twig directory to USD.
        
        Args:
            twig_dir: Path to twig directory
            
        Returns:
            True if successful, False otherwise
        """
        species_name = twig_dir.name.replace('Twig', '').replace('twig', '')
        logger.info(f"Converting twig: {species_name}")
        
        start_time = time.time()
        success = False
        
        try:
            # Find .blend files in directory
            blend_files = list(twig_dir.glob("*.blend"))
            if not blend_files:
                logger.warning(f"No .blend files found in {twig_dir.name}")
                return False
                
            # Use the main .blend file (usually matches directory name)
            main_blend = None
            for blend_file in blend_files:
                if blend_file.stem == twig_dir.name:
                    main_blend = blend_file
                    break
                    
            # If no exact match, use first .blend file
            if not main_blend:
                main_blend = blend_files[0]
                
            # Load geometry from .blend file
            twig_data = self.load_twig_from_blend(main_blend)
            if not twig_data:
                return False
                
            object_name, geometry_data = twig_data
            
            # Find textures
            textures = self.find_textures_for_twig(twig_dir, species_name)
            
            # Copy textures to output directory
            copied_textures = self.copy_texture_files(textures, species_name)
            
            # Create USD material
            material_path = ""
            if copied_textures:
                material_path = self.create_usd_material(species_name, copied_textures)
                
            # Create USD prototype
            prototype_path = self.create_usd_prototype(species_name, geometry_data, material_path)
            
            if prototype_path:
                success = True
                self.conversion_results[species_name] = {
                    'success': True,
                    'prototype_path': prototype_path,
                    'material_path': material_path,
                    'textures': list(copied_textures.keys()),
                    'vertex_count': geometry_data['vertex_count'],
                    'face_count': geometry_data['face_count']
                }
            else:
                self.conversion_results[species_name] = {'success': False, 'error': 'Failed to create prototype'}
                
        except Exception as e:
            logger.error(f"Error converting {species_name}: {e}")
            self.conversion_results[species_name] = {'success': False, 'error': str(e)}
            
        conversion_time = time.time() - start_time
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"Conversion {species_name}: {status} in {conversion_time:.2f}s")
        
        return success
        
    def convert_all_twigs(self) -> Dict[str, bool]:
        """
        Convert all twig directories to USD.
        
        Returns:
            Dictionary mapping species name to success status
        """
        if not BLENDER_AVAILABLE:
            logger.error("Blender not available - cannot convert .blend files")
            return {}
            
        if not USD_AVAILABLE:
            logger.error("USD not available - cannot create USD files")
            return {}
            
        logger.info("Starting conversion of all twig files to USD")
        start_time = time.time()
        
        # Find all twig directories
        twig_dirs = self.find_twig_directories()
        if not twig_dirs:
            logger.error("No twig directories found")
            return {}
            
        # Convert each directory
        results = {}
        successful = 0
        
        for i, twig_dir in enumerate(twig_dirs):
            logger.info(f"Processing {i+1}/{len(twig_dirs)}: {twig_dir.name}")
            
            success = self.convert_twig_directory(twig_dir)
            results[twig_dir.name] = success
            
            if success:
                successful += 1
                
        total_time = time.time() - start_time
        logger.info(f"Conversion completed: {successful}/{len(twig_dirs)} successful in {total_time:.2f}s")
        
        # Save conversion report
        self.save_conversion_report()
        
        return results
        
    def save_conversion_report(self):
        """Save detailed conversion report."""
        report_path = self.output_dir / "conversion_report.json"
        
        try:
            with open(report_path, 'w') as f:
                json.dump(self.conversion_results, f, indent=2)
                
            logger.info(f"Conversion report saved: {report_path}")
            
        except Exception as e:
            logger.error(f"Failed to save conversion report: {e}")


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Convert Grove twig .blend files to USD prototypes"
    )
    parser.add_argument(
        "--twigs_dir",
        type=Path,
        required=True,
        help="Directory containing twig .blend files"
    )
    parser.add_argument(
        "--output_dir", 
        type=Path,
        required=True,
        help="Directory to save USD prototypes"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Check requirements
    if not BLENDER_AVAILABLE:
        logger.error("Blender (bpy) module required but not available")
        logger.error("Install with: pip install bpy")
        return False
        
    if not USD_AVAILABLE:
        logger.error("USD (pxr) module required but not available") 
        logger.error("Install with: pip install usd-core")
        return False
        
    # Initialize converter
    converter = TwigToUSDConverter(args.twigs_dir, args.output_dir)
    
    # Convert all twigs
    results = converter.convert_all_twigs()
    
    # Report final results
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    if successful > 0:
        logger.info(f"Conversion successful: {successful}/{total} twigs converted")
        return True
    else:
        logger.error("Conversion failed: No twigs were successfully converted")
        return False


if __name__ == "__main__":
    main()