"""Tests for growpy.io.pve_foliage_extractor coordinate conversion functions."""

import pytest

from growpy.io.unreal.pve_foliage_extractor import grove_to_pve_position, grove_to_pve_vector


class TestGroveToPvePosition:
    """Tests for Grove->PVE position conversion (Z-up meters -> Y-up centimeters)."""

    def test_origin(self):
        result = grove_to_pve_position((0.0, 0.0, 0.0))
        assert result == [0.0, 0.0, 0.0]

    def test_unit_x(self):
        result = grove_to_pve_position((1.0, 0.0, 0.0))
        assert result == [100.0, 0.0, 0.0]

    def test_unit_y(self):
        # Grove Y -> PVE Z (third component)
        result = grove_to_pve_position((0.0, 1.0, 0.0))
        assert result == [0.0, 0.0, 100.0]

    def test_unit_z(self):
        # Grove Z -> PVE Y (second component, up axis)
        result = grove_to_pve_position((0.0, 0.0, 1.0))
        assert result == [0.0, 100.0, 0.0]

    def test_meters_to_centimeters(self):
        result = grove_to_pve_position((2.5, 3.0, 10.0))
        assert result[0] == pytest.approx(250.0)
        assert result[1] == pytest.approx(1000.0)  # Z (height) -> PVE Y
        assert result[2] == pytest.approx(300.0)  # Y -> PVE Z

    def test_negative_values(self):
        result = grove_to_pve_position((-1.0, -2.0, -3.0))
        assert result == [-100.0, -300.0, -200.0]


class TestGroveToPveVector:
    """Tests for Grove->PVE direction vector conversion (axis swap only)."""

    def test_unit_x_preserved(self):
        result = grove_to_pve_vector((1.0, 0.0, 0.0))
        assert result == [1.0, 0.0, 0.0]

    def test_unit_y_swapped_to_z(self):
        result = grove_to_pve_vector((0.0, 1.0, 0.0))
        assert result == [0.0, 0.0, 1.0]

    def test_unit_z_swapped_to_y(self):
        result = grove_to_pve_vector((0.0, 0.0, 1.0))
        assert result == [0.0, 1.0, 0.0]

    def test_no_scaling(self):
        result = grove_to_pve_vector((0.5, 0.5, 0.707))
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.707)
        assert result[2] == pytest.approx(0.5)
