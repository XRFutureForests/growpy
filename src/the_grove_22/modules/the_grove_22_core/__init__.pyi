# Type stub for the_grove_22_core module
# This file provides type information for the compiled Grove library

from typing import List, Dict, Any, Tuple, Union

class Vector:
    """An (X, Y, Z) vector class with all the math needed to grow trees."""

    def __init__(self, x: float, y: float, z: float) -> None: ...

    # Math operators
    def __add__(self, other: "Vector") -> "Vector": ...
    def __sub__(self, other: "Vector") -> "Vector": ...
    def __mul__(self, scalar: float) -> "Vector": ...
    def __truediv__(self, scalar: float) -> "Vector": ...

    # Vector methods
    def angle(self, b: "Vector") -> float: ...
    def cross(self, b: "Vector") -> "Vector": ...
    def dot(self, b: "Vector") -> float: ...
    def as_tuple(self) -> Tuple[float, float, float]: ...
    def flip_y_z(self) -> "Vector": ...
    def length(self) -> float: ...
    def lerp(self, b: "Vector", amount: float) -> "Vector": ...
    def normalized(self) -> "Vector": ...
    def slerp(self, b: "Vector", amount: float) -> "Vector": ...

    # Properties
    x: float
    y: float
    z: float

class Rotation:
    """A high level rotation quaternion class."""

    @staticmethod
    def identity() -> "Rotation": ...
    @staticmethod
    def from_axis_angle(axis: Vector, angle: float) -> "Rotation": ...
    @staticmethod
    def from_vector_to_vector(from_vec: Vector, to_vec: Vector) -> "Rotation": ...
    @staticmethod
    def z_axis_angle(angle: float) -> "Rotation": ...
    @staticmethod
    def from_right_to_vector_z_up(to_vec: Vector) -> "Rotation": ...
    def rotate_vector(self, vector: Vector) -> Vector: ...

class Randomizer:
    """Generate pseudo-random floating point numbers from 0.0 to 1.0."""

    def __init__(self) -> None: ...
    def factor(self) -> float: ...
    def set_seed(self, seed: int) -> None: ...

class Node:
    """A branch is a list of connected nodes, and every node has a list of side branches."""

    direction: Vector  # A relative Vector that points from this node to the next node
    pos: Vector  # The absolute position of the node after bending
    radius: float  # Half the thickness of the branch section at that point
    thickness: float  # A normalized value where 1.0 is the thickest point at the base
    side_branches: List["Branch"]  # Every node can have a number of side branches

class Branch:
    """A branch is a list of nodes."""

    nodes: List[Node]

class Properties:
    """Properties store all natural growth parameters that together define how the tree grows."""

    # Growth parameters
    grow_nodes: int
    grow_length: float
    favor_bright: float
    favor_end: float
    favor_end_reduce: float
    favor_rising: float
    favor_dwindle: float

    # Add parameters
    add_side_branches: int
    add_chance: float
    add_angle: float
    add_up: float
    add_fork: float
    add_horizontal: float
    add_planar: float
    add_twist: float
    add_regenerate: float
    add_only_on_end: bool
    add_chance_reduce: float
    add_bud_life: int

    # Turn parameters
    turn_to_light: float
    turn_up: float
    turn_up_in_shade: float
    turn_to_horizon: float
    turn_random: float

    # Thicken parameters
    thicken_tips: float
    thicken_tips_reduce: float
    thicken_join: float
    thicken_deadwood: float
    thicken_base_buttress: float
    thicken_base_scale: float
    thicken_base_shape: float

    # Drop parameters
    drop_shaded: float
    drop_weak: float
    drop_obsolete: float
    drop_decay: float

    # Shade parameters
    shade_area: float
    shade_area_reduce: float
    shade_area_depth: float
    shade_leaf_sides: bool
    shade_branches: bool
    shade_alongside: int
    shade_alongside_diameter: float
    shade_avoidance: float

    # Bend parameters
    bend_mass: float
    bend_twig_mass: float
    bend_twig_mass_solidify: float
    bend_reaction: float

    # Twig parameters
    twig_longevity: int
    twig_wither: int
    twig_density: float
    twig_side_on_tips: bool

    # Auto prune parameters
    auto_prune_enabled: bool
    auto_prune_low: float
    auto_prune_keep_thick: float
    auto_prune_dangling: float

    # React parameters
    react_enabled: bool
    react_attract_strength: float
    react_attract_falloff: float
    react_deflect_strength: float
    react_deflect_falloff: float

    # Surround parameters
    surround_enabled: bool
    surround_grow: bool
    surround_density: float
    surround_distance: float
    surround_height: float

    # Stake parameters
    stake_enabled: bool
    stake_height: float

    # Sow parameters
    sow_enabled: bool
    sow_age: int
    sow_chance: float
    sow_distance: float
    sow_limit: int

    # Simulation scale
    simulation_scale: float

