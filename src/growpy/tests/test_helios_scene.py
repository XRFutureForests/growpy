"""Tests for growpy.io.helios_scene XML generation.

Imports directly from the module to avoid triggering growpy.io.__init__
which may attempt to load Blender/USD DLLs.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from growpy.io.helios.helios_scene import generate_helios_scene


class TestGenerateHeliosScene:
    """Tests for Helios++ scene XML generation."""

    def test_basic_scene(self, tmp_path):
        entries = [
            (Path("trees/tree_0001.obj"), 100.0, 200.0, 0.0, "norway_spruce"),
        ]
        out = tmp_path / "scene.xml"
        result = generate_helios_scene(entries, out)

        assert result == out
        assert out.exists()

        tree = ET.parse(str(out))
        root = tree.getroot()
        assert root.tag == "document"

        scene = root.find("scene")
        assert scene is not None
        assert scene.get("id") == "forest"

    def test_tree_count_matches_parts(self, tmp_path):
        entries = [
            (Path(f"t{i}.obj"), float(i), 0.0, 0.0, "sp") for i in range(5)
        ]
        out = tmp_path / "scene.xml"
        generate_helios_scene(entries, out)

        tree = ET.parse(str(out))
        parts = tree.getroot().find("scene").findall("part")
        assert len(parts) == 5

    def test_translate_filter_values(self, tmp_path):
        entries = [
            (Path("t.obj"), 1.5, 2.5, 3.5, "beech"),
        ]
        out = tmp_path / "scene.xml"
        generate_helios_scene(entries, out)

        tree = ET.parse(str(out))
        part = tree.getroot().find("scene").find("part")
        filters = part.findall("filter")

        # First filter is objloader, second is translate
        translate = filters[1]
        assert translate.get("type") == "translate"
        offset = translate.find("param[@key='offset']")
        assert offset.get("value") == "1.5;2.5;3.5"

    def test_objloader_filepath(self, tmp_path):
        obj = Path("data/output/tree.obj")
        entries = [(obj, 0.0, 0.0, 0.0, "oak")]
        out = tmp_path / "scene.xml"
        generate_helios_scene(entries, out)

        tree = ET.parse(str(out))
        part = tree.getroot().find("scene").find("part")
        loader = part.find("filter[@type='objloader']")
        fp = loader.find("param[@key='filepath']")
        assert fp.get("value") == str(obj)

    def test_custom_scene_id_and_name(self, tmp_path):
        entries = [(Path("t.obj"), 0.0, 0.0, 0.0, "sp")]
        out = tmp_path / "scene.xml"
        generate_helios_scene(
            entries, out, scene_id="my_forest", scene_name="My Forest"
        )

        tree = ET.parse(str(out))
        scene = tree.getroot().find("scene")
        assert scene.get("id") == "my_forest"
        assert scene.get("name") == "My Forest"

    def test_up_axis_parameter(self, tmp_path):
        entries = [(Path("t.obj"), 0.0, 0.0, 0.0, "sp")]
        out = tmp_path / "scene.xml"
        generate_helios_scene(entries, out, up_axis="y")

        tree = ET.parse(str(out))
        part = tree.getroot().find("scene").find("part")
        loader = part.find("filter[@type='objloader']")
        up = loader.find("param[@key='up']")
        assert up.get("value") == "y"

    def test_empty_entries(self, tmp_path):
        out = tmp_path / "scene.xml"
        generate_helios_scene([], out)

        tree = ET.parse(str(out))
        scene = tree.getroot().find("scene")
        parts = scene.findall("part")
        assert len(parts) == 0

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "scene.xml"
        generate_helios_scene([], out)
        assert out.exists()
