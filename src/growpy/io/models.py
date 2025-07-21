"""3D model input/output operations with USD twig instancing support."""

import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import the_grove_22_core as gc

try:
    from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False


def save_model(model, file_path: Path, format: str = "usd") -> None:
    """Save 3D model to USD file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format.lower() == "usd":
        model_string = gc.io.model_to_usda_string(model)
    else:
        raise ValueError(f"Only USD format is supported, got: {format}")
    
    with open(file_path, 'w') as f:
        f.write(model_string)


def save_multiple_models(models: List, file_paths: List[Path], 
                        format: str = "usd") -> List[Path]:
    """Save multiple models to USD files."""
    for model, file_path in zip(models, file_paths):
        save_model(model, file_path, format)
    return file_paths


def save_lod_models(grove: gc.Grove, species_name: str, output_dir: Path,
                   lod_configs: Dict[str, Dict[str, Any]], format: str = "usd") -> List[Path]:
    """
    Save models for all LOD levels.
    
    Args:
        grove: Grove object
        species_name: Species name for file naming
        output_dir: Directory to save models
        lod_configs: Dictionary of LOD configurations
        format: File format (only 'usd' supported)
        
    Returns:
        List of saved file paths
    """
    saved_files = []
    safe_species_name = species_name.replace(" ", "_").replace("_-_", "_")
    
    # Create species directory
    species_dir = output_dir / safe_species_name
    species_dir.mkdir(parents=True, exist_ok=True)
    
    for lod_name, lod_settings in lod_configs.items():
        # Build models for this LOD level
        models = grove.build_models(lod_settings)
        
        # Save each model
        for tree_index, model in enumerate(models):
            filename = f"{safe_species_name}_tree_{tree_index:03d}_{lod_name}.{format}"
            file_path = species_dir / filename
            
            save_model(model, file_path, format)
            saved_files.append(file_path)
    
    return saved_files


def load_model_data(file_path: Path) -> str:
    """Load model data from file."""
    with open(file_path, 'r') as f:
        return f.read()


def export_forest_models(forest_data, output_dir: Path, lod_configs: Dict[str, Dict], 
                        format: str = "usd", input_name: str = "forest") -> List[Path]:
    """Export models for all species in forest data."""
    models_dir = output_dir / input_name / "tree_models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    all_saved_files = []
    for grove, species_name, tree_count in forest_data:
        saved_files = save_lod_models(grove, species_name, models_dir, lod_configs, format)
        all_saved_files.extend(saved_files)
    
    return all_saved_files


class USDTwigInstancer:
    """Handles USD-based twig instancing for improved performance."""
    
    def __init__(self, twig_prototypes_dir: Optional[Path] = None):
        """
        Initialize USD twig instancer.
        
        Args:
            twig_prototypes_dir: Directory containing USD twig prototypes
        """
        if not USD_AVAILABLE:
            raise ImportError("USD (pxr) module required for twig instancing")
            
        if twig_prototypes_dir is None:
            possible_dirs = [
                Path.cwd() / "data" / "twig_prototypes",
                Path(__file__).parent.parent.parent / "data" / "twig_prototypes",
                Path.cwd() / "twig_prototypes"
            ]
            for dir_path in possible_dirs:
                if (dir_path / "prototypes").exists():
                    twig_prototypes_dir = dir_path
                    break
                    
        if twig_prototypes_dir is None:
            raise FileNotFoundError("Twig prototypes directory not found")
            
        self.prototypes_dir = Path(twig_prototypes_dir) / "prototypes"
        self.materials_dir = Path(twig_prototypes_dir) / "materials"
        self.prototype_cache = {}
        
    def find_species_prototype(self, species_name: str) -> Optional[Path]:
        """
        Find USD prototype file for a species.
        
        Args:
            species_name: Species name to find prototype for
            
        Returns:
            Path to prototype file or None if not found
        """
        # Clean species name for matching
        clean_name = species_name.replace(" ", "_").replace("_-_", "_")
        
        # Try exact match first
        prototype_path = self.prototypes_dir / f"{clean_name}_prototype.usda"
        if prototype_path.exists():
            return prototype_path
            
        # Try partial matches
        for prototype_file in self.prototypes_dir.glob("*_prototype.usda"):
            prototype_species = prototype_file.stem.replace("_prototype", "")
            if clean_name.lower() in prototype_species.lower():
                return prototype_file
                
        # Extract main species name (e.g., "Fagaceae - European oak" -> "oak")
        if " - " in species_name:
            main_species = species_name.split(" - ")[-1].replace(" ", "_")
            for prototype_file in self.prototypes_dir.glob("*_prototype.usda"):
                if main_species.lower() in prototype_file.stem.lower():
                    return prototype_file
        
        return None
        
    def calculate_triangle_center(self, model, face_indices: List[int]) -> Tuple[float, float, float]:
        """
        Calculate the center point of a triangle face.
        
        Args:
            model: Grove model object
            face_indices: List of vertex indices for the face
            
        Returns:
            Tuple of (x, y, z) coordinates
        """
        if len(face_indices) < 3:
            return (0.0, 0.0, 0.0)
            
        # Get the first 3 vertices to form a triangle
        v1 = model.points[face_indices[0]]
        v2 = model.points[face_indices[1]] 
        v3 = model.points[face_indices[2]]
        
        # Calculate centroid
        center_x = (v1.x + v2.x + v3.x) / 3.0
        center_y = (v1.y + v2.y + v3.y) / 3.0
        center_z = (v1.z + v2.z + v3.z) / 3.0
        
        return (center_x, center_y, center_z)
        
    def calculate_triangle_normal(self, model, face_indices: List[int]) -> Tuple[float, float, float]:
        """
        Calculate the normal vector of a triangle face.
        
        Args:
            model: Grove model object
            face_indices: List of vertex indices for the face
            
        Returns:
            Tuple of (x, y, z) normal vector (normalized)
        """
        if len(face_indices) < 3:
            return (1.0, 0.0, 0.0)  # Default X-axis forward
            
        # Get the first 3 vertices to form a triangle
        v1 = model.points[face_indices[0]]
        v2 = model.points[face_indices[1]]
        v3 = model.points[face_indices[2]]
        
        # Calculate two edge vectors
        edge1 = (v2.x - v1.x, v2.y - v1.y, v2.z - v1.z)
        edge2 = (v3.x - v1.x, v3.y - v1.y, v3.z - v1.z)
        
        # Calculate cross product (normal)
        normal_x = edge1[1] * edge2[2] - edge1[2] * edge2[1]
        normal_y = edge1[2] * edge2[0] - edge1[0] * edge2[2]  
        normal_z = edge1[0] * edge2[1] - edge1[1] * edge2[0]
        
        # Normalize
        length = math.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
        if length > 0:
            normal_x /= length
            normal_y /= length
            normal_z /= length
        else:
            return (1.0, 0.0, 0.0)  # Default X-axis forward
            
        return (normal_x, normal_y, normal_z)
        
    def extract_twig_placements(self, model, species_name: str) -> Dict[str, List[Dict]]:
        """
        Extract twig placement data from Grove model face attributes.
        
        Args:
            model: Grove model with face attributes
            species_name: Species name for logging
            
        Returns:
            Dictionary mapping twig type to list of placement data
        """
        placements = {
            'long': [],      # Apical/terminal twigs
            'short': [],     # Lateral/side twigs  
            'upward': [],    # Upward-facing twigs
            'dead': []       # Dead branch twigs
        }
        
        # Map face attributes to twig types
        twig_attributes = [
            ('long', getattr(model, 'face_attribute_twig_long', None)),
            ('short', getattr(model, 'face_attribute_twig_short', None)), 
            ('upward', getattr(model, 'face_attribute_twig_upward', None)),
            ('dead', getattr(model, 'face_attribute_twig_dead', None))
        ]
        
        for twig_type, face_attributes in twig_attributes:
            if not face_attributes:
                continue
                
            max_faces = min(len(face_attributes), len(model.faces))
            
            for face_index in range(max_faces):
                if face_attributes[face_index]:
                    # Calculate placement transform
                    face_indices = model.faces[face_index]
                    center = self.calculate_triangle_center(model, face_indices)
                    normal = self.calculate_triangle_normal(model, face_indices)
                    
                    placement = {
                        'position': center,
                        'normal': normal,
                        'face_index': face_index
                    }
                    
                    placements[twig_type].append(placement)
                   
        return placements
        
    def create_rotation_matrix_from_normal(self, normal: Tuple[float, float, float]):
        """
        Create rotation matrix to align X-axis with normal vector.
        
        Args:
            normal: Normal vector (x, y, z)
            
        Returns:
            USD transformation matrix
        """
        # Grove twigs are oriented with X-axis forward
        target = Gf.Vec3d(normal[0], normal[1], normal[2])
        x_axis = Gf.Vec3d(1, 0, 0)
        
        # Calculate rotation from X-axis to target
        if target.GetLength() < 1e-6:
            return Gf.Matrix4d(1.0)  # Identity matrix
            
        target = target.GetNormalized()
        
        # If vectors are already aligned
        if abs(Gf.Dot(x_axis, target) - 1.0) < 1e-6:
            return Gf.Matrix4d(1.0)
            
        # If vectors are opposite
        if abs(Gf.Dot(x_axis, target) + 1.0) < 1e-6:
            # Use Y-axis as rotation axis
            rotation_axis = Gf.Vec3d(0, 1, 0)
            angle = 180.0
        else:
            # Calculate rotation axis and angle
            rotation_axis = Gf.Cross(x_axis, target).GetNormalized()
            angle = math.degrees(math.acos(Gf.Dot(x_axis, target)))
            
        # Create rotation matrix
        rotation = Gf.Rotation(rotation_axis, angle)
        return Gf.Matrix4d(rotation, Gf.Vec3d(0, 0, 0))
        
    def create_usd_with_twig_instances(self, model, species_name: str, output_path: Path,
                                     scale_factor: float = 1.0) -> bool:
        """
        Create USD file with base model and twig instances.
        
        Args:
            model: Grove model object
            species_name: Species name for prototype lookup
            output_path: Output USD file path
            scale_factor: Scale factor to apply
            
        Returns:
            True if successful, False otherwise
        """
        # Find twig prototype
        prototype_path = self.find_species_prototype(species_name)
        if not prototype_path:
            # Fall back to standard USD export
            return self._create_standard_usd(model, output_path, scale_factor)
            
        # Create USD stage
        stage = Usd.Stage.CreateNew(str(output_path))
        
        # Create root prim
        root_prim = stage.DefinePrim(f"/{species_name.replace(' ', '_')}")
        stage.SetDefaultPrim(root_prim)
        
        # Add base tree model
        tree_prim_path = f"/{species_name.replace(' ', '_')}/Tree"
        self._add_base_model_to_stage(stage, model, tree_prim_path, scale_factor)
        
        # Extract twig placement data
        twig_placements = self.extract_twig_placements(model, species_name)
        
        # Reference twig prototype
        prototype_ref_path = f"./{prototype_path.relative_to(self.prototypes_dir.parent)}"
        
        # Add twig instances for each type
        for twig_type, placements in twig_placements.items():
            if not placements:
                continue
                
            for i, placement in enumerate(placements):
                instance_prim_path = f"/{species_name.replace(' ', '_')}/Twigs/{twig_type}_twig_{i:04d}"
                instance_prim = stage.DefinePrim(instance_prim_path)
                
                # Add reference to prototype
                references = instance_prim.GetReferences()
                references.AddReference(prototype_ref_path)
                
                # Set transform
                xformable = UsdGeom.Xformable(instance_prim)
                
                # Position
                position = placement['position']
                if scale_factor != 1.0:
                    position = (position[0] * scale_factor, 
                              position[1] * scale_factor,
                              position[2] * scale_factor)
                              
                # Rotation from normal
                rotation_matrix = self.create_rotation_matrix_from_normal(placement['normal'])
                
                # Combine translation and rotation
                transform_matrix = Gf.Matrix4d(1.0)
                transform_matrix.SetTranslateOnly(Gf.Vec3d(*position))
                transform_matrix = transform_matrix * rotation_matrix
                
                if scale_factor != 1.0:
                    scale_matrix = Gf.Matrix4d(1.0)
                    scale_matrix.SetScale(Gf.Vec3d(scale_factor, scale_factor, scale_factor))
                    transform_matrix = transform_matrix * scale_matrix
                    
                # Set transform
                xform_op = xformable.AddXformOp(UsdGeom.XformOp.TypeTransform)
                xform_op.Set(transform_matrix)
                
        # Set stage metadata
        root_prim.SetMetadata("kind", "component")
        root_prim.SetDocumentation(f"Grove tree with twig instances for {species_name}")
        
        # Save stage
        stage.Save()
        
        return True
            
    def _create_standard_usd(self, model, output_path: Path, scale_factor: float = 1.0) -> bool:
        """
        Create standard USD file without twig instances (fallback).
        
        Args:
            model: Grove model object
            output_path: Output USD file path
            scale_factor: Scale factor to apply
            
        Returns:
            True if successful, False otherwise
        """
        # Use Grove core's built-in USD export
        model_string = gc.io.model_to_usda_string(model)
        
        with open(output_path, 'w') as f:
            f.write(model_string)
            
        return True
            
    def _add_base_model_to_stage(self, stage, model, prim_path: str, 
                               scale_factor: float = 1.0):
        """
        Add base tree model geometry to USD stage.
        
        Args:
            stage: USD stage
            model: Grove model object
            prim_path: USD prim path for the model
            scale_factor: Scale factor to apply
        """
        # Create mesh prim
        mesh_prim = UsdGeom.Mesh.Define(stage, prim_path)
        
        # Extract geometry data from Grove model
        vertices = [(p.x, p.y, p.z) for p in model.points]
        faces = [list(face) for face in model.faces]
        
        # Apply scale
        if scale_factor != 1.0:
            vertices = [(v[0] * scale_factor, v[1] * scale_factor, v[2] * scale_factor) 
                       for v in vertices]
                       
        # Convert to USD format
        points = Vt.Vec3fArray([Gf.Vec3f(*v) for v in vertices])
        face_vertex_indices = Vt.IntArray([idx for face in faces for idx in face])
        face_vertex_counts = Vt.IntArray([len(face) for face in faces])
        
        # Set geometry attributes
        mesh_prim.CreatePointsAttr().Set(points)
        mesh_prim.CreateFaceVertexIndicesAttr().Set(face_vertex_indices)
        mesh_prim.CreateFaceVertexCountsAttr().Set(face_vertex_counts)


def save_model_with_twig_instances(model, file_path: Path, species_name: str, 
                                 twig_prototypes_dir: Optional[Path] = None,
                                 scale_factor: float = 1.0) -> bool:
    """
    Save Grove model with USD twig instances for improved performance.
    
    Args:
        model: Grove model object
        file_path: Path to save USD file
        species_name: Species name for twig prototype lookup
        twig_prototypes_dir: Directory containing twig prototypes (auto-detect if None)
        scale_factor: Scale factor to apply to model and instances
        
    Returns:
        True if successful, False otherwise
    """
    if not USD_AVAILABLE:
        save_model(model, file_path, "usd")
        return False
        
    # Initialize twig instancer
    instancer = USDTwigInstancer(twig_prototypes_dir)
    
    # Create USD with twig instances
    return instancer.create_usd_with_twig_instances(model, species_name, file_path, scale_factor)


def export_forest_models_with_twigs(forest_data, output_dir: Path, lod_configs: Dict[str, Dict],
                                   input_name: str = "forest", twig_prototypes_dir: Optional[Path] = None) -> List[Path]:
    """
    Export USD models with twig instances using native LOD variants (eliminates FBX need).
    
    Creates single USD files per tree with all LOD levels as variants, providing:
    - Native game engine support (Unity/Unreal)
    - Efficient instancing at all LOD levels
    - No FBX conversion required
    
    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_dir: Output directory
        lod_configs: LOD configurations
        input_name: Name for output subdirectory
        twig_prototypes_dir: Directory containing twig prototypes
        
    Returns:
        List of saved USD file paths (one per tree with all LODs)
    """
    models_dir = output_dir / input_name / "usd_trees_multi_lod" 
    models_dir.mkdir(parents=True, exist_ok=True)
    
    all_saved_files = []
    
    for grove, species_name, tree_count in forest_data:
        safe_species_name = species_name.replace(" ", "_").replace("_-_", "_")
        species_dir = models_dir / safe_species_name
        species_dir.mkdir(parents=True, exist_ok=True)
        
        # Build all LOD models for this species
        all_lod_models = {}
        for lod_name, lod_settings in lod_configs.items():
            all_lod_models[lod_name] = grove.build_models(lod_settings)
            
        # Create one USD file per tree with all LOD variants
        tree_count = len(next(iter(all_lod_models.values())))  # Get count from first LOD
        
        for tree_index in range(tree_count):
            filename = f"{safe_species_name}_tree_{tree_index:03d}_multi_lod.usda"
            file_path = species_dir / filename
            
            # Collect models for this tree across all LODs
            tree_lod_models = {lod_name: models[tree_index] 
                             for lod_name, models in all_lod_models.items()}
            
            success = create_multi_lod_usd_with_twigs(
                tree_lod_models, file_path, species_name, twig_prototypes_dir
            )
            
            if success:
                all_saved_files.append(file_path)
                    
    return all_saved_files


def create_multi_lod_usd_with_twigs(lod_models: Dict[str, Any], output_path: Path, species_name: str,
                                   twig_prototypes_dir: Optional[Path] = None) -> bool:
    """
    Create single USD file with multiple LOD levels as variants, including twig instances.
    
    This replaces the entire FBX pipeline by providing game engine-ready USD files with:
    - LOD0_Ultra through LOD5_Minimal as variants
    - Twig instances at each LOD level  
    - Native game engine support
    
    Args:
        lod_models: Dictionary mapping LOD names to Grove model objects
        output_path: Output USD file path
        species_name: Species name for prototype lookup
        twig_prototypes_dir: Directory containing twig prototypes
        
    Returns:
        True if successful, False otherwise
    """
    if not USD_AVAILABLE:
        return False
        
    # Initialize twig instancer
    instancer = USDTwigInstancer(twig_prototypes_dir) if twig_prototypes_dir else None
    
    # Create USD stage
    stage = Usd.Stage.CreateNew(str(output_path))
    
    # Create root prim
    root_name = species_name.replace(" ", "_").replace("-", "_")
    root_prim = stage.DefinePrim(f"/{root_name}")
    stage.SetDefaultPrim(root_prim)
    
    # Create LOD variant set
    variant_set = root_prim.GetVariantSets().AddVariantSet("LOD")
    
    # LOD order for proper game engine recognition
    lod_order = ["LOD0_Ultra", "LOD1_High", "LOD2_Medium", "LOD3_Low", "LOD4_VeryLow", "LOD5_Minimal"]
    
    # Create each LOD as a variant
    for lod_name in lod_order:
        if lod_name not in lod_models:
            continue
            
        # Set this LOD variant as active
        variant_set.AddVariant(lod_name)
        variant_set.SetVariantSelection(lod_name)
        
        # Create variant edit context
        with variant_set.GetVariantEditContext():
            # Create tree mesh for this LOD
            tree_prim_path = f"/{root_name}/Tree"
            tree_prim = UsdGeom.Mesh.Define(stage, tree_prim_path)
            
            # Add base tree model geometry
            model = lod_models[lod_name]
            _add_model_geometry_to_mesh(tree_prim, model)
            
            # Add twig instances if available
            if instancer:
                prototype_path = instancer.find_species_prototype(species_name)
                if prototype_path:
                    _add_twig_instances_to_variant(stage, model, species_name, root_name, 
                                                 instancer, prototype_path)
                    
    # Set default LOD (highest quality)
    variant_set.SetVariantSelection("LOD0_Ultra")
    
    # Set metadata for game engines
    root_prim.SetMetadata("kind", "component") 
    root_prim.SetDocumentation(f"Multi-LOD tree with twig instances for {species_name}")
    
    # Add custom metadata for game engine LOD recognition
    root_prim.SetCustomDataByKey("lodCount", len(lod_models))
    root_prim.SetCustomDataByKey("hasLODVariants", True)
    root_prim.SetCustomDataByKey("species", species_name)
    
    # Save stage
    stage.Save()
    
    return True


def _add_model_geometry_to_mesh(mesh_prim, model) -> None:
    """Add Grove model geometry to USD mesh primitive."""
    # Extract geometry data
    vertices = [(p.x, p.y, p.z) for p in model.points]
    faces = [list(face) for face in model.faces]
    
    # Convert to USD format
    points = Vt.Vec3fArray([Gf.Vec3f(*v) for v in vertices])
    face_vertex_indices = Vt.IntArray([idx for face in faces for idx in face])
    face_vertex_counts = Vt.IntArray([len(face) for face in faces])
    
    # Set geometry attributes
    mesh_prim.CreatePointsAttr().Set(points)
    mesh_prim.CreateFaceVertexIndicesAttr().Set(face_vertex_indices)
    mesh_prim.CreateFaceVertexCountsAttr().Set(face_vertex_counts)


def _add_twig_instances_to_variant(stage, model, species_name: str, root_name: str,
                                 instancer: 'USDTwigInstancer', prototype_path: Path) -> None:
    """Add twig instances to current LOD variant."""
    # Extract twig placement data
    twig_placements = instancer.extract_twig_placements(model, species_name)
    
    # Reference twig prototype
    prototype_ref_path = f"./{prototype_path.relative_to(instancer.prototypes_dir.parent)}"
    
    # Add twig instances for each type
    instance_count = 0
    for twig_type, placements in twig_placements.items():
        if not placements:
            continue
            
        for i, placement in enumerate(placements):
            instance_prim_path = f"/{root_name}/Twigs/{twig_type}_twig_{i:04d}"
            instance_prim = stage.DefinePrim(instance_prim_path)
            
            # Add reference to prototype
            references = instance_prim.GetReferences()
            references.AddReference(prototype_ref_path)
            
            # Set transform
            xformable = UsdGeom.Xformable(instance_prim)
            
            # Create transformation matrix
            position = placement['position'] 
            rotation_matrix = instancer.create_rotation_matrix_from_normal(placement['normal'])
            
            transform_matrix = Gf.Matrix4d(1.0)
            transform_matrix.SetTranslateOnly(Gf.Vec3d(*position))
            transform_matrix = transform_matrix * rotation_matrix
            
            # Set transform
            xform_op = xformable.AddXformOp(UsdGeom.XformOp.TypeTransform)
            xform_op.Set(transform_matrix)
            
            instance_count += 1