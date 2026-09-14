"""Tests for the custom-twig overlay in growpy.cli.prepare_assets (XRFF-444).

``prepare_assets`` rmtree's each twig directory and rebuilds it from the Grove
source. A hand-edited asset living only in ``data/assets/`` -- which is
gitignored -- is therefore one ordinary run from being lost. That is not
hypothetical: the silver fir twig was welded to add a smaller foliage variant,
taking the UE foliage library from 1,364 MB to 86 MB, and the edit existed
nowhere else.

The custom directory is an OVERLAY rather than a replacement so that such an
edit needs to track only the file that changed. The Grove twigs are licensed
commercial content and deliberately gitignored, so a full replacement copy
could not be committed even if it were wanted.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from growpy.cli.prepare_assets import _overlay_custom_twigs, _warn_on_unbacked_edits


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


class TestUnbackedEditWarning:
    def _working(self, tmp_path, content: bytes) -> Path:
        directory = tmp_path / "assets" / "some_twig"
        directory.mkdir(parents=True)
        (directory / "SomeTwig.blend").write_bytes(content)
        return directory

    def test_it_warns_when_an_edit_exists_nowhere_else(
        self, grove, custom, tmp_path, caplog
    ):
        working = self._working(tmp_path, b"welded in place, never backed up")
        with caplog.at_level(logging.WARNING):
            _warn_on_unbacked_edits(working, grove, custom)
        assert any("DISCARD" in r.message for r in caplog.records)

    def test_it_is_silent_once_the_edit_has_a_custom_override(
        self, grove, custom, tmp_path, caplog
    ):
        welded = b"welded in place, now backed up"
        (custom / "SomeTwig.blend").write_bytes(welded)
        working = self._working(tmp_path, welded)
        with caplog.at_level(logging.WARNING):
            _warn_on_unbacked_edits(working, grove, custom)
        assert caplog.records == []

    def test_it_is_silent_for_an_untouched_grove_file(
        self, grove, custom, tmp_path, caplog
    ):
        working = self._working(tmp_path, b"stock blend")
        with caplog.at_level(logging.WARNING):
            _warn_on_unbacked_edits(working, grove, custom)
        assert caplog.records == []

    def test_it_copes_with_no_custom_directory_at_all(self, grove, tmp_path, caplog):
        working = self._working(tmp_path, b"edited")
        with caplog.at_level(logging.WARNING):
            _warn_on_unbacked_edits(working, grove, None)
        assert any("DISCARD" in r.message for r in caplog.records)

    def test_it_names_where_to_put_the_file(self, grove, custom, tmp_path, caplog):
        working = self._working(tmp_path, b"edited")
        with caplog.at_level(logging.WARNING):
            _warn_on_unbacked_edits(working, grove, custom)
        assert any("custom" in r.message for r in caplog.records)


class TestTheFirFoliageLadder:
    """The asset this whole mechanism exists for.

    Seven smaller sprays, grown in The Grove and appended to the silver fir
    twig. They are what took the UE foliage library from 1,364 MB to 86 MB, and
    they are not derivable from anything: they share 0 % of their vertices with
    Grove's own spray and match no object in the Grove twig library. So they
    are stored, not scripted.

    They sit BESIDE the Grove .blend rather than merged into it, because
    convert_twigs reads every .blend in a twig directory -- which also means
    Grove's own shipped spray never has to be copied anywhere.
    """

    OVERRIDE = Path("data/input/custom_twigs/PacificSilverFirTwig")
    VARIANTS = OVERRIDE / "PacificSilverFirVariants.blend"
    GROVE = Path("src/the_grove_23/twigs/PacificSilverFirTwig")

    def test_the_variants_file_is_tracked(self):
        if not self.OVERRIDE.is_dir():
            pytest.skip("custom twig override not present in this checkout")
        assert self.VARIANTS.is_file()

    def test_groves_own_blend_is_not_redistributed(self):
        # The override directory must hold only our generated sprays. Grove's
        # shipped twig is licensed commercial content and lives solely in
        # src/the_grove_23/, which is gitignored.
        if not self.OVERRIDE.is_dir():
            pytest.skip("custom twig override not present in this checkout")
        assert not (self.OVERRIDE / "PacificSilverFirTwig.blend").exists()

    def test_it_is_far_smaller_than_groves_own_spray(self):
        # A cheap proxy for "contains the seven variants, not Grove's 28k-vert
        # original": if this ever approaches the Grove file's size, someone has
        # merged the stock object back in.
        if not (self.VARIANTS.is_file() and self.GROVE.is_dir()):
            pytest.skip("Grove source or override not present in this checkout")
        stock = self.GROVE / "PacificSilverFirTwig.blend"
        assert self.VARIANTS.stat().st_size < 0.5 * stock.stat().st_size
