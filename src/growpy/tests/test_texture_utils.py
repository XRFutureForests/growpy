"""Tests for growpy.io.texture_utils module."""

import logging
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from growpy.io.texture_utils import (
    bump_to_normal,
    extract_alpha_from_diffuse,
    is_power_of_2,
    next_power_of_2,
    normalize_alpha_texture,
    resize_to_power_of_2,
    strip_alpha_from_diffuse,
)


class TestNextPowerOf2:
    """Tests for next_power_of_2 function."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (1, 1),
            (2, 2),
            (3, 4),
            (4, 4),
            (5, 8),
            (100, 128),
            (256, 256),
            (257, 512),
            (1000, 1024),
            (1024, 1024),
            (1025, 2048),
            (2000, 2048),
        ],
    )
    def test_values(self, value, expected):
        assert next_power_of_2(value) == expected

    def test_zero_returns_one(self):
        assert next_power_of_2(0) == 1

    def test_negative_returns_one(self):
        assert next_power_of_2(-5) == 1

    def test_large_value(self):
        assert next_power_of_2(4000) == 4096

    def test_result_is_always_power_of_2(self):
        for v in [1, 7, 15, 33, 100, 511, 1023]:
            result = next_power_of_2(v)
            assert is_power_of_2(result)
            assert result >= v


class TestIsPowerOf2:
    """Tests for is_power_of_2 function."""

    @pytest.mark.parametrize("value", [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024])
    def test_powers_of_2(self, value):
        assert is_power_of_2(value) is True

    @pytest.mark.parametrize("value", [0, 3, 5, 6, 7, 9, 10, 15, 100, 255, 1023])
    def test_non_powers_of_2(self, value):
        assert is_power_of_2(value) is False

    def test_negative_returns_false(self):
        assert is_power_of_2(-4) is False


class TestResizeToPowerOf2:
    """Tests for resize_to_power_of_2."""

    def test_already_power_of_2_returns_same_path(self, tmp_path):
        img = Image.new("RGB", (256, 512))
        p = tmp_path / "tex.png"
        img.save(p)
        result = resize_to_power_of_2(p)
        assert result == p
        assert Image.open(p).size == (256, 512)

    def test_upscales_to_next_power(self, tmp_path):
        img = Image.new("RGB", (100, 200))
        p = tmp_path / "tex.png"
        img.save(p)
        resize_to_power_of_2(p)
        assert Image.open(p).size == (128, 256)

    def test_output_path(self, tmp_path):
        img = Image.new("RGB", (100, 100))
        src = tmp_path / "src.png"
        dst = tmp_path / "dst.png"
        img.save(src)
        result = resize_to_power_of_2(src, output_path=dst)
        assert result == dst
        assert dst.exists()
        assert Image.open(dst).size == (128, 128)

    def test_invalid_path_returns_none(self, tmp_path):
        result = resize_to_power_of_2(tmp_path / "nonexistent.png")
        assert result is None


class TestBumpToNormal:
    """Tests for bump_to_normal conversion."""

    def test_flat_bump_produces_neutral_normal(self, tmp_path):
        # Uniform grey bump = no gradients = (0.5, 0.5, ~1.0 blue)
        img = Image.new("L", (64, 64), 128)
        p = tmp_path / "bump.png"
        img.save(p)
        result = bump_to_normal(p)
        assert result is not None
        normal = np.array(Image.open(result))
        assert normal.shape == (64, 64, 3)
        # Center pixels should be close to neutral (128, 128, ~255 blue)
        center = normal[32, 32]
        assert abs(int(center[0]) - 128) < 5
        assert abs(int(center[1]) - 128) < 5
        assert center[2] > 200  # Blue dominant for flat surface

    def test_output_path_custom(self, tmp_path):
        img = Image.new("L", (32, 32), 128)
        p = tmp_path / "bump.png"
        out = tmp_path / "custom_normal.png"
        img.save(p)
        result = bump_to_normal(p, output_path=out)
        assert result == out
        assert out.exists()

    def test_rgb_input_converted_to_grayscale(self, tmp_path):
        img = Image.new("RGB", (32, 32), (128, 128, 128))
        p = tmp_path / "bump_rgb.png"
        img.save(p)
        result = bump_to_normal(p)
        assert result is not None

    def test_invert_flag(self, tmp_path):
        # Gradient bump: left dark, right bright
        arr = np.zeros((32, 32), dtype=np.uint8)
        arr[:, 16:] = 255
        img = Image.fromarray(arr, "L")
        p = tmp_path / "bump.png"
        img.save(p)
        normal_not_inv = np.array(Image.open(bump_to_normal(p, tmp_path / "n1.png")))
        normal_inv = np.array(
            Image.open(bump_to_normal(p, tmp_path / "n2.png", invert=True))
        )
        # Red channel (gradient direction) should differ between inverted and normal
        assert not np.array_equal(normal_not_inv[:, :, 0], normal_inv[:, :, 0])

    def test_nonexistent_returns_none(self, tmp_path):
        result = bump_to_normal(tmp_path / "missing.png")
        assert result is None


class TestExtractAlphaFromDiffuse:
    """Tests for extract_alpha_from_diffuse."""

    def test_rgba_with_meaningful_alpha(self, tmp_path):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[:, :, 3] = 128  # Semi-transparent
        img = Image.fromarray(arr, "RGBA")
        p = tmp_path / "diffuse.png"
        img.save(p)
        result = extract_alpha_from_diffuse(p)
        assert result is not None
        alpha_img = Image.open(result)
        assert alpha_img.mode == "L"

    def test_rgba_all_opaque_returns_none(self, tmp_path):
        img = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        p = tmp_path / "diffuse.png"
        img.save(p)
        result = extract_alpha_from_diffuse(p)
        assert result is None

    def test_rgb_no_alpha_returns_none(self, tmp_path):
        img = Image.new("RGB", (32, 32), (255, 0, 0))
        p = tmp_path / "diffuse.png"
        img.save(p)
        result = extract_alpha_from_diffuse(p)
        assert result is None

    def test_nonexistent_returns_none(self, tmp_path):
        result = extract_alpha_from_diffuse(tmp_path / "missing.png")
        assert result is None

    def test_custom_output_path(self, tmp_path):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[:, :, 3] = 100
        img = Image.fromarray(arr, "RGBA")
        p = tmp_path / "diffuse.png"
        out = tmp_path / "my_alpha.png"
        img.save(p)
        result = extract_alpha_from_diffuse(p, output_path=out)
        assert result == out


class TestStripAlphaFromDiffuse:
    """Tests for strip_alpha_from_diffuse."""

    def test_strips_alpha_from_rgba(self, tmp_path):
        img = Image.new("RGBA", (32, 32), (255, 0, 0, 128))
        p = tmp_path / "diffuse.png"
        img.save(p)
        result = strip_alpha_from_diffuse(p)
        assert result is True
        assert Image.open(p).mode == "RGB"

    def test_rgb_returns_false(self, tmp_path):
        img = Image.new("RGB", (32, 32), (255, 0, 0))
        p = tmp_path / "diffuse.png"
        img.save(p)
        assert strip_alpha_from_diffuse(p) is False

    def test_nonexistent_returns_false(self, tmp_path):
        assert strip_alpha_from_diffuse(tmp_path / "missing.png") is False


class TestNormalizeAlphaTexture:
    """Tests for normalize_alpha_texture."""

    def test_standard_convention_no_change(self, tmp_path):
        # Black corners (transparent) = standard, no inversion needed
        arr = np.zeros((64, 64), dtype=np.uint8)
        arr[20:44, 20:44] = 255  # White center "leaf"
        img = Image.fromarray(arr, "L")
        p = tmp_path / "alpha.png"
        img.save(p)
        result = normalize_alpha_texture(p)
        assert result is False  # No change needed

    def test_inverted_convention_gets_inverted(self, tmp_path):
        # White corners (bright background) = inverted, should flip
        arr = np.full((64, 64), 255, dtype=np.uint8)
        arr[20:44, 20:44] = 0  # Black center "leaf"
        img = Image.fromarray(arr, "L")
        p = tmp_path / "alpha.png"
        img.save(p)
        result = normalize_alpha_texture(p)
        assert result is True
        # After normalization, corners should be dark
        normalized = np.array(Image.open(p))
        corner_val = normalized[0:5, 0:5].mean()
        assert corner_val < 100

    def test_nonexistent_returns_false(self, tmp_path):
        assert normalize_alpha_texture(tmp_path / "missing.png") is False

    def test_tiny_image_returns_false(self, tmp_path):
        img = Image.new("L", (4, 4), 200)
        p = tmp_path / "tiny.png"
        img.save(p)
        assert normalize_alpha_texture(p) is False


class TestTextureWarningLogs:
    """Tests verifying warning messages on failure paths."""

    def test_extract_alpha_logs_warning_on_corrupt_file(self, tmp_path, caplog):
        p = tmp_path / "corrupt.png"
        p.write_bytes(b"not a real image")
        with caplog.at_level(logging.WARNING, logger="growpy.io.texture_utils"):
            result = extract_alpha_from_diffuse(p)
        assert result is None
        assert "Failed to extract alpha" in caplog.text

    def test_strip_alpha_logs_warning_on_corrupt_file(self, tmp_path, caplog):
        p = tmp_path / "corrupt.png"
        p.write_bytes(b"not a real image")
        with caplog.at_level(logging.WARNING, logger="growpy.io.texture_utils"):
            result = strip_alpha_from_diffuse(p)
        assert result is False
        assert "Failed to strip alpha" in caplog.text

    def test_normalize_alpha_logs_warning_on_corrupt_file(self, tmp_path, caplog):
        p = tmp_path / "corrupt.png"
        p.write_bytes(b"not a real image")
        with caplog.at_level(logging.WARNING, logger="growpy.io.texture_utils"):
            result = normalize_alpha_texture(p)
        assert result is False
        assert "Failed to normalize alpha" in caplog.text
