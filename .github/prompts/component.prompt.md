# Generate Python Module

**Purpose**: Create a new Python module following project patterns and best practices.

## Requirements

1. **Module Structure**:
   - Create the main module file in `src/project_name/`
   - Include proper type hints
   - Add minimal, meaningful docstrings
   - Follow package-style imports

2. **Code Style**:
   - Use Black formatting (88 char line length)
   - Minimal comments, self-documenting code
   - Shallow indentation, avoid nested if/else
   - Early returns for error conditions

3. **Testing**:
   - Generate pytest tests in `tests/`
   - Test main functionality and edge cases
   - Use descriptive test function names
   - Clean up test files after validation

4. **Dependencies**:
   - Prefer standard library when possible
   - Add new dependencies to environment.yml if needed
   - Use type hints for better code clarity

5. **Integration**:
   - Follow existing project structure
   - Update `__init__.py` exports if needed
   - Consider Linear issue context

## Template Variables

- `moduleName`: Name of the module to create
- `functionality`: Core functionality to implement
- `dependencies`: Required packages or modules
- `linearIssue`: Related Linear issue ID

## Usage

Run this prompt with: `/component`

Then specify:
- Module name and purpose
- Core functionality needed
- Any Linear issue context