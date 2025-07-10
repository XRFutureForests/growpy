"""
Tests for core GrowPy functionality.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, mock_open

import growpy
from growpy import GrowPyConfig, ExportFormat, GrowPyError
from growpy.growpy import apply_species_preset


class TestListSpecies:
    """Test species listing functionality."""

    def test_list_species_with_presets(self):
        """Test that species are listed correctly when presets exist."""
        with patch("growpy.growpy.DEFAULT_PRESETS_PATH") as mock_path:
            # Mock preset files
            mock_preset_files = [
                MagicMock(
                    stem="Fagaceae - Beech.seed", name="Fagaceae - Beech.seed.json"
                ),
                MagicMock(
                    stem="Fagaceae - European oak.seed",
                    name="Fagaceae - European oak.seed.json",
                ),
                MagicMock(
                    stem="Cupressaceae - Western redcedar.seed",
                    name="Cupressaceae - Western redcedar.seed.json",
                ),
            ]

            mock_path.exists.return_value = True
            mock_path.glob.return_value = mock_preset_files

            species = growpy.list_species()

            expected = [
                "Cupressaceae - Western redcedar",
                "Fagaceae - Beech",
                "Fagaceae - European oak",
            ]
            assert species == expected

    def test_list_species_no_presets_directory(self):
        """Test behavior when presets directory doesn't exist."""
        with patch("growpy.growpy.DEFAULT_PRESETS_PATH") as mock_path:
            mock_path.exists.return_value = False

            species = growpy.list_species()
            assert species == []

    def test_list_species_empty_directory(self):
        """Test behavior when presets directory is empty."""
        with patch("growpy.growpy.DEFAULT_PRESETS_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.glob.return_value = []

            species = growpy.list_species()
            assert species == []


class TestGetGroveInfo:
    """Test Grove information functionality."""

    def test_get_grove_info_success(self):
        """Test successful Grove info retrieval."""
        with patch("growpy.growpy.grove_core") as mock_grove:
            mock_grove.about.release = "2.2.1"
            mock_grove.about.edition = "studio"
            mock_grove.about.about = "The Grove tree generation system"

            info = growpy.get_grove_info()

            expected = {
                "version": "2.2.1",
                "edition": "studio",
                "description": "The Grove tree generation system",
            }
            assert info == expected

    def test_get_grove_info_failure(self):
        """Test Grove info retrieval when attributes are missing."""
        with patch("growpy.growpy.grove_core") as mock_grove:
            # Simulate missing attributes
            del mock_grove.about

            info = growpy.get_grove_info()

            expected = {
                "version": "unknown",
                "edition": "unknown",
                "description": "Grove info unavailable",
            }
            assert info == expected


class TestApplySpeciesPreset:
    """Test species preset application."""

    def test_apply_species_preset_success(self):
        """Test successful preset application."""
        mock_grove = MagicMock()

        with patch("growpy.growpy.DEFAULT_PRESETS_PATH") as mock_path, patch(
            "builtins.open", mock_open(read_data='{"preset": "data"}')
        ), patch("growpy.growpy.grove_core") as mock_grove_core:

            # Setup mocks
            preset_file = mock_path / "Fagaceae - Beech.seed.json"
            preset_file.exists.return_value = True

            mock_properties = MagicMock()
            mock_grove_core.io.properties_from_json_string.return_value = (
                mock_properties
            )

            # Test the function
            result = growpy.growpy.apply_species_preset(mock_grove, "Fagaceae - Beech")

            # Assertions
            assert result is True
            mock_grove_core.io.properties_from_json_string.assert_called_once_with(
                '{"preset": "data"}'
            )
            mock_grove.set_properties.assert_called_once_with(mock_properties)

    def test_apply_species_preset_file_not_found(self):
        """Test preset application when file doesn't exist."""
        mock_grove = MagicMock()

        with patch("growpy.growpy.DEFAULT_PRESETS_PATH") as mock_path:
            preset_file = mock_path / "NonExistent.seed.json"
            preset_file.exists.return_value = False

            result = growpy.growpy.apply_species_preset(mock_grove, "NonExistent")

            assert result is False

    def test_apply_species_preset_json_error(self):
        """Test preset application when JSON loading fails."""
        mock_grove = MagicMock()

        with patch("growpy.growpy.DEFAULT_PRESETS_PATH") as mock_path, patch(
            "builtins.open", mock_open(read_data="invalid json")
        ), patch("growpy.growpy.grove_core") as mock_grove_core:

            preset_file = mock_path / "Fagaceae - Beech.seed.json"
            preset_file.exists.return_value = True

            # Simulate JSON parsing error
            mock_grove_core.io.properties_from_json_string.side_effect = Exception(
                "JSON error"
            )

            result = growpy.growpy.apply_species_preset(mock_grove, "Fagaceae - Beech")

            assert result is False


class TestGenerateTreesValidation:
    """Test input validation for generate_trees function."""

    def test_generate_trees_file_not_found(self):
        """Test error when CSV file doesn't exist."""
        with pytest.raises(GrowPyError, match="CSV file not found"):
            growpy.generate_trees("nonexistent.csv")

    def test_generate_trees_invalid_csv(self, invalid_csv_file):
        """Test error with invalid CSV structure."""
        with pytest.raises(GrowPyError, match="Missing columns"):
            growpy.generate_trees(invalid_csv_file)

    def test_generate_trees_invalid_species(self, csv_with_invalid_species):
        """Test error with invalid species names."""
        with patch("growpy.list_species", return_value=["ValidSpecies"]):
            with pytest.raises(GrowPyError, match="Unknown species"):
                growpy.generate_trees(csv_with_invalid_species)

    def test_generate_trees_pandas_error(self, temp_csv_file):
        """Test error when pandas fails to read CSV."""
        with patch("pandas.read_csv", side_effect=Exception("Pandas error")):
            with pytest.raises(GrowPyError, match="Error loading CSV"):
                growpy.generate_trees(temp_csv_file)


class TestGenerateTreesSuccess:
    """Test successful tree generation scenarios."""

    @patch("growpy.growpy.grove_core")
    @patch("growpy.list_species")
    def test_generate_trees_individual_mode(
        self, mock_list_species, mock_grove_core, temp_csv_file, temp_output_dir
    ):
        """Test successful tree generation in individual mode."""
        # Setup mocks
        mock_list_species.return_value = [
            "Fagaceae - Beech",
            "Fagaceae - European oak",
            "Fagaceae - Red oak",
        ]

        mock_grove = MagicMock()
        mock_grove.trees = [MagicMock(), MagicMock()]  # Mock trees list
        mock_grove_core.Grove.return_value = mock_grove

        mock_model = MagicMock()
        mock_grove.build_models.return_value = [mock_model]

        # Mock Grove vector and tree math
        mock_grove_core.Vector = MagicMock
        mock_grove_core.tree_math.add_variation.return_value = (
            [MagicMock(), MagicMock()],  # positions
            [MagicMock(), MagicMock()],  # directions
            [0, 0],  # delays
        )

        # Mock preset application
        with patch("growpy.growpy.apply_species_preset", return_value=True), patch(
            "growpy.growpy._export_model"
        ):

            config = GrowPyConfig(
                output_dir=temp_output_dir,
                growth_cycles=1,
            )

            result = growpy.generate_trees(temp_csv_file, config)

            # Should return list of file paths
            assert isinstance(result, list)
            assert len(result) > 0

    @patch("growpy.growpy.grove_core")
    @patch("growpy.list_species")
    def test_generate_trees_combined_mode(
        self, mock_list_species, mock_grove_core, temp_csv_file, temp_output_dir
    ):
        """Test successful tree generation in combined mode."""
        # Setup mocks
        mock_list_species.return_value = [
            "Fagaceae - Beech",
            "Fagaceae - European oak",
            "Fagaceae - Red oak",
        ]

        mock_grove = MagicMock()
        mock_grove.trees = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]  # Mock trees list
        mock_grove_core.Grove.return_value = mock_grove

        mock_model = MagicMock()
        mock_grove.build_as_one_model.return_value = mock_model

        # Mock Grove vector and tree math
        mock_grove_core.Vector = MagicMock
        mock_grove_core.tree_math.add_variation.return_value = (
            [MagicMock(), MagicMock(), MagicMock(), MagicMock()],  # positions
            [MagicMock(), MagicMock(), MagicMock(), MagicMock()],  # directions
            [0, 0, 0, 0],  # delays
        )

        # Mock preset application
        with patch("growpy.growpy.apply_species_preset", return_value=True), patch(
            "growpy.growpy._export_model"
        ):

            config = GrowPyConfig(
                output_dir=temp_output_dir,
                growth_cycles=1,
            )

            result = growpy.generate_trees(temp_csv_file, config)

            # Should return list with single combined file
            assert isinstance(result, list)
            assert len(result) == 1

    def test_generate_trees_default_config(self, temp_csv_file):
        """Test that default config is used when none provided."""
        with patch(
            "growpy.list_species",
            return_value=[
                "Fagaceae - Beech",
                "Fagaceae - European oak",
                "Fagaceae - Red oak",
            ],
        ), patch(
            "growpy.growpy._generate_individual_species", return_value=["output.obj"]
        ):

            result = growpy.generate_trees(temp_csv_file)

            assert isinstance(result, list)


