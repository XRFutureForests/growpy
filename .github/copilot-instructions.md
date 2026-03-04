# GitHub Copilot Custom Instructions - The Grove Project

This project is **The Grove** - a simplified tree generation system using The Grove 2.2 with FBX export workflow for Unreal Engine 5 Nanite integration.

## Project-Specific Context

### Core Architecture - Forest/Grove/Tree/Twig Hierarchy
- **Forest**: Collection of groves with light competition simulation
- **Grove**: Species-specific tree collection with shared growth models  
- **Tree**: Individual tree instances with mesh + skeleton
- **Twig**: Reusable twig assets exported as FBX

### Key Components
- **`src/growpy/`**: Main Python package with modular structure (config/, core/, io/, cli/, utils/)
- **`src/the_grove_22/`**: The Grove 2.2 Python API integration (external dependency)
- **`data/assets/`**: Tree assets (presets/, textures/, twigs/, growth_models/)
- **Pipeline Scripts**: Four-step workflow in `src/growpy/cli/`

### Critical Dependencies
- **The Grove 2.2**: Commercial 3D tree modeling software with Python API
- **bpy module**: Blender Python API for FBX export (install via conda-forge)
- **Environment**: `environment.yml` with PYTHONPATH set to `./src:./src/the_grove_22/modules`

## Development Environment

- **Primary Language**: Python (specialized for 3D modeling and FBX export)
- **Environment**: Windows with conda (no Docker - native Windows workflow)
- **Package Management**: MANDATORY use of mamba/conda environments - NO pip venv, virtualenv, or poetry
- **Project Management**: Linear with MCP integration for issue tracking
- **Repository**: GitLab for source control

## Essential Workflows

### The Four-Step Pipeline
Always run from conda environment (`conda activate the-grove`):

1. **Asset Preparation**: `python src/growpy/cli/prepare_assets.py` - Copy assets from Grove 2.2
2. **Twig Export**: `python src/growpy/cli/convert_twigs.py` - Convert .blend to USD
3. **Growth Models**: `python src/growpy/cli/create_growth_models.py` - Generate height prediction models
4. **Forest Generation**: `python src/growpy/cli/generate_forest.py` - Multi-species simulation with export

**Complete Pipeline**: `python src/growpy/cli/run_pipeline.py` (runs steps 1-3)

### Critical Commands
```bash
# Environment setup
conda activate the-grove
conda install -c conda-forge bpy pandas numpy scikit-learn matplotlib tqdm

# Development install (enables imports)
pip install -e .

# Check dependencies
python -c "import the_grove_22_core.grove_core as gc; print('Grove API ready')"
```

## Grove 2.2 Integration Patterns

### Importing Grove API
```python
# Always use this import pattern
from growpy.utils.dependencies import gc  # Grove core (the_grove_22_core.grove_core)

# Grove API key methods
grove = gc.Grove()
grove.load_seed("species.seed.json")
grove.add_new_tree(gc.Vector(0,0,0), gc.Vector(0,0,1), 0)
grove.simulate(flushes=10)
grove.build_models(build_options)
```

### Configuration System
- **Species Lookup**: `src/growpy/config/tree_asset_lookup.csv` maps species to assets
- **Config Class**: `GrowPyConfig` handles asset resolution and species data
- **Usage**: `from growpy import get_config; config = get_config()`

### Export Patterns
```python
# FBX export with skeleton (preferred)
from growpy import export_tree_as_fbx
export_tree_as_fbx(grove, "tree.fbx", species_name, include_skeleton=True)

# Twig export from .blend files
from growpy.io import export_twigs_from_blend
export_twigs_from_blend(blend_file, output_dir)
```

## Python Coding Standards

- **Style**: Minimal, clean code with shallow indentation  
- **Formatting**: Use Black formatter (88 char line length)
- **Comments**: Minimal comments, let code be self-documenting
- **Control Flow**: Avoid complex if/else chains, prefer early returns
- **Error Handling**: Simple, meaningful error messages (avoid complex try/except chains)
- **Import Organization**: Group imports in order: standard library, third-party, local imports
- **Grove Integration**: Always import Grove API via `from growpy.utils.dependencies import gc`

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
- **Standard Folders**: `data/`, `src/`, `docs/`, `.config/`, `.vscode/`, `.github/`
- **Source Code**: Package-style structure in `src/growpy/` (modular: config/, core/, io/, cli/, utils/)
- **Grove 2.2 Integration**: External API at `src/the_grove_22/modules/` (PYTHONPATH configured)
- **Asset Management**: `data/assets/` contains species presets, textures, twigs, growth_models
- **Environment**: Project-specific conda environment named `the-grove`
- **Configuration Files**: Species lookup in `src/growpy/config/tree_asset_lookup.csv`
- **PYTHONPATH Critical**: Environment sets `./src:./src/the_grove_22/modules` for Grove API access

### Key Directory Structure
```
the-grove/
├── src/growpy/              # Main package
│   ├── config/             # Species configuration & lookup
│   ├── core/               # Forest/Grove/Tree simulation  
│   ├── io/                 # FBX/USD export functionality
│   ├── cli/                # Four pipeline scripts
│   └── utils/              # Shared utilities & dependencies
├── src/the_grove_22/        # Grove 2.2 API (external)
│   └── modules/            # Python API modules
├── data/assets/            # Tree assets from Grove 2.2
│   ├── presets/           # Species .seed.json files
│   ├── textures/          # Bark/leaf textures  
│   ├── twigs/             # .blend twig files
│   └── growth_models/     # Generated prediction models
└── docs/growpy/           # Complete documentation
```

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


## Additional GitHub Copilot Specific Notes

- Use GitHub Copilot's code completion features effectively
- Leverage Copilot Chat for complex problem-solving
- Follow the same development patterns as outlined in the main instructions

---

*These instructions integrate with Linear MCP workflow for enhanced project management and follow established development patterns for Python/R/PostGIS projects.*