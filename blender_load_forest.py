#!/usr/bin/env python3
"""
Blender Forest Loader for GrowPy Generated Trees

This script loads all tree models with twigs from the GrowPy forest generation output
and organizes them in a Blender scene. It includes options for material handling,
collection organization, and basic scene setup.

Usage in Blender:
1. Open Blender
2. Go to Scripting workspace
3. Load and run this script
4. Adjust the FOREST_DIR path if needed
"""

import bpy
import bmesh
from pathlib import Path
from mathutils import Vector
import os

# Configuration
FOREST_DIR = Path("/Users/maximiliansperlich/Developer/the-grove/data/output/illustration_gis/twigs")
SCALE_FACTOR = 1.0  # Adjust if trees need scaling
COLLECTION_NAME = "GrowPy_Forest"


def clear_scene():
    """Clear the default scene objects."""
    # Select all objects
    bpy.ops.object.select_all(action='SELECT')
    # Delete selected objects
    bpy.ops.object.delete(use_global=False)
    
    # Clear materials
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)
    
    print("✅ Cleared default scene")


def setup_scene():
    """Set up the scene for forest rendering."""
    scene = bpy.context.scene
    
    # Set up units (meters)
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'
    scene.unit_settings.scale_length = 1.0
    
    # Set up world background (sky blue)
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = (0.5, 0.7, 1.0, 1.0)  # Sky blue
        bg_node.inputs[1].default_value = 0.3  # Strength
    
    print("✅ Scene setup complete")


def create_forest_collection():
    """Create a collection for the forest."""
    # Create main forest collection
    if COLLECTION_NAME in bpy.data.collections:
        forest_collection = bpy.data.collections[COLLECTION_NAME]
    else:
        forest_collection = bpy.data.collections.new(COLLECTION_NAME)
        bpy.context.scene.collection.children.link(forest_collection)
    
    return forest_collection


def setup_materials():
    """Create basic materials for trees if they don't exist."""
    materials = {}
    
    # Bark Material
    if "BarkMaterial" not in bpy.data.materials:
        bark_mat = bpy.data.materials.new(name="BarkMaterial")
        bark_mat.use_nodes = True
        
        # Get the principled BSDF node
        principled = bark_mat.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.6, 0.4, 0.2, 1.0)  # Brown
            principled.inputs["Roughness"].default_value = 0.9
            principled.inputs["Specular"].default_value = 0.3
        
        materials["bark"] = bark_mat
    
    # Leaf Material
    if "LeafMaterial" not in bpy.data.materials:
        leaf_mat = bpy.data.materials.new(name="LeafMaterial")
        leaf_mat.use_nodes = True
        
        # Get the principled BSDF node
        principled = leaf_mat.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.2, 0.6, 0.15, 1.0)  # Green
            principled.inputs["Roughness"].default_value = 0.7
            principled.inputs["Specular"].default_value = 0.4
            principled.inputs["Alpha"].default_value = 0.9
        
        # Enable transparency
        leaf_mat.blend_method = 'BLEND'
        materials["leaf"] = leaf_mat
    
    # Woody Twig Material
    if "WoodyTwigMaterial" not in bpy.data.materials:
        woody_mat = bpy.data.materials.new(name="WoodyTwigMaterial")
        woody_mat.use_nodes = True
        
        # Get the principled BSDF node
        principled = woody_mat.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.4, 0.3, 0.15, 1.0)  # Dark brown
            principled.inputs["Roughness"].default_value = 0.8
            principled.inputs["Specular"].default_value = 0.2
        
        materials["woody"] = woody_mat
    
    print("✅ Materials setup complete")
    return materials


def import_usd_file(usd_path, collection):
    """Import a USD file into Blender."""
    try:
        # Store current objects to identify new ones
        existing_objects = set(bpy.context.scene.objects)
        
        # Import USD file
        bpy.ops.wm.usd_import(
            filepath=str(usd_path),
            scale=SCALE_FACTOR,
            import_meshes=True,
            import_lights=False,
            import_cameras=False,
            import_materials=True,
            import_subdiv=False
        )
        
        # Find newly imported objects
        new_objects = set(bpy.context.scene.objects) - existing_objects
        
        # Move new objects to forest collection
        for obj in new_objects:
            # Remove from current collections
            for coll in obj.users_collection:
                coll.objects.unlink(obj)
            
            # Add to forest collection
            collection.objects.link(obj)
        
        print(f"✅ Imported {usd_path.name}: {len(new_objects)} objects")
        return len(new_objects)
        
    except Exception as e:
        print(f"❌ Failed to import {usd_path.name}: {e}")
        return 0


