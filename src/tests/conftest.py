"""
Pytest configuration and fixtures for GrowPy tests.
"""

import pytest
import tempfile
import pandas as pd
from pathlib import Path
import sys

# Add growpy to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_csv_data():
    """Create sample CSV data for testing."""
    return pd.DataFrame(
        {
            "x": [0.0, 5.0, -3.0, 2.0],
            "y": [0.0, 2.0, 4.0, -1.0],
            "z": [0.0, 0.0, 0.0, 0.0],
            "species": [
                "Fagaceae - Beech",
                "Fagaceae - European oak",
                "Fagaceae - Beech",
                "Fagaceae - Red oak",
            ],
        }
    )


@pytest.fixture
def temp_csv_file(sample_csv_data):
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as f:
        sample_csv_data.to_csv(f.name, index=False)
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def invalid_csv_data():
    """Create invalid CSV data for testing error cases."""
    return pd.DataFrame(
        {
            "x": [0.0, 5.0],
            "y": [0.0, 2.0],
            # Missing 'z' column and 'species' column
        }
    )


@pytest.fixture
def invalid_csv_file(invalid_csv_data):
    """Create an invalid CSV file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as f:
        invalid_csv_data.to_csv(f.name, index=False)
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def csv_with_invalid_species():
    """Create CSV with invalid species names."""
    data = pd.DataFrame(
        {
            "x": [0.0, 5.0],
            "y": [0.0, 2.0],
            "z": [0.0, 0.0],
            "species": ["NonExistentSpecies", "AnotherFakeSpecies"],
        }
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as f:
        data.to_csv(f.name, index=False)
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)
