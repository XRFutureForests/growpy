# GrowPy Testing Guide

This document describes how to run the comprehensive test suite for GrowPy.

## Test Structure

The test suite is organized into several categories:

### Unit Tests (`tests/test_*.py`)

- **test_config.py**: Tests for configuration classes and enums
- **test_growpy.py**: Tests for core functionality with mocked Grove dependencies
- No external dependencies required
- Can run without Grove installation

### Integration Tests (`tests/test_integration.py`)

- Tests with real Grove functionality
- Requires The Grove 2.2 to be installed
- Tests actual tree generation and export
- Marked with `@pytest.mark.integration`

## Prerequisites

### Required Dependencies

```bash
pip install -r requirements-test.txt
```

### Optional: The Grove 2.2

- Integration tests require The Grove 2.2 to be installed
- Unit tests work without Grove

## Running Tests

### Quick Test Run

```bash
# Run all unit tests (no Grove required)
python -m pytest tests/test_config.py tests/test_growpy.py -v

# Run integration tests (Grove required)
python -m pytest tests/test_integration.py -v

# Run all tests
python -m pytest tests/ -v
```

### Using the Test Runner Script

```bash
# Unit tests only (no Grove required)
python run_tests.py unit --verbose

# Integration tests only (Grove required)
python run_tests.py integration --verbose

# Fast tests (excludes slow integration tests)
python run_tests.py fast --verbose

# All tests
python run_tests.py all --verbose

# With coverage report
python run_tests.py unit --coverage
```

### Test Selection

#### By Markers

```bash
# Run only unit tests
pytest -m "not integration"

# Run only integration tests  
pytest -m "integration"

# Skip slow tests
pytest -m "not slow"
```

#### By Test File

```bash
# Configuration tests only
pytest tests/test_config.py

# Core functionality tests
pytest tests/test_growpy.py

# Integration tests
pytest tests/test_integration.py
```

#### By Test Function

```bash
# Specific test function
pytest tests/test_config.py::TestGrowPyConfig::test_default_config

# Test class
pytest tests/test_growpy.py::TestListSpecies
```

## Test Categories

### Configuration Tests (`test_config.py`)

- ✅ Enum value validation
- ✅ Default configuration values
- ✅ Custom configuration creation
- ✅ Grove build options conversion
- ✅ Path handling
- ✅ Boolean and numeric settings

### Core Functionality Tests (`test_growpy.py`)

- ✅ Species listing with various scenarios
- ✅ Grove info retrieval
- ✅ Species preset application
- ✅ CSV validation (missing columns, null values)
- ✅ Tree generation modes (individual/combined)
- ✅ Export functionality (OBJ/USD)
- ✅ Error handling and validation

### Integration Tests (`test_integration.py`)

- ✅ Real Grove availability detection
- ✅ Actual species listing from presets
- ✅ Real tree generation (minimal settings)
- ✅ Export format testing
- ✅ Enhanced features (position variation, coordinate systems)
- ✅ Error propagation from Grove

## Coverage Reports

Generate coverage reports:

```bash
# HTML coverage report
pytest --cov=growpy --cov-report=html tests/

# Terminal coverage report
pytest --cov=growpy --cov-report=term tests/

# Combined
python run_tests.py unit --coverage
```

Coverage reports will be generated in `htmlcov/` directory.

## Continuous Integration

### Minimal CI Setup

```bash
# Install dependencies
pip install -r requirements-test.txt

# Run unit tests (no Grove required)
pytest tests/test_config.py tests/test_growpy.py

# Optional: Run integration tests if Grove is available
pytest tests/test_integration.py || echo "Integration tests skipped - Grove not available"
```

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - run: pip install -r requirements-test.txt
    - run: pytest tests/test_config.py tests/test_growpy.py -v
```

## Test Data

### Sample CSV Data

The test fixtures create realistic CSV data with proper structure:

```csv
x,y,z,species
0.0,0.0,0.0,Fagaceae - Beech
5.0,2.0,0.0,Fagaceae - European oak
-3.0,4.0,0.0,Fagaceae - Beech
```

### Temporary Files

- Tests use `tempfile` for creating test files
- Automatic cleanup after each test
- No persistent test artifacts

## Troubleshooting

### Common Issues

#### Import Errors

```
ImportError: No module named 'the_grove_22_core'
```

**Solution**: This is expected for unit tests. Integration tests will be skipped automatically.

#### Species Not Found

```
GrowPyError: Unknown species: ['NonExistentSpecies']
```

**Solution**: Integration tests use only species found in the actual Grove installation.

#### Permission Errors

```
PermissionError: [Errno 13] Permission denied
```

**Solution**: Ensure write permissions for output directories. Tests use temporary directories by default.

### Test Debugging

#### Verbose Output

```bash
pytest -v -s tests/test_growpy.py::TestListSpecies::test_list_species_with_presets
```

#### Print Debugging

Add print statements in tests (they'll show with `-s` flag):

```python
def test_something(self):
    result = some_function()
    print(f"Debug: result = {result}")  # Will show with -s
    assert result == expected
```

#### Test Fixtures

Access test fixtures for debugging:

```python
def test_debug_csv(self, sample_csv_data):
    print(sample_csv_data)  # Show the test data
    # ... rest of test
```

## Best Practices

### Test Organization

- Keep unit tests fast and isolated
- Use mocks for external dependencies
- Integration tests should be minimal and focused
- Group related tests in classes

### Test Data

- Use fixtures for reusable test data
- Create realistic but minimal test cases
- Clean up temporary files automatically

### Error Testing

- Test both success and failure cases
- Verify specific error messages
- Use `pytest.raises()` for expected exceptions

### Mocking

- Mock external dependencies in unit tests
- Use `patch()` for Grove functionality in unit tests
- Verify mock calls to ensure correct API usage

## Running Specific Test Scenarios

### Testing Configuration

```bash
# Test only configuration functionality
pytest tests/test_config.py -v
```

### Testing Error Handling

```bash
# Test error scenarios
pytest tests/test_growpy.py::TestGenerateTreesValidation -v
```

### Testing Export Formats

```bash
# Test OBJ/USD export (requires Grove)
pytest tests/test_integration.py::TestExportFormats -v
```

### Testing with Different Grove Editions

```bash
# Test what works with current Grove edition
pytest tests/test_integration.py -v
```

This comprehensive test suite ensures GrowPy works correctly across different scenarios and Grove configurations.
