# Python Code Review with Linear Context

**Purpose**: Perform comprehensive code review focusing on Python best practices, performance, and Linear workflow integration.

## Review Checklist

### 1. **Python Code Quality**
- [ ] Code follows Black formatting standards
- [ ] Type hints are used appropriately
- [ ] Functions have clear, descriptive names
- [ ] Minimal comments, self-documenting code
- [ ] Shallow indentation, avoid nested conditionals
- [ ] Early returns for error conditions

### 2. **Functionality & Logic**
- [ ] Code implements Linear issue requirements
- [ ] Edge cases are handled properly
- [ ] Error handling with meaningful messages
- [ ] Input validation where needed
- [ ] Business logic is correct and efficient

### 3. **Testing & Quality**
- [ ] pytest tests cover main functionality
- [ ] Tests are independent and isolated
- [ ] Appropriate use of fixtures and mocking
- [ ] Test names are descriptive
- [ ] Tests validate Linear acceptance criteria

### 4. **Performance & Efficiency**
- [ ] Efficient algorithms and data structures
- [ ] Appropriate use of pandas/numpy for data operations
- [ ] Database queries are optimized (if applicable)
- [ ] Memory usage is reasonable
- [ ] No obvious performance bottlenecks

### 5. **Dependencies & Environment**
- [ ] Dependencies are minimal and necessary
- [ ] environment.yml is updated if needed
- [ ] Conda environment compatibility
- [ ] Docker configuration works correctly

### 6. **Linear Workflow Integration**
- [ ] Code addresses Linear issue requirements
- [ ] Acceptance criteria are met
- [ ] Changes are properly scoped
- [ ] Ready for Linear issue closure

### 7. **Data & Spatial Considerations**
- [ ] PostGIS spatial operations are efficient
- [ ] Data validation for spatial inputs
- [ ] Proper handling of coordinate systems
- [ ] R integration works if applicable

### 8. **Git & Deployment**
- [ ] Changes are properly committed
- [ ] Commit messages are meaningful
- [ ] GitLab CI pipeline will pass
- [ ] Docker build/deployment considerations

## Review Process

1. **Check Linear Context**: Review related Linear issues and requirements
2. **Analyze Code**: Examine Python code quality and patterns
3. **Validate Testing**: Ensure pytest coverage and quality
4. **Performance Check**: Look for efficiency issues
5. **Integration Verify**: Check Docker, conda, and CI compatibility
6. **Provide Feedback**: Specific, actionable suggestions

## Usage

Run this prompt with: `/review`

Then specify:
- Files or changes to review
- Related Linear issue context
- Priority level and focus areas