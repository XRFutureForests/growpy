"""Tests for growpy.io.pve_foliage_extractor coordinate conversion functions."""

import pytest

from growpy.io.unreal.pve_foliage_extractor import (
    grove_to_pve_position,
    grove_to_pve_vector,
    quaternion_to_pve_up,
)


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


class TestQuaternionToPveUp:
    """Grove twig orientation is a (w, x, y, z) quaternion, not an up vector.

    Reading it as a 3-vector raised "too many values to unpack (expected 3)"
    for every tree, and the caller swallowed that into a warning -- so PVE
    recipes were silently never written and every assembly failed the PVE
    admission check.
    """

    def test_identity_gives_grove_z_up(self):
        # IDENTITY_QUAT is (1, 0, 0, 0) scalar-first. Grove +Z is up, and PVE
        # carries up in the second component.
        assert quaternion_to_pve_up((1.0, 0.0, 0.0, 0.0)) == [0.0, 1.0, 0.0]

    def test_accepts_four_floats(self):
        # The regression: a 4-tuple must not raise.
        result = quaternion_to_pve_up((0.7071068, 0.0, 0.7071068, 0.0))
        assert len(result) == 3

    def test_half_turn_about_x_flips_up(self):
        # 180 deg about X maps +Z to -Z, which PVE reports as -1 in component 1.
        result = quaternion_to_pve_up((0.0, 1.0, 0.0, 0.0))
        assert result[1] == pytest.approx(-1.0)

    def test_quarter_turn_about_y_puts_up_on_x(self):
        # +90 deg about Y maps +Z to +X.
        s = 0.7071067811865476
        result = quaternion_to_pve_up((s, 0.0, s, 0.0))
        assert result[0] == pytest.approx(1.0, abs=1e-6)
        assert result[1] == pytest.approx(0.0, abs=1e-6)

    def test_result_stays_unit_length(self):
        s = 0.7071067811865476
        for quat in (
            (1.0, 0.0, 0.0, 0.0),
            (s, s, 0.0, 0.0),
            (0.5, 0.5, 0.5, 0.5),
            (0.0, 0.0, 0.0, 1.0),
        ):
            x, y, z = quaternion_to_pve_up(quat)
            assert (x * x + y * y + z * z) == pytest.approx(1.0, abs=1e-9)

    def test_matches_quat_forward_convention(self):
        # Cross-check against the established (w, x, y, z) reader in core.twig:
        # forward (+X) and up (+Z) must stay perpendicular for any rotation.
        from growpy.core.twig import _quat_forward

        for quat in (
            (0.5, 0.5, 0.5, 0.5),
            (0.7071067811865476, 0.0, 0.7071067811865476, 0.0),
            (0.6, 0.0, 0.8, 0.0),
        ):
            fx, fy, fz = _quat_forward(quat)
            # quaternion_to_pve_up returns PVE order [x, z, y]; undo it.
            px, pz, py = quaternion_to_pve_up(quat)
            dot = fx * px + fy * py + fz * pz
            assert dot == pytest.approx(0.0, abs=1e-9)
