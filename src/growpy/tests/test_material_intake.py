"""Bark material intake (XRFF-679): folder check, packing, catalog, Fab source."""

import json

import numpy as np
import pytest
from PIL import Image

from growpy.tools import material_intake as mi


def _height(n=128):
    yy, xx = np.mgrid[0:n, 0:n] / n * 2 * np.pi
    return np.sin(3 * xx) * np.cos(2 * yy) + 0.5 * np.sin(5 * yy + xx)


def _normal(h, convention):
    """Tangent normal of a height field; green up for OpenGL, down for DirectX."""
    dcol = np.gradient(h, axis=1) * 8
    drow = np.gradient(h, axis=0) * 8
    x, y = -dcol, drow if convention == "opengl" else -drow
    z = np.ones_like(x)
    n = np.stack([x, y, z], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).round().astype(np.uint8), "RGB")


def _folder(tmp_path, convention="opengl", source="fab", **over):
    folder = tmp_path / "fab_test_bark"
    folder.mkdir()
    h = _height()
    Image.new("RGB", (128, 128), (90, 70, 50)).save(folder / "albedo.png")
    _normal(h, convention).save(folder / "normal.png")
    Image.new("L", (128, 128), 200).save(folder / "roughness.png")
    Image.fromarray(((h - h.min()) / np.ptp(h) * 255).astype(np.uint8), "L").save(
        folder / "height.png"
    )
    material = {
        "id": "fab_test_bark",
        "species": "douglas_fir",
        "bark_stage": "mature",
        "dbh_cm": [0, 200],
        "tile_size_m": [1.0, 1.0],
        "normal_convention": convention,
        "source": source,
        "source_ref": "megascans:x",
        "licence": mi.FAB_LICENCE,
        "redistributable": False,
    }
    material.update(over)
    mi.write_material_toml(folder, material)
    return folder


@pytest.mark.parametrize("convention", ["opengl", "directx"])
def test_the_curl_test_reads_the_green_convention(convention):
    assert mi.normal_convention_by_curl(_normal(_height(), convention)) == convention


def test_a_complete_folder_passes(tmp_path):
    assert mi.check(_folder(tmp_path)) == []


def test_a_wrong_normal_convention_is_caught(tmp_path):
    folder = _folder(tmp_path, convention="opengl", normal_convention="directx")
    assert any("reads opengl" in p for p in mi.check(folder))


def test_the_licence_is_required(tmp_path):
    assert any("licence" in p for p in mi.check(_folder(tmp_path, licence=" ")))


def test_a_tile_that_does_not_match_the_maps_is_caught(tmp_path):
    assert any(
        "aspect" in p for p in mi.check(_folder(tmp_path, tile_size_m=[1.0, 2.0]))
    )


def test_pack_uses_the_measured_height(tmp_path):
    folder = _folder(tmp_path)
    nah = np.asarray(Image.open(mi.pack(folder)))
    assert nah.shape == (128, 128, 4)
    height = np.asarray(Image.open(folder / "height.png"), dtype=float)
    assert np.corrcoef(nah[..., 3].ravel(), height.ravel())[0, 1] > 0.99


def test_build_writes_script_and_catalog(tmp_path):
    folder = _folder(tmp_path)
    script, catalog = tmp_path / "s.py", tmp_path / "catalog.toml"
    assert mi.build([folder], script, root=tmp_path, catalog=catalog) == []
    text = script.read_text(encoding="utf-8")
    assert "'flip_green': True" in text and "MI_" in text
    compile(text, "s.py", "exec")
    import tomllib

    entry = tomllib.loads(catalog.read_text(encoding="utf-8"))["materials"][
        "fab_test_bark"
    ]
    assert entry["redistributable"] is False
    assert entry["instance"].endswith("/fab_test_bark/MI_fab_test_bark")


