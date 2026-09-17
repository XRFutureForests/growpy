"""Tests for the custom-twig overlay in growpy.cli.prepare_assets.

``prepare_assets`` rmtree's each twig directory and rebuilds it from the Grove
source, so a hand-edited asset in ``data/assets/`` -- which is gitignored --
does not survive. The custom directory is the supported way to re-apply such an
edit, and it is an OVERLAY rather than a replacement so an override tracks only
the file that actually changed: the Grove twigs are licensed commercial content
and deliberately gitignored, so a full replacement copy could not be committed
even if it were wanted.

Note the silver fir foliage ladder is NOT such a case. It is derived at
conversion time by ``_derive_ladders_for_single_object_assets`` (XRFF-412),
which splits the single Grove spray along its own structure and appends the
variants. Storing it here would give the directory more than one object and
silently disable that derivation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from growpy.cli.prepare_assets import _overlay_custom_twigs


@pytest.fixture
def grove(tmp_path) -> Path:
    directory = tmp_path / "grove" / "SomeTwig"
    (directory / "textures").mkdir(parents=True)
    (directory / "SomeTwig.blend").write_bytes(b"stock blend")
    (directory / "ReadMe.txt").write_text("grove readme")
    (directory / "textures" / "Top.png").write_bytes(b"top")
    (directory / "textures" / "Bottom.png").write_bytes(b"bottom")
    return directory


@pytest.fixture
def custom(tmp_path) -> Path:
    directory = tmp_path / "custom" / "SomeTwig"
    directory.mkdir(parents=True)
    return directory


def _rebuild(grove: Path, custom: Path, tmp_path: Path) -> Path:
    """What prepare_assets now does: copy Grove, then overlay custom."""
    import shutil

    destination = tmp_path / "assets" / "some_twig"
    shutil.copytree(grove, destination)
    _overlay_custom_twigs(custom, destination)
    return destination


class TestOverlay:
    def test_an_override_replaces_only_its_own_file(self, grove, custom, tmp_path):
        (custom / "SomeTwig.blend").write_bytes(b"welded blend")
        built = _rebuild(grove, custom, tmp_path)

        assert (built / "SomeTwig.blend").read_bytes() == b"welded blend"
        # Everything the override does not mention survives from Grove.
        assert (built / "ReadMe.txt").read_text() == "grove readme"
        assert (built / "textures" / "Top.png").read_bytes() == b"top"

    def test_an_empty_override_changes_nothing(self, grove, custom, tmp_path):
        built = _rebuild(grove, custom, tmp_path)
        assert (built / "SomeTwig.blend").read_bytes() == b"stock blend"

    def test_it_overlays_into_subdirectories(self, grove, custom, tmp_path):
        (custom / "textures").mkdir()
        (custom / "textures" / "Top.png").write_bytes(b"repainted")
        built = _rebuild(grove, custom, tmp_path)

        assert (built / "textures" / "Top.png").read_bytes() == b"repainted"
        assert (built / "textures" / "Bottom.png").read_bytes() == b"bottom"

    def test_it_can_add_a_file_grove_does_not_ship(self, grove, custom, tmp_path):
        (custom / "extra_variant.blend").write_bytes(b"new")
        built = _rebuild(grove, custom, tmp_path)
        assert (built / "extra_variant.blend").read_bytes() == b"new"

    def test_it_reports_what_it_applied(self, grove, custom, tmp_path):
        (custom / "SomeTwig.blend").write_bytes(b"welded")
        (custom / "textures").mkdir()
        (custom / "textures" / "Top.png").write_bytes(b"repainted")
        import shutil

        destination = tmp_path / "assets" / "some_twig"
        shutil.copytree(grove, destination)
        applied = _overlay_custom_twigs(custom, destination)
        assert sorted(applied) == ["SomeTwig.blend", "textures/Top.png"]

    def test_directories_are_not_reported_as_files(self, grove, custom, tmp_path):
        (custom / "textures").mkdir()
        (custom / "textures" / "Top.png").write_bytes(b"x")
        import shutil

        destination = tmp_path / "assets" / "some_twig"
        shutil.copytree(grove, destination)
        assert _overlay_custom_twigs(custom, destination) == ["textures/Top.png"]