class TestCSVValidation:
    """Test CSV data validation."""

    def test_validate_csv_data_success(self, sample_csv_data):
        """Test validation with correct CSV data."""
        # This should not raise any exception
        growpy.growpy._validate_csv_data(sample_csv_data)

    def test_validate_csv_data_missing_columns(self):
        """Test validation with missing required columns."""
        incomplete_data = pd.DataFrame(
            {
                "x": [1, 2],
                "y": [1, 2],
                # Missing 'z' and 'species'
            }
        )

        with pytest.raises(ValueError, match="Missing columns"):
            growpy.growpy._validate_csv_data(incomplete_data)

    def test_validate_csv_data_null_values(self):
        """Test validation with null values."""
        data_with_nulls = pd.DataFrame(
            {
                "x": [1.0, None],
                "y": [1.0, 2.0],
                "z": [0.0, 0.0],
                "species": ["Species1", "Species2"],
            }
        )

        with pytest.raises(ValueError, match="contains missing values"):
            growpy.growpy._validate_csv_data(data_with_nulls)


class TestExportModel:
    """Test model export functionality."""

    @patch("growpy.growpy.grove_core")
    @patch("builtins.open", new_callable=mock_open)
    def test_export_model_obj_success(
        self, mock_file, mock_grove_core, temp_output_dir
    ):
        """Test successful OBJ export."""
        mock_model = MagicMock()
        mock_grove_core.io.model_to_obj_string.return_value = "obj content"

        config = GrowPyConfig(export_format=ExportFormat.OBJ, up_axis="Y")
        file_path = temp_output_dir / "test.obj"

        growpy.growpy._export_model(mock_model, file_path, ExportFormat.OBJ, config)

        # Check that file was written
        mock_file.assert_called_once_with(file_path, "w")
        mock_file().write.assert_called_once_with("obj content")
        mock_model.set_up_axis.assert_called_once_with("Y")

    @patch("growpy.growpy.grove_core")
    def test_export_model_obj_not_available(self, mock_grove_core, temp_output_dir):
        """Test OBJ export when not available in Grove edition."""
        mock_model = MagicMock()
        # Simulate OBJ export not available
        del mock_grove_core.io.model_to_obj_string

        config = GrowPyConfig(export_format=ExportFormat.OBJ)
        file_path = temp_output_dir / "test.obj"

        with pytest.raises(GrowPyError, match="OBJ export not available"):
            growpy.growpy._export_model(mock_model, file_path, ExportFormat.OBJ, config)

    @patch("growpy.growpy.grove_core")
    @patch("builtins.open", new_callable=mock_open)
    def test_export_model_usd_success(
        self, mock_file, mock_grove_core, temp_output_dir
    ):
        """Test successful USD export."""
        mock_model = MagicMock()
        mock_grove_core.io.model_to_usda_string.return_value = "usd content"

        config = GrowPyConfig(export_format=ExportFormat.USD)
        file_path = temp_output_dir / "test.usd"

        growpy.growpy._export_model(mock_model, file_path, ExportFormat.USD, config)

        # Check that file was written
        mock_file.assert_called_once_with(file_path, "w")
        mock_file().write.assert_called_once_with("usd content")

    def test_export_model_unsupported_format(self, temp_output_dir):
        """Test export with unsupported format."""
        mock_model = MagicMock()
        config = GrowPyConfig()
        file_path = temp_output_dir / "test.unknown"

        # Create a fake format enum
        class FakeFormat:
            value = "unknown"

        with pytest.raises(GrowPyError, match="Unsupported export format"):
            growpy.growpy._export_model(mock_model, file_path, FakeFormat(), config)