@pytest.mark.parametrize(
    "name, kind",
    [
        ("Bark_BaseColor.png", "albedo"),
        ("oak_scan_diffuse_4k.jpg", "albedo"),
        ("T_Bark_Normal.tif", "normal"),
        ("bark-nrm.png", "normal"),
        ("bark_Roughness.png", "roughness"),
        ("bark_Glossiness.png", "gloss"),
        ("bark_AO.png", "ao"),
        ("bark_Displacement.png", "height"),
        ("bark_preview.png", None),
        ("bark_normal_roughness.png", None),  # ambiguous: two kinds
    ],
)
def test_map_names_are_recognised(name, kind):
    from pathlib import Path

    assert mi.classify_map(Path(name)) == kind


def test_set_takes_a_custom_texture_folder(tmp_path):
    src = tmp_path / "scan"
    src.mkdir()
    h = _height(256)
    Image.new("RGB", (256, 256), (120, 110, 100)).save(src / "Bark01_BaseColor.png")
    _normal(h, "directx").save(src / "Bark01_Normal.png")
    Image.new("L", (256, 256), 200).save(src / "Bark01_Gloss.png")
    h16 = ((h - h.min()) / np.ptp(h) * 65535).astype(np.uint16)
    Image.fromarray(h16).save(src / "Bark01_Height.png")
    Image.new("RGB", (64, 64)).save(src / "Bark01_preview.png")
    folder = mi.prepare_set(
        src,
        "european_beech",
        material_id="scan_test",
        tile_size_m=(0.5, 0.5),
        licence="CC-BY-4.0",
        source_ref="capture:2026-11-12-01",
        size=128,
        root=tmp_path / "in",
    )
    m = mi.read_material(folder)
    assert m["normal_convention"] == "directx"
    assert m["source"] == "scan" and m["redistributable"] is False
    rough = np.asarray(Image.open(folder / "roughness.png"))
    assert rough.mean() == pytest.approx(55, abs=1)  # gloss 200 inverted
    height = np.asarray(Image.open(folder / "height.png"))
    assert height.dtype == np.uint8 and height.max() == 255
    assert mi.check(folder) == []


def test_set_without_a_normal_map_is_refused(tmp_path):
    src = tmp_path / "scan"
    src.mkdir()
    Image.new("RGB", (32, 32)).save(src / "x_albedo.png")
    with pytest.raises(FileNotFoundError, match="normal"):
        mi.prepare_set(
            src,
            "x",
            material_id="x",
            tile_size_m=(1, 1),
            licence="l",
            source_ref="r",
            root=tmp_path / "in",
        )


def test_fab_reads_the_megascans_set(tmp_path):
    raw = tmp_path / "set" / "texture-set" / "raw" / "x_extracted"
    raw.mkdir(parents=True)
    h = _height(256)
    Image.new("RGB", (256, 512), (80, 60, 40)).save(raw / "Bark_x_8K_BaseColor.jpg")
    _normal(np.vstack([h, h]), "opengl").save(raw / "Bark_x_8K_Normal.jpg", quality=98)
    for kind in ("Roughness", "AO", "Displacement"):
        Image.new("L", (256, 512), 128).save(raw / f"Bark_x_8K_{kind}.jpg")
    (raw / "x.json").write_text(
        json.dumps(
            {
                "id": "x",
                "name": "Test Bark",
                "physicalSize": "1x2",
                "maps": [],
                "meta": [{"key": "scanArea", "value": "1x2 m"}],
            }
        ),
        encoding="utf-8",
    )
    folder = mi.prepare_fab(
        tmp_path / "set", "douglas_fir", size=128, root=tmp_path / "in"
    )
    m = mi.read_material(folder)
    assert m["tile_size_m"] == [1.0, 2.0]
    assert m["normal_convention"] == "opengl"
    assert m["source_ref"] == "megascans:x"
    assert Image.open(folder / "albedo.png").size == (128, 256)
    assert {p.stem for p in folder.glob("*.png")} == {
        "albedo",
        "normal",
        "roughness",
        "ao",
        "height",
    }
