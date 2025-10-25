# Documentation Structure

This document describes the organization of The Grove project documentation.

## Directory Structure

```text
docs/
├── README.md                          # This file
├── GETTING_STARTED.md                 # Quick start guide
├── QUICK_REFERENCE_LOOKUP.md          # Quick reference for asset lookup
├── sources.md                         # Data sources and references
├── houdini.md                         # Houdini integration notes
├── growpy/                            # GrowPy package documentation
│   ├── README.md                      # Package overview
│   ├── USER_GUIDE.md                  # End-user guide
│   ├── GROWPY_GUIDE.md                # Developer guide
│   ├── CONFIGURATION.md               # Configuration system
│   ├── GROVE_INTEGRATION.md           # Grove 2.2 API integration
│   ├── MODULE_OVERVIEW.md             # Module structure
│   ├── COMPLETE_WORKFLOW.md           # End-to-end workflow
│   ├── SPECIES_LOOKUP_GUIDE.md        # Species asset lookup
│   ├── TEXTURE_IMPLEMENTATION.md      # Texture system
│   ├── TWIG_CONVERSION_V2.md          # Twig conversion process
│   ├── TWIG_WORKFLOW_QUICK_REF.md     # Twig workflow reference
│   ├── USD_EXPORT_WITH_TWIGS.md       # USD export guide
│   ├── UNREAL_ENGINE_NANITE.md        # Nanite compatibility
│   ├── UNREAL_IMPORT_GUIDE.md         # Unreal Engine import
│   ├── NANITE_ASSEMBLY_GUIDE.md       # Nanite assembly workflow
│   ├── NANITE_COMPATIBILITY.md        # Nanite requirements
│   └── TWIG_NANITE_ASSEMBLY.md        # Twig Nanite integration
├── guides/                            # User guides
│   ├── GENERATING_SPECIES_LIBRARY.md  # Species library generation
│   └── UNREAL_NANITE_ASSEMBLY.md      # Unreal Nanite assembly
├── the_grove/                         # The Grove 2.2 API docs
│   └── [API reference files]          # Generated API documentation
└── archive/                           # Historical documentation
    ├── README.md                      # Archive index
    └── [archived summaries]           # Development summaries
```

## Documentation Categories

### Getting Started

- **GETTING_STARTED.md**: First steps for new users
- **README.md**: Project overview (in root)
- **CHANGELOG.md**: Version history and notable changes (in root)

### User Documentation

- **docs/growpy/USER_GUIDE.md**: Complete user guide for GrowPy
- **docs/guides/**: Step-by-step guides for common tasks
- **docs/QUICK_REFERENCE_LOOKUP.md**: Quick reference card

### Developer Documentation

- **docs/growpy/GROWPY_GUIDE.md**: Developer guide
- **docs/growpy/MODULE_OVERVIEW.md**: Code organization
- **docs/growpy/GROVE_INTEGRATION.md**: Grove API integration
- **docs/the_grove/**: The Grove 2.2 API reference

### Workflow Documentation

- **docs/growpy/COMPLETE_WORKFLOW.md**: End-to-end pipeline
- **docs/growpy/TWIG_WORKFLOW_QUICK_REF.md**: Twig workflow
- **docs/guides/GENERATING_SPECIES_LIBRARY.md**: Species library workflow

### Integration Guides

- **docs/growpy/UNREAL_ENGINE_NANITE.md**: Unreal Engine integration
- **docs/growpy/NANITE_ASSEMBLY_GUIDE.md**: Nanite assembly process
- **docs/guides/UNREAL_NANITE_ASSEMBLY.md**: Unreal Nanite workflow

### Technical Documentation

- **docs/growpy/CONFIGURATION.md**: Configuration system
- **docs/growpy/TEXTURE_IMPLEMENTATION.md**: Texture system
- **docs/growpy/USD_EXPORT_WITH_TWIGS.md**: USD export details
- **docs/growpy/TWIG_CONVERSION_V2.md**: Twig conversion system

### Historical Documentation

- **docs/archive/**: Development summaries and fix documentation
- See **docs/archive/README.md** for archive organization

## Documentation Standards

### Markdown Format

All documentation uses Markdown with:

- Clear headings and hierarchy
- Code blocks with language tags
- Links to related documentation
- Examples and use cases

### File Naming

- `UPPERCASE_WITH_UNDERSCORES.md` for guides and references
- `lowercase-with-hyphens.md` for specific topics (not currently used)
- README.md for directory overviews

### Content Organization

1. **Overview**: Brief description of purpose
2. **Prerequisites**: What you need to know/have
3. **Main Content**: Step-by-step instructions or reference material
4. **Examples**: Practical examples
5. **Related**: Links to related documentation

## Updating Documentation

When updating documentation:

1. Keep current docs in main `docs/` directory
2. Move superseded docs to `docs/archive/`
3. Update `CHANGELOG.md` with significant changes
4. Update cross-references as needed
5. Follow markdown linting standards

## Finding Documentation

### By Task

- **First time setup**: docs/GETTING_STARTED.md
- **Generate trees**: docs/growpy/COMPLETE_WORKFLOW.md
- **Use with Unreal**: docs/guides/UNREAL_NANITE_ASSEMBLY.md
- **Configure species**: docs/growpy/SPECIES_LOOKUP_GUIDE.md
- **Export USD**: docs/growpy/USD_EXPORT_WITH_TWIGS.md

### By Component

- **GrowPy package**: docs/growpy/
- **Grove API**: docs/the_grove/
- **User guides**: docs/guides/
- **Configuration**: docs/growpy/CONFIGURATION.md
- **Textures**: docs/growpy/TEXTURE_IMPLEMENTATION.md

### By Topic

- **Nanite**: Search for "NANITE" in docs/growpy/ and docs/guides/
- **Twigs**: docs/growpy/TWIG_WORKFLOW_QUICK_REF.md
- **USD**: docs/growpy/USD_EXPORT_WITH_TWIGS.md
- **Species**: docs/growpy/SPECIES_LOOKUP_GUIDE.md
