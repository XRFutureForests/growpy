"""
Tests for GrowPy configuration module.
"""

from pathlib import Path

from growpy.config import GrowPyConfig, ExportFormat


class TestExportFormat:
    """Test ExportFormat enum."""

    def test_export_format_values(self):
        """Test that export formats have correct values."""
        assert ExportFormat.OBJ.value == "obj"
        assert ExportFormat.USD.value == "usd"

    def test_export_format_membership(self):
        """Test enum membership."""
        assert ExportFormat.OBJ in ExportFormat
        assert ExportFormat.USD in ExportFormat


class TestGrowPyConfig:
    """Test GrowPyConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = GrowPyConfig()

        assert config.growth_cycles == 10
        assert config.random_seed is None
        assert config.export_format == ExportFormat.OBJ
        assert config.output_dir == Path("output")
        assert config.resolution == 16
        assert config.add_position_variation is False
        assert config.position_random_shift == 0.5
        assert config.up_axis == "Z"

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = GrowPyConfig(
            growth_cycles=20,
            random_seed=42,
            export_format=ExportFormat.USD,
            output_dir=Path("custom_output"),
            resolution=32,
            add_position_variation=True,
            position_random_shift=1.0,
            up_axis="Y",
        )

        assert config.growth_cycles == 20
        assert config.random_seed == 42
        assert config.export_format == ExportFormat.USD
        assert config.output_dir == Path("custom_output")
        assert config.resolution == 32
        assert config.add_position_variation is True
        assert config.position_random_shift == 1.0
        assert config.up_axis == "Y"

    def test_to_grove_build_options(self):
        """Test conversion to Grove build options."""
        config = GrowPyConfig(resolution=24)
        options = config.to_grove_build_options()

        expected = {
            "resolution": 24,
            "build_end_cap": True,
        }

        assert options == expected

    def test_to_grove_build_options_custom_resolution(self):
        """Test Grove build options with custom resolution."""
        config = GrowPyConfig(resolution=8)
        options = config.to_grove_build_options()

        assert options["resolution"] == 8
        assert options["build_end_cap"] is True

    def test_config_immutability_after_creation(self):
        """Test that config values can be changed after creation."""
        config = GrowPyConfig()

        # Should be able to modify dataclass fields
        config.growth_cycles = 25
        assert config.growth_cycles == 25

        config.export_format = ExportFormat.USD
        assert config.export_format == ExportFormat.USD

    def test_path_handling(self):
        """Test that Path objects are handled correctly."""
        custom_path = Path("/some/custom/path")
        config = GrowPyConfig(output_dir=custom_path)

        assert config.output_dir == custom_path
        assert isinstance(config.output_dir, Path)

    def test_boolean_settings(self):
        """Test boolean configuration options."""
        config = GrowPyConfig(add_position_variation=True)
        assert config.add_position_variation is True

        config = GrowPyConfig(add_position_variation=False)
        assert config.add_position_variation is False

    def test_numeric_settings_validation(self):
        """Test numeric configuration values."""
        config = GrowPyConfig(growth_cycles=5, resolution=64, position_random_shift=2.5)

        assert config.growth_cycles == 5
        assert config.resolution == 64
        assert config.position_random_shift == 2.5

    def test_coordinate_system_settings(self):
        """Test coordinate system configuration."""
        # Z-up (default)
        config_z = GrowPyConfig(up_axis="Z")
        assert config_z.up_axis == "Z"

        # Y-up
        config_y = GrowPyConfig(up_axis="Y")
        assert config_y.up_axis == "Y"
