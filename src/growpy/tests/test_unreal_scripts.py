"""Tests for growpy.io.unreal_scripts string generation functions."""


from growpy.io.unreal.unreal_scripts import (
    _build_consolidation_script,
    _build_import_block,
    _write_batch_script,
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

    def test_emits_a_per_asset_record_on_every_path(self):
        """Per-batch wall-clock cannot tell a build from a skip -- a batch
        that skipped everything looks like a fast build (XRFF-323)."""
        block = _build_import_block("/p", "d", "my_label")
        for outcome in ("skipped", "{_outcome}", "error"):
            assert f"[ASSET] outcome={outcome} " in block
        assert '_outcome = "imported"' in block
        assert '_outcome = "failed"' in block
        assert block.count("label=my_label") == 3

    def test_per_asset_timing_spans_the_gc_and_vram_settle(self):
        """An asset's real cost includes the cleanup that follows it, so the
        record is emitted after _wait_for_vram, not at the import call."""
        block = _build_import_block("/p", "d", "l")
        assert block.index("_t0 = time.time()") < block.index("_wait_for_vram")
        assert block.index("_wait_for_vram") < block.index("[ASSET] outcome={_outcome}")


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


class TestImportBlockDoneMarker:
    """Regression tests for the done.txt resume contract (XRFF-332).

    `import_task.imported_object_paths` being non-empty only means UE created
    the objects. With `import_task.save = True` the save can still fail -- a
    full disk did exactly this on 2026-08-15 -- and the marker was written
    anyway, so every later run skipped an asset that was never on disk.
    """

    def _block(self):
        return _build_import_block(
            file_path="/path/to/tree.usda",
            dest_path="silver_fir/r00",
            label="Silver_Fir_r00_h20m_d26cm_full_assembly",
        )

    def test_done_marker_requires_a_package_on_disk(self):
        block = self._block()
        # The marker is gated on the disk check, not on imported_object_paths
        # alone.
        assert "_package_saved_to_disk(" in block
        marker_at = block.index("_record_file_done(")
        guard_at = block.index("_package_saved_to_disk(")
        assert guard_at < marker_at

    def test_objects_without_a_package_count_as_failed(self):
        block = self._block()
        assert "elif import_task.imported_object_paths:" in block
        assert "NOT recorded as done" in block
        # The operator needs to know a re-run will retry it, since the whole
        # point is that the asset is absent rather than done.
        assert "re-run to retry" in block


class TestPackageSavedToDiskHelper:
    """The preamble helper that backs the done.txt guard."""

    def _preamble(self, tmp_path):
        script = tmp_path / "import_batch_06_silver_fir.py"
        _write_batch_script(
            script_path=script,
            project_path="/Game/Assets/TheGrove",
            batch_label="silver_fir",
            import_blocks="",
            file_count=0,
        )
        return script.read_text(encoding="utf-8")

    def test_helper_is_defined_before_use(self, tmp_path):
        text = self._preamble(tmp_path)
        assert "def _package_saved_to_disk(object_paths):" in text
        assert "_CONTENT_DIR" in text
        # Size check as well as existence: a 0-byte .uasset is not a saved
        # package either.
        assert "os.path.getsize(_fp) > 0" in text

    def test_generated_script_is_valid_python(self, tmp_path):
        import ast

        ast.parse(self._preamble(tmp_path))
