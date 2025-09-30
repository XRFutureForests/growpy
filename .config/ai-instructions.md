# AI Assistant Custom Instructions

## Development Environment

- **Primary Language**: Python (with occasional R for data analysis)
- **Environment**: WSL on Windows with Docker integration
- **Package Management**: MANDATORY use of mamba/conda environments - NO pip venv, virtualenv, or poetry
- **Project Management**: Linear with MCP integration for issue tracking
- **Repository**: GitLab for source control

## Python Coding Standards

- **Style**: Minimal, clean code with shallow indentation
- **Formatting**: Use Black formatter (88 char line length)
- **Comments**: Minimal comments, let code be self-documenting
- **Control Flow**: Avoid complex if/else chains, prefer early returns
- **Error Handling**: Simple, meaningful error messages
- **Main Module**: Always name the main entry point file `main.py` (not package name) for clear project entry point
- **Import Organization**: Group imports in order: standard library, third-party, local imports
- **Type Hints**: Use type hints for function parameters and return values when beneficial
- **Function Length**: Keep functions focused and under 50 lines when possible
- **Class Design**: Follow single responsibility principle, avoid overly complex classes
- **Constants**: Use UPPER_CASE for constants, define them at module level or in separate config module

## Documentation Standards

- **README Structure**: Problem statement, setup instructions, usage examples, contribution guidelines
- **API Documentation**: Focus on examples and common use cases, not exhaustive parameter lists
- **Code Comments**: Only for business rules, complex algorithms, or non-obvious decisions
- **Architecture Decisions**: Simple ADR format for significant technical decisions in `docs/adr/`
- **Change Documentation**: Maintain CHANGELOG.md for user-facing changes following Keep a Changelog format
- **Inline Documentation**: Use docstrings for public APIs, focus on purpose and usage examples
- **Documentation Location**: All project documentation in `docs/` directory, technical specs in `.specify/`

## Project Structure

- **Template Compliance**: This project follows a strict template structure - NEVER deviate from it
- **Standard Folders**: `.docker/`, `data/`, `src/`, `docs/`, `.config/`, `.vscode/`, `.github/`, `.devcontainer/`, `.specify/`
- **Source Code**: Package-style structure in `src/project_name/`
- **Main Entry Point**: Always use `main.py` as the primary entry point file (not package name) for clear project navigation
- **Dependencies**: Keep minimal, prefer standard libraries
- **Environment**: Project-specific conda environment named after project folder
- **Python Packaging**: When creating installable packages, pyproject.toml can be placed in `src/package_name/` OR project root
- **Environment Priority**: ALWAYS use conda/mamba - never pip venv, virtualenv, poetry, or other Python environment tools
- **Configuration Files**: Use `.editorconfig` for cross-editor consistency
- **License**: Include appropriate LICENSE file when creating packages or open-source projects
- **Secrets Management**: Use `.env` files for environment variables (never commit .env to git), provide `.env.example` templates
- **CRITICAL - Folder Adherence**: STRICTLY maintain the defined template folder structure:
  - `data/` - All data files (raw/, input/, output/) - excluded from version control
  - `docs/` - Project documentation and specifications
  - `src/` - Source code in package structure (`src/project_name/`)
  - `.docker/` - **ALL** Docker-related files (Dockerfile, docker-compose.yml, scripts) - NEVER in project root
  - `.config/` - Configuration files including AI instructions
  - `.vscode/` - VS Code configuration and settings
  - `.github/` - GitHub Actions, templates, and GitHub-specific configuration
- **Root Directory**: Keep project root CLEAN - only essential files like README.md, .gitignore, and optionally pyproject.toml
- **Package Configuration**: For Python packages, pyproject.toml can be placed either in project root OR in `src/package_name/` directory
- **PyProject Template**: Use the template at `src/project_name/pyproject.toml.template` as a starting point for Python packaging
- **PYTHONPATH Configuration**: When using `src/` layout with packages, add the `src/` directory to PYTHONPATH for proper imports:
  - **PREFERRED METHOD**: Use `pip install -e .` (editable install) from project root - this is the recommended approach
  - **Environment**: Add `export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"` to environment (only if editable install not possible)
  - **IDE Configuration**: Configure VS Code/PyCharm to recognize `src/` as source root
  - **Development**: Always prefer `pip install -e .` (editable install) to avoid PYTHONPATH complexities

### Python Package Structure Patterns

Choose between two structure patterns based on project complexity:

#### **Flat Structure** (Simple Projects)

**Use for:** Scripts, utilities, small APIs, prototypes (< 500 lines, single domain)

