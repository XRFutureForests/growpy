# Generate API Route

**Purpose**: Create a new API endpoint with proper validation, error handling, and documentation.

## Requirements

1. **Route Structure**:
   - Follow RESTful conventions
   - Implement proper HTTP methods (GET, POST, PUT, DELETE)
   - Use appropriate status codes
   - Include request/response validation

2. **Security**:
   - Implement authentication/authorization if needed
   - Validate and sanitize all inputs
   - Use HTTPS and secure headers
   - Follow OWASP security guidelines

3. **Error Handling**:
   - Comprehensive error catching
   - Meaningful error messages
   - Proper HTTP status codes
   - Structured error responses

4. **Documentation**:
   - OpenAPI/Swagger documentation
   - Request/response examples
   - Parameter descriptions
   - Error code documentation

5. **Testing**:
   - Unit tests for route handlers
   - Integration tests for full request/response cycle
   - Test various scenarios (success, validation errors, server errors)
   - Performance tests if applicable

6. **Data Handling**:
   - Proper database connections
   - Transaction handling where needed
   - Data validation and transformation
   - Efficient queries and operations

## Template Variables

- `routePath`: The API endpoint path
- `httpMethods`: HTTP methods to implement
- `dataModel`: Data structure for requests/responses
- `authRequired`: Whether authentication is required
- `database`: Database operations needed

## Usage

Run this prompt with: `/api-route`

Then specify:
- Endpoint path and methods
- Data models
- Authentication requirements
- Database operations needed