# Generate Python Tests

**Purpose**: Create comprehensive pytest test suites for existing Python code.

## Requirements

1. **Test Structure**:
   - Use pytest framework conventions
   - Organize tests in `tests/` directory
   - Mirror source structure: `tests/test_module.py` for `src/project/module.py`
   - Use clear, descriptive test function names

2. **Test Coverage**:
   - Test happy path scenarios
   - Test edge cases and boundary conditions
   - Test error scenarios with appropriate exceptions
   - Test different input combinations
   - Focus on critical business logic

3. **Test Patterns**:
   - Use fixtures for setup and teardown
   - Mock external dependencies and API calls
   - Use parametrized tests for multiple inputs
   - Keep tests independent and isolated

4. **Code Style**:
   - Follow Black formatting
   - Minimal comments, descriptive test names
   - Use type hints where helpful
   - Clean, readable assertions

5. **Data and Mocking**:
   - Use pytest fixtures for test data
   - Mock external services and databases
   - Use temporary files/directories for file operations
   - Clean up resources after tests

6. **Integration with Linear**:
   - Reference Linear issue context
   - Validate acceptance criteria from Linear issues
   - Remove test files after validation if requested

## Template Variables

- `targetModule`: Python module to test
- `testScope`: Type of tests (unit, integration, end-to-end)
- `mockingNeeds`: External dependencies to mock
- `linearContext`: Related Linear issue or requirements

## Usage

Run this prompt with: `/test`

Then specify:
- Target module or function to test
- Specific test scenarios needed
- Linear issue context if applicable