```text
src/project_name/
├── __init__.py
├── main.py              # Entry point
├── config.py            # Configuration
├── models.py            # Data models (if needed)
├── utils.py             # Helper functions
└── exceptions.py        # Custom exceptions
```

#### **Modular Structure** (Growing Projects)

**Use for:** Multi-feature apps, web APIs, data pipelines (500+ lines, multiple features, teams)

```text
src/project_name/
├── __init__.py
├── main.py              # Entry point
├── core/                # Core business logic
│   ├── __init__.py
│   ├── models.py        # Domain models
│   ├── services.py      # Business services
│   ├── exceptions.py    # Domain exceptions
│   └── validators.py    # Input validation
├── data/                # Data access layer
│   ├── __init__.py
│   ├── repositories.py  # Data repositories
│   ├── database.py      # DB connections
│   └── queries.py       # SQL queries/ORM
├── api/                 # API layer (web apps)
│   ├── __init__.py
│   ├── routes.py        # Route definitions
│   ├── schemas.py       # Request/response schemas
│   └── middleware.py    # Custom middleware
├── cli/                 # Command-line interface
│   ├── __init__.py
│   └── commands.py      # CLI commands
└── utils/               # Shared utilities
    ├── __init__.py
    ├── helpers.py       # Generic helpers
    ├── logging.py       # Logging setup
    └── config.py        # Configuration management
```

#### **Structure Migration Path**

Projects naturally evolve: **Flat → Modular**

**Decision Criteria:**

- **Lines of Code:** < 500 (Flat) vs 500+ (Modular)
- **Features:** Single purpose (Flat) vs Multiple features (Modular)
- **Team Size:** 1 developer (Flat) vs 2+ developers (Modular)
- **Maintenance:** Short-term (Flat) vs Long-term (Modular)

## Development Workflow

- **Spec-Driven Process**: Follow constitution -> specification -> plan -> tasks -> implement
- **Specification First**: Always check specs/ directory for project requirements and plans
- **Linear Integration**: Use MCP commands to check current issues and create new ones
- **Git Commits**: Regular commits with short, meaningful messages after significant changes
- **Code Quality**: Enforce consistent formatting and linting through manual tools
- **Versioning**: Use Semantic Versioning (SemVer) for all releases - MAJOR.MINOR.PATCH format
  - MAJOR: Breaking changes or incompatible API changes
  - MINOR: New features that are backward compatible
  - PATCH: Backward compatible bug fixes
  - Pre-release: Use alpha/beta/rc suffixes (1.0.0-alpha.1)
- **Docker**: Use containerized development environment with volume mounts
- **Template Structure Enforcement**: Always place files in their designated template folders - Docker files in `.docker/`, configs in `.config/`, etc.
- **Documentation**: Update documentation alongside code changes, maintain README files
- **Dependency Management**: Keep environment.yml and pyproject.toml dependencies minimal and up-to-date

## Environment Management

- **MANDATORY Conda/Mamba**: ONLY use conda or mamba for Python environment management - NEVER use pip venv, virtualenv, poetry, pipenv, or any other Python environment solutions
- **Conda Environment**: ALWAYS ensure the custom conda environment is activated before running Python commands
- **Environment Activation**: Use `conda activate <project-name>` or `mamba activate <project-name>` before executing any Python-related tasks
- **Environment Creation**: Use `mamba create -n <project-name> python=3.x` for new environments
- **Package Installation**: Use `mamba install` or `conda install` when possible, `pip install` only when packages unavailable in conda-forge
- **Docker Commands**: Always use `docker compose` (with space) instead of `docker-compose` (with hyphen)
- **Python Execution**: Verify environment is active with correct Python interpreter before running scripts

## Linear MCP Integration

- **Always check current issues**: Use `mcp_linear_list_my_issues` when starting work
- **Project context**: Use `mcp_linear_get_project` to understand current project status
- **Issue creation**: Follow interview approach - understand completed vs outstanding work
- **Team coordination**: Reference team IDs and project contexts in issue management

## Database and Spatial Data

- **Preferred DB**: PostgreSQL with PostGIS for spatial data
- **Data Processing**: Efficient queries, consider performance implications
- **Spatial Operations**: Use PostGIS functions for spatial analysis
- **Data Validation**: Validate inputs and handle edge cases

## Security and Best Practices

