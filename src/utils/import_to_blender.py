w"""
Script to import grove data into Blender's Grove add-on.
This script should be run inside Blender's scripting window or saved as a .py file
and executed through Blender's text editor.

Instructions:
1. Open Blender with The Grove add-on installed
2. Go to Scripting workspace
3. Open or paste this script
4. Update the file_path variable to point to your exported grove JSON file
5. Run the script

Note: This script assumes the grove modules are available in Blender's Python path.
If running in a standalone Python environment, ensure the grove modules are accessible.
"""

import gzip
from pathlib import Path
from typing import Optional, Union

try:
    import bpy
    import the_grove_22_core as gc
except ImportError:
    print("This script must be run inside Blender with The Grove add-on installed")
    print("Or ensure the grove modules are in your Python path")
    exit()


def import_grove_from_json_file(
    file_path: Union[str, Path], collection_name: Optional[str] = None
):
    """
    Import a grove from a JSON file exported by the Python API.

    Args:
        file_path: Path to the JSON file containing grove data
        collection_name: Name for the new collection (defaults to filename)
    """
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return

    # Read the grove JSON data
    with open(file_path, "r") as f:
        grove_json = f.read()

    # Load the grove using The Grove's API
    grove = gc.io.grove_from_json_string(grove_json)

    # Create a new collection for the imported grove
    if collection_name is None:
        collection_name = file_path.stem

    # Create collection
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)

    # Store the grove data in the collection (compressed, like the Blender add-on does)
    compressed_grove = gzip.compress(bytes(grove_json.encode("utf-8")), compresslevel=1)
    collection["grove"] = compressed_grove

    # Set the collection as active
    bpy.context.view_layer.active_layer_collection = (
        bpy.context.view_layer.layer_collection.children[collection_name]
    )

    print(f"Successfully imported grove with {len(grove.trees)} trees from {file_path}")
    print(f"Collection '{collection_name}' created with grove data")
    print("You can now use The Grove's 'Rebuild' button to build the tree geometry")

    return grove, collection


def import_all_groves_from_directory(directory_path: Union[str, Path]):
    """
    Import all grove JSON files from a directory.

    Args:
        directory_path: Path to directory containing grove JSON files
    """
    directory = Path(directory_path)
    grove_files = list(directory.glob("*_grove.json"))

    if not grove_files:
        print(f"No grove files found in {directory}")
        return

    for grove_file in grove_files:
        species_name = grove_file.stem.replace("_grove", "")
        import_grove_from_json_file(grove_file, f"Grove_{species_name}")


# Example usage:
if __name__ == "__main__":
    # Update this path to point to your exported grove files
    output_directory = "/Users/maximiliansperlich/Developer/the-grove/data/output"

    # Import all grove files from the output directory
    import_all_groves_from_directory(output_directory)

    # Or import a specific grove file:
    # import_grove_from_json_file("/path/to/your/Fagaceae___Beech_grove.json", "Beech_Grove")
