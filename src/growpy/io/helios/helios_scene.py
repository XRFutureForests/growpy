"""Helios++ scene XML generation.

Generates a Helios scene XML that positions individual tree OBJ files
using translate filters. Each tree is a separate <part> entry referencing
its OBJ file with coordinate transforms from the forest CSV data.

Scene XML format reference:
    https://github.com/3dgeo-heidelberg/helios/wiki/Scene
"""

import logging
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

logger = logging.getLogger(__name__)


def generate_helios_scene(
    tree_entries: list[tuple[Path, float, float, float, str]],
    output_path: Path,
    scene_id: str = "forest",
    scene_name: str = "Generated Forest",
    up_axis: str = "z",
) -> Path:
    """Generate a Helios++ scene XML file referencing individual tree OBJ files.

    Args:
        tree_entries: List of (obj_path, x, y, z, species_name) tuples
        output_path: Path to write the scene XML file
        scene_id: Scene identifier for Helios
        scene_name: Human-readable scene name
        up_axis: Coordinate up axis ("z" or "y")

    Returns:
        Path to generated scene XML
    """
    scene = Element("document")

    scene_elem = SubElement(scene, "scene")
    scene_elem.set("id", scene_id)
    scene_elem.set("name", scene_name)

    for part_id, (obj_path, x, y, z, species) in enumerate(tree_entries):
        part = SubElement(scene_elem, "part")

        # OBJ loader filter
        loader = SubElement(part, "filter")
        loader.set("type", "objloader")

        filepath_param = SubElement(loader, "param")
        filepath_param.set("type", "string")
        filepath_param.set("key", "filepath")
        filepath_param.set("value", str(obj_path))

        up_param = SubElement(loader, "param")
        up_param.set("type", "string")
        up_param.set("key", "up")
        up_param.set("value", up_axis)

        # Translate filter to position tree at CSV coordinates
        translate = SubElement(part, "filter")
        translate.set("type", "translate")

        offset_param = SubElement(translate, "param")
        offset_param.set("type", "vec3")
        offset_param.set("key", "offset")
        offset_param.set("value", f"{x};{y};{z}")

    tree = ElementTree(scene)
    indent(tree, space="    ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), encoding="unicode", xml_declaration=True)

    logger.info("Helios scene: %s (%d trees)", output_path.name, len(tree_entries))
    return output_path
