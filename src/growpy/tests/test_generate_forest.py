"""Tests for growpy.cli.generate_forest._resolve_static_export_for_obj."""

from growpy.cli.generate_forest import _resolve_static_export_for_obj


class _FakeConfig:
    """Minimal stand-in for GrowPyConfig -- the guard only reads/writes these."""

    def __init__(
        self,
        helios_export_obj: bool = False,
        helios_helios_scene: bool = False,
        export_static: bool = False,
    ):
        self.helios_export_obj = helios_export_obj
        self.helios_helios_scene = helios_helios_scene
        self.export_static = export_static


class TestResolveStaticExportForObj:
    """XRFF-304: guard must fire regardless of export_skeletal."""

    def test_forces_static_when_export_obj_requested(self):
        config = _FakeConfig(helios_export_obj=True, export_static=False)
        forced = _resolve_static_export_for_obj(config)
        assert forced is True
        assert config.export_static is True

    def test_forces_static_when_helios_scene_requested(self):
        config = _FakeConfig(helios_helios_scene=True, export_static=False)
        forced = _resolve_static_export_for_obj(config)
        assert forced is True
        assert config.export_static is True

    def test_leaves_static_alone_when_obj_export_not_requested(self):
        config = _FakeConfig(
            helios_export_obj=False, helios_helios_scene=False, export_static=False
        )
        forced = _resolve_static_export_for_obj(config)
        assert forced is False
        assert config.export_static is False

    def test_noop_when_static_already_on(self):
        config = _FakeConfig(helios_export_obj=True, export_static=True)
        forced = _resolve_static_export_for_obj(config)
        assert forced is False
        assert config.export_static is True