def organize_by_species(forest_collection):
    """Organize trees into species-based subcollections."""
    species_collections = {}
    
    for obj in forest_collection.objects:
        # Try to determine species from object name
        species = "Unknown"
        if "Beech" in obj.name:
            species = "Beech"
        elif "SilverFir" in obj.name or "Fir" in obj.name:
            species = "Silver_Fir"
        elif "Oak" in obj.name:
            species = "Oak"
        elif "Pine" in obj.name:
            species = "Pine"
        
        # Create species collection if it doesn't exist
        species_coll_name = f"{species}_Trees"
        if species_coll_name not in species_collections:
            species_coll = bpy.data.collections.new(species_coll_name)
            forest_collection.children.link(species_coll)
            species_collections[species_coll_name] = species_coll
        
        # Move object to species collection
        forest_collection.objects.unlink(obj)
        species_collections[species_coll_name].objects.link(obj)
    
    print(f"✅ Organized trees into {len(species_collections)} species collections")


def setup_camera_and_lighting():
    """Set up basic camera and lighting for the forest scene."""
    
    # Add camera if not exists
    if not any(obj.type == 'CAMERA' for obj in bpy.context.scene.objects):
        bpy.ops.object.camera_add(location=(50, -50, 25))
        camera = bpy.context.active_object
        camera.name = "Forest_Camera"
        
        # Point camera towards center
        camera.rotation_euler = (1.1, 0, 0.785)  # Look down at 45 degrees
    
    # Add sun light if not exists
    if not any(obj.type == 'LIGHT' for obj in bpy.context.scene.objects):
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 50))
        sun = bpy.context.active_object
        sun.name = "Forest_Sun"
        sun.data.energy = 5.0
        sun.rotation_euler = (0.3, 0.1, 0)  # Angle the sun
    
    print("✅ Camera and lighting setup complete")


def load_forest():
    """Main function to load the entire forest."""
    print(f"🌲 Starting GrowPy Forest Loader")
    print(f"📁 Looking for trees in: {FOREST_DIR}")
    
    # Check if directory exists
    if not FOREST_DIR.exists():
        print(f"❌ Error: Directory not found: {FOREST_DIR}")
        print("Please update FOREST_DIR path in the script")
        return
    
    # Find all USD files with twigs
    usd_files = list(FOREST_DIR.glob("*_with_twigs.usda"))
    
    if not usd_files:
        print(f"❌ No tree files found in {FOREST_DIR}")
        print("Make sure you've run the forest generation script first")
        return
    
    print(f"🌳 Found {len(usd_files)} tree files to import")
    
    # Clear existing scene
    clear_scene()
    
    # Setup scene
    setup_scene()
    
    # Create forest collection
    forest_collection = create_forest_collection()
    
    # Setup materials
    materials = setup_materials()
    
    # Import all USD files
    total_objects = 0
    successful_imports = 0
    
    for i, usd_file in enumerate(usd_files, 1):
        print(f"📦 Importing {i}/{len(usd_files)}: {usd_file.name}")
        num_objects = import_usd_file(usd_file, forest_collection)
        
        if num_objects > 0:
            successful_imports += 1
            total_objects += num_objects
    
    # Organize by species
    organize_by_species(forest_collection)
    
    # Setup camera and lighting
    setup_camera_and_lighting()
    
    # Set camera as active
    for obj in bpy.context.scene.objects:
        if obj.type == 'CAMERA':
            bpy.context.scene.camera = obj
            break
    
    # Summary
    print(f"\n🎉 Forest import complete!")
    print(f"✅ Successfully imported: {successful_imports}/{len(usd_files)} files")
    print(f"🌲 Total objects in scene: {total_objects}")
    print(f"📁 Trees organized in collection: {COLLECTION_NAME}")
    
    # Final tips
    print(f"\n💡 Tips for working with your forest:")
    print(f"   • Use Numpad 0 to view from camera")
    print(f"   • Press Z and select 'Material Preview' or 'Rendered' to see materials")
    print(f"   • Trees are organized by species in the Outliner")
    print(f"   • Adjust SCALE_FACTOR in script if trees appear too large/small")


# Run the forest loader
if __name__ == "__main__":
    load_forest()