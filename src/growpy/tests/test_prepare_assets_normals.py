"""Tests for the bark normal-map resolver in growpy.cli.prepare_assets.

The Grove spells 47 of its 48 bark normals ``<Stem>Normal.jpg`` and one of them
``Birch70_normal.jpg``. The copy step used to probe that single spelling, so
silver birch was copied without a normal map -- silently, at debug level -- and
its trunk rendered as polished chrome. These tests pin the tolerance and the
one case that broke it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from growpy.cli.prepare_assets import _index_bark_normals

GROVE_TEXTURES = Path(__file__).resolve().parents[3] / "src/the_grove_23/textures"


def _make(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).write_bytes(b"")
    return tmp_path


class TestSpellingTolerance:
    @pytest.mark.parametrize(
        "normal_name",
        [
            "Beech60Normal.jpg",
            "Beech60_normal.jpg",
            "Beech60-normal.jpg",
            "Beech60NORMAL.jpg",
            "beech60normal.jpg",
        ],
    )
    def test_every_spelling_the_grove_might_use_is_found(self, tmp_path, normal_name):
        _make(tmp_path, "Beech60.jpg", normal_name)
        index = _index_bark_normals(tmp_path)
        assert index["beech60"].name == normal_name

    def test_the_extension_need_not_match_the_diffuse(self, tmp_path):
        _make(tmp_path, "Beech60.jpg", "Beech60Normal.png")
        assert _index_bark_normals(tmp_path)["beech60"].suffix == ".png"

    def test_a_diffuse_with_no_normal_is_absent_not_guessed(self, tmp_path):
        _make(tmp_path, "Beech60.jpg")
        assert "beech60" not in _index_bark_normals(tmp_path)

    def test_a_normal_with_no_diffuse_is_not_claimed(self, tmp_path):
        # Without the diffuse check, a texture legitimately named "...Normal"
        # would register itself as some other texture's normal map.
        _make(tmp_path, "StandaloneNormal.jpg")
        assert _index_bark_normals(tmp_path) == {}

    def test_a_missing_directory_yields_an_empty_index(self, tmp_path):
        assert _index_bark_normals(tmp_path / "absent") == {}


class TestAgainstTheRealGroveSource:
    """Guards the actual data, which is where the defect lived."""

    @pytest.fixture(autouse=True)
    def _require_grove(self):
        if not GROVE_TEXTURES.is_dir():
            pytest.skip("The Grove source textures are not present")

    def test_birch70_is_found_despite_its_odd_spelling(self):
        # The one file in 97 that the old hardcoded rule missed.
        index = _index_bark_normals(GROVE_TEXTURES)
        assert index["birch70"].name == "Birch70_normal.jpg"

    def test_every_bark_diffuse_now_has_a_normal(self):
        index = _index_bark_normals(GROVE_TEXTURES)
        diffuse = [
            p
            for p in GROVE_TEXTURES.iterdir()
            if p.is_file()
            and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".tga")
            and "normal" not in p.stem.lower()
        ]
        missing = [p.name for p in diffuse if p.stem.lower() not in index]
        assert missing == [], f"bark diffuse with no normal map: {missing}"

    def test_the_conventional_spelling_still_resolves(self):
        index = _index_bark_normals(GROVE_TEXTURES)
        assert index["beech60"].name == "Beech60Normal.jpg"
        assert index["fir70"].name == "Fir70Normal.jpg"
