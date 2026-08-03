"""Tests for growpy.io.unreal.script_generation.

Regression coverage for XRFF-294: cli/generate_forest.py used to inline its
own copy of this orchestration and had drifted -- missing nanite_cfg's
"voxelization" key, the wind import script, and the nanite voxelize script.
Both CLIs now call one shared function; these tests pin down that it
generates every optional script when enabled, and that both entry points
really do share the same function object (not just look similar).
"""

from growpy.io.unreal import script_generation


class _FakeConfig:
    def __init__(self, **overrides):
        self.unreal_project_path = "/Game/GrowPy"
        self.unreal_voxelization = True
        self.unreal_nanite_fallback_percent = 50
        self.unreal_nanite_fallback_target = 500
        self.unreal_nanite_lerp_uvs = True
        self.unreal_db_path = None
        self.unreal_generate_wind_data = True
        self.unreal_generate_pve_presets = True
        self.unreal_pve_import_base = "/Game/GrowPy"
        self.unreal_import_to_unreal = True
        self.__dict__.update(overrides)


def _recorder(calls, name, captured_kwargs=None):
    def _fn(*args, **kwargs):
        calls.append(name)
        if captured_kwargs is not None:
            captured_kwargs[name] = kwargs
        return f"{name}.py"

    return _fn


class TestGenerateUnrealScripts:
    """Every optional generator fires when its config flag is enabled."""

    def _patch_all_generators(self, monkeypatch, calls, captured_kwargs):
        monkeypatch.setattr(
            "growpy.io.unreal.unreal_scripts.generate_unreal_import_script",
            _recorder(calls, "import_script", captured_kwargs),
        )
        monkeypatch.setattr(
            "growpy.io.unreal.unreal_scripts.generate_unreal_cleanup_script",
            _recorder(calls, "cleanup_script", captured_kwargs),
        )
        monkeypatch.setattr(
            "growpy.io.unreal.wind_import_script.generate_wind_import_script",
            _recorder(calls, "wind_script", captured_kwargs),
        )
        monkeypatch.setattr(
            "growpy.io.unreal.pve_import_script.build_species_twig_map",
            lambda: {},
        )
        monkeypatch.setattr(
            "growpy.io.unreal.pve_foliage_data.generate_all_foliage_data",
            lambda *a, **k: [],
        )
        monkeypatch.setattr(
            "growpy.io.unreal.pve_import_script.generate_pve_preset_import_script",
            _recorder(calls, "pve_script", captured_kwargs),
        )
        monkeypatch.setattr(
            "growpy.io.unreal.pve_graph_script.generate_pve_graph_script",
            _recorder(calls, "pve_graph_script", captured_kwargs),
        )
        monkeypatch.setattr(
            "growpy.io.unreal.nanite_voxelize_script.generate_nanite_voxelize_script",
            _recorder(calls, "voxelize_script", captured_kwargs),
        )

    def test_calls_every_generator_when_all_features_enabled(
        self, tmp_path, monkeypatch
    ):
        calls: list[str] = []
        captured_kwargs: dict = {}
        self._patch_all_generators(monkeypatch, calls, captured_kwargs)

        import_script, cleanup_script = script_generation.generate_unreal_scripts(
            tmp_path, _FakeConfig(), include_static=False
        )

        assert calls == [
            "import_script",
            "cleanup_script",
            "wind_script",
            "pve_script",
            "pve_graph_script",
            "voxelize_script",
        ]
        assert import_script == "import_script.py"
        assert cleanup_script == "cleanup_script.py"

        # The bug this replaces: the CLI copy never set this key at all.
        assert captured_kwargs["import_script"]["nanite_cfg"]["voxelization"] is True

    def test_skips_optional_scripts_when_disabled(self, tmp_path, monkeypatch):
        calls: list[str] = []
        self._patch_all_generators(monkeypatch, calls, {})

        config = _FakeConfig(
            unreal_generate_wind_data=False,
            unreal_generate_pve_presets=False,
            unreal_voxelization=False,
        )
        script_generation.generate_unreal_scripts(tmp_path, config)

        assert calls == ["import_script", "cleanup_script"]


class TestSingleEntryPoint:
    """Both CLIs must call the exact same function object -- no re-drift."""

    def test_generate_forest_uses_the_shared_function(self):
        from growpy.cli import generate_forest

        assert (
            generate_forest.generate_unreal_scripts
            is script_generation.generate_unreal_scripts
        )

    def test_dataset_pipeline_uses_the_shared_function(self):
        from growpy.cli import dataset_pipeline

        assert (
            dataset_pipeline.generate_unreal_scripts
            is script_generation.generate_unreal_scripts
        )
