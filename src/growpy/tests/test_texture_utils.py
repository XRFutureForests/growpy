"""Tests for growpy.io.texture_utils module."""

import pytest

from growpy.io.texture_utils import is_power_of_2, next_power_of_2


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