class Model:
    """A 3D model consisting of lists of points, faces, uvs and attribute layers."""

    points: List[Vector]
    faces: List[List[int]]

    # Model manipulation methods
    def apply_uv_aspect_ratio(self, aspect: float) -> None: ...
    def get_uvs_flat(self) -> List[float]: ...
    def get_uvws_flat(self) -> List[float]: ...
    def get_uv_islands_flat(self) -> List[float]: ...
    def get_directions_flat(self) -> List[float]: ...
    def get_points_flat(self) -> List[float]: ...
    def get_shape_as_tuples(self) -> List[Tuple[float, float, float]]: ...
    def set_up_axis(self, new_up_axis: str) -> None: ...  # "Y" or "Z"
    def set_winding_order(
        self, new_winding_order: str
    ) -> None: ...  # "CLOCKWISE" or "COUNTER_CLOCKWISE"
    def triangulate(self) -> None: ...

    # Attribute layers (face attributes)
    face_attribute_tree_index: List[int]
    face_attribute_twig_long: List[bool]
    face_attribute_twig_short: List[bool]
    face_attribute_twig_upward: List[bool]
    face_attribute_twig_dead: List[bool]
    face_attribute_dead: List[bool]
    face_attribute_branch_index: List[int]
    face_attribute_branch_index_parent: List[int]
    face_attribute_end: List[bool]
    face_attribute_direction: List[Tuple[float, float, float]]

    # Point attributes
    point_attribute_age: List[int]
    point_attribute_mass: List[float]
    point_attribute_orientation: List[Tuple[float, float, float, float]]
    point_attribute_shade: List[float]
    point_attribute_thickness: List[float]
    point_attribute_vigor: List[float]
    point_attribute_photosynthesis: List[float]
    point_attribute_pitch: List[float]

class Skeleton:
    """A skeleton structure for physics simulation purposes."""

    points: List[Tuple[float, float, float]]  # List of bone joint coordinates
    poly_lines: List[List[int]]  # Connects the joints in points
    location: Tuple[float, float, float]  # Origin point of the skeleton

    # Attributes
    face_attribute_branch_id: List[int]
    point_attribute_age: List[int]
    point_attribute_mass: List[float]
    point_attribute_radius: List[float]

class RayTree:
    """A bounding volume hierarchy used primarily to calculate shade."""

    pass

class Grove:
    """A grove is a group of trees, a small woodland or orchard."""

    def __init__(self) -> None: ...

    # Tree management
    trees: List[Branch]  # List of tree trunks (which are branches)
    def clear_trees(self) -> None: ...
    def add_new_tree(self, position: Vector, direction: Vector, delay: int) -> None: ...

    # Properties management
    def get_properties(self) -> Properties: ...
    def set_properties(self, properties: Properties) -> None: ...

    # Simulation
    def simulate(self, flushes: int = 1) -> None: ...
    def set_random_seed(self, seed: int) -> None: ...

    # Shade calculation for multiple groves
    def create_shade_geometry_coords(self) -> List[Tuple[float, float, float]]: ...
    def calculate_shade_together(
        self, coords: List[Tuple[float, float, float]]
    ) -> None: ...

    # Building models
    def build_models(self, build_options: Dict[str, Any]) -> List[Model]: ...
    def build_as_one_model(self, build_options: Dict[str, Any]) -> Model: ...
    def build_skeletons(self) -> List[Skeleton]: ...  # studio edition feature

    # Manual operations
    def manual_prune(self, ray_tree: RayTree) -> None: ...
    def manual_draw(self, start_node_index: int, guide: List[Vector]) -> None: ...
    def replant_tree(
        self, tree_index: int, translation: Vector, rotation: Rotation
    ) -> None: ...

# Build options type for better typing
BuildOptions = Dict[str, Union[int, float, bool]]

class io:
    """Input and output of entire simulations, presets, and tree models."""

    @staticmethod
    def grove_from_json_string(json_string: str) -> Grove: ...
    @staticmethod
    def grove_to_json_string(grove: Grove) -> str: ...
    @staticmethod
    def properties_to_json_string(properties: Properties) -> str: ...
    @staticmethod
    def properties_from_json_string(json_string: str) -> Properties: ...
    @staticmethod
    def grove_to_svg_string(grove: Grove) -> str: ...  # studio edition feature
    @staticmethod
    def model_to_obj_string(model: Model) -> str: ...  # studio edition feature
    @staticmethod
    def model_to_usda_string(model: Model) -> str: ...  # studio edition feature

class tree_math:
    """Functions for planting groups of trees in clumps, islands, rings and rows."""

    @staticmethod
    def phyllotaxis_samples(number: int) -> List[Vector]: ...
    @staticmethod
    def phyllotaxis_samples_flat(
        number: int, space: float, random_factor: float
    ) -> List[Vector]: ...
    @staticmethod
    def plant_clump(number: int, space: float, clearing: float) -> List[Vector]: ...
    @staticmethod
    def plant_islands(
        islands_number: int,
        islands_space: float,
        trees_number: int,
        trees_space: float,
        randomize_number: int,
        random_shift: float,
        clearing: float,
        seed: int,
    ) -> List[Vector]: ...
    @staticmethod
    def plant_rows(
        trees_number: int,
        tree_space: float,
        rows_number: int,
        rows_space: float,
        diamond: bool,
    ) -> List[Vector]: ...
    @staticmethod
    def plant_ring(number: int, radius: float) -> List[Vector]: ...
    @staticmethod
    def add_variation(
        positions: List[Vector],
        random_shift: float,
        diverge: float,
        delay: int,
        seed: int,
    ) -> Tuple[List[Vector], List[Vector], List[int]]: ...

class about:
    """Information about The Grove."""

    about: str  # Short description of the program
    license: str  # The EULA for The Grove
    release: str  # Release version, e.g. "2.2"
    edition: str  # Edition: "starter", "indie", or "studio"

# Math constants
PI: float