- **Environment Variables**: Never hardcode secrets, API keys, or sensitive data in code
- **Gitignore Management**: Ensure `.env`, `__pycache__/`, and sensitive files are properly excluded
- **Dependencies**: Pin major versions in environment.yml to avoid breaking changes
- **Input Validation**: Always validate user inputs and external data sources
- **Error Handling**: Implement proper exception handling with meaningful error messages
- **Logging**: Use appropriate logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Database Security**: Use parameterized queries to prevent SQL injection
- **File Permissions**: Set appropriate file permissions for scripts and data files
- **Container Security**: ALWAYS create and use non-root users in Docker images to prevent file permission issues and improve security
- **Docker User Management**: Create non-root users with matching UID/GID to host user when possible to avoid file ownership conflicts

## Configuration Management

- **12-Factor Principles**: Configuration through environment variables, not config files
- **Environment Separation**: Clear separation between dev/staging/prod configurations
- **Secret Management**: Never commit secrets, use environment variables with secure injection
- **Feature Flags**: Simple boolean flags for gradual feature rollouts
- **Configuration Validation**: Validate all required config at application startup
- **Configuration Location**: All config files in `.config/` directory, use `.env.example` templates
- **Runtime Configuration**: Prefer environment variables over configuration files for deployment flexibility

## AI Assistant Behavior

- **Code Generation**: Follow established patterns, minimal and clean
- **Documentation**: Focus on complex logic only, avoid over-commenting
- **No Emojis/Icons**: Never use emojis, icons, or decorative symbols in code, comments, or documentation
- **Git Integration**: Suggest commit messages and regular commits
- **Linear Workflow**: Reference Linear context and update issues appropriately
- **Security Awareness**: Always consider security implications when generating code
- **Performance Considerations**: Be mindful of performance implications in data processing and database operations
- **Folder Structure**: Always create new files in the appropriate standard folders:
  - New Python modules → `src/project_name/`
  - Test data/fixtures → `data/` subdirectories (raw/, input/, output/) - not version controlled
  - Documentation → `docs/`
  - Docker-related → `.docker/`
- **Template Compliance**: NEVER place Docker files, configuration files, or other template-designated files in the project root
- **File Placement Validation**: Before creating ANY file, verify it belongs in the correct template folder according to project structure

## File Naming and Placement Conventions

- **Python Files**: Use snake_case for all Python files and modules
- **Configuration Files**: Place all config files in `.config/` directory (environment.yml, .env.example, etc.)
- **Docker Files**: ALL Docker-related files in `.docker/` (Dockerfile, docker-compose.yml, scripts)
- **Documentation**: Use lowercase with hyphens for markdown files (project-overview.md, api-reference.md)
- **Data Files**: Organize in `data/` subdirectories (raw/, input/, output/, processed/)
- **Scripts**: Utility scripts in `src/project_name/scripts/` or separate `scripts/` folder if standalone
- **GitHub Files**: Templates, workflows, and GitHub-specific configs in `.github/`
- **VS Code Files**: Workspace settings, launch configs, and extensions in `.vscode/`
- **Spec Files**: Project specifications and plans in `.specify/` directory
- **Never in Root**: Avoid placing operational files (Docker, config, scripts) in project root - keep it clean

## Docker Commands

- **Command Format**: Always use `docker compose` (with space) for all Docker Compose operations
- **Examples**:
  - `docker compose up -d` (NOT `docker-compose up -d`)
  - `docker compose exec dev bash` (NOT `docker-compose exec dev bash`)
  - `docker compose down` (NOT `docker-compose down`)
- **Container Naming**: Always use meaningful names and tags for Docker containers and images to avoid automatic hash numbers
- **Consistency**: Apply this format in all documentation, scripts, and instructions

## Docker Compose Configuration

- **Version Field**: NEVER include the deprecated `version:` field in docker-compose.yml files
- **Modern Format**: Docker Compose files should start directly with `services:` without version specification
- **Examples**:

  ```yaml
  # CORRECT - Modern format
  services:
    app:
      build: .
  
  # INCORRECT - Deprecated format
  version: '3.8'
  services:
    app:
      build: .
  ```

- **Build Context**: When docker-compose.yml is in `.docker/` subdirectory, use `context: ..` to reference parent directory
- **Volume Mounts**: Use relative paths from docker-compose.yml location (e.g., `..:/workspace` when compose file is in `.docker/`)

## Technologies and Tools

- **Python**: Core development language
- **R**: Data analysis and statistical computing
- **PostgreSQL/PostGIS**: Spatial database operations
- **Docker**: Containerized development environment (use `docker compose`)
- **mamba/conda**: Environment and package management
- **Black**: Code formatting
- **GitLab**: Source control and CI/CD
- **Linear**: Project management with MCP integration
- **VS Code**: Primary IDE with Copilot integration

---

*These instructions integrate with Linear MCP workflow for enhanced project management and follow established development patterns for Python/R/PostGIS projects.*
