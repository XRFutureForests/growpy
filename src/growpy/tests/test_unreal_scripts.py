"""Tests for growpy.io.unreal_scripts string generation functions."""


from growpy.io.unreal.unreal_scripts import (
    _build_consolidation_script,
    _build_import_block,
)


class TestBuildImportBlock:
    """Tests for USD import block generation."""

    def test_basic_block_structure(self):
        block = _build_import_block(
            file_path="/path/to/tree.usda",
            dest_path="species/variant",
            label="tree_0001",
        )
        assert "import_task = unreal.AssetImportTask()" in block
        assert 'import_task.filename = "/path/to/tree.usda"' in block
        assert 'IMPORT_PATH + "/species/variant"' in block
        assert "tree_0001" in block

    def test_no_nanite_config_by_default(self):
        block = _build_import_block("/p", "d", "l")
        assert "_configure_nanite_assembly" not in block

    def test_nanite_config_flag_accepted(self):
        block = _build_import_block(
            "/p",
            "d",
            "l",
            wind_json_path="/wind.json",
            configure_nanite=True,
        )
        assert "import_task" in block

    def test_nanite_config_empty_wind(self):
        block = _build_import_block(
            "/p",
            "d",
            "l",
            wind_json_path="",
            configure_nanite=True,
        )
        assert "import_task" in block

    def test_gc_and_cleanup_present(self):
        block = _build_import_block("/p", "d", "l")
        assert "gc.collect()" in block
        assert "collect_garbage" in block

    def test_error_handling(self):
        block = _build_import_block("/p", "d", "l")
        assert "except Exception as e:" in block


class TestBuildConsolidationScript:
    """Tests for twig consolidation script generation."""

    def test_contains_project_path(self):
        script = _build_consolidation_script("/Game/GrowPy/Trees")
        assert 'IMPORT_PATH = "/Game/GrowPy/Trees"' in script

    def test_contains_consolidation_logic(self):
        script = _build_consolidation_script("/Game/Test")
        assert "consolidate_assets" in script
        assert "canonical" in script
        assert "duplicates" in script

    def test_imports_unreal(self):
        script = _build_consolidation_script("/Game/Test")
        assert "import unreal" in script
        assert "import gc" in script

    def test_instances_subpath(self):
        script = _build_consolidation_script("/Game/Trees")
        assert 'INSTANCES_PATH = IMPORT_PATH + "/Instances"' in script

    def test_instances_subpath(self):
        script = _build_consolidation_script("/Game/Trees")
        assert 'INSTANCES_PATH = IMPORT_PATH + "/Instances"' in script
