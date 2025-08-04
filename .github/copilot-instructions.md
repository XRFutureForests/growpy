````instructions
# GitHub Copilot Instructions - The Grove Repository

## Repository Role: Logic Tier - Tree Asset Generation Service

This repository implements the **Tree Asset Generation Service** within the Logic Tier of the XR Future Forests Lab architecture. It generates realistic 3D tree models using The Grove core engine to match real forest data from the Digital Twin database.

## Project Context

- **Multi-Repository Architecture**: Part of 3-tier system (Data/Logic/Presentation)
- **Linear Project**: Create Virtual Forest Ecosense (`50992750-6878-41ca-92a4-520f9ee40c0c`)
- **Team**: XR Future Forests (`5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf`)
- **Timeline**: July 18 - September 19, 2025
- **Lead**: Paul Lakos
- **My Role**: Tree generation using The Grove core for VR integration

## Architecture Integration

### Input Sources (Data Tier)
- **Tree Database**: PostgreSQL tree measurements and species data via Tree API
- **CSV Format**: Tree positions, species, heights, DBH measurements
- **Species Mapping**: `data/tree_asset_lookup.csv` maps database species to Grove presets

### Processing (Logic Tier)
- **The Grove 22**: Procedural tree generation engine
- **Growth Simulation**: Age calculations and development cycles
- **Species Modeling**: Realistic tree characteristics per species
- **LOD Generation**: Multiple levels of detail for performance

### Output (Presentation Tier)
- **USD Files**: Universal Scene Description format for Unity/Unreal
- **Point Instancing**: Optimized twig/leaf rendering
- **Multi-LOD**: Distance-based detail switching
- **VR Integration**: Delivered to Paul's Unity VR forest system

## Current Implementation Status

### ✅ **Completed Components**
- **Core Pipeline**: `debug_grove_core.py` - main testing and generation script
- **Species Mapping**: Complete lookup table with 15+ species
- **Grove Integration**: Python wrapper around The Grove core (`src/growpy/`)
- **LOD System**: Multiple detail levels for performance optimization
- **Basic USD Export**: Tree models exported in Universal Scene Description format
- **Twig Integration**: Point-instanced small branches and leaves

### 🔧 **Current Priority (Due Aug 15)**
- **Twig Orientation Fixes**: Point-instanced twigs not facing correct direction in USD export
- **Technical Challenge**: USD point instancer orientation matrix calculation
- **Impact**: Affects visual realism in VR forest visualization

### 📋 **Planned Enhancements**
- **Database API Integration**: Direct connection to Digital Twin PostgreSQL database
- **Growth Model Improvements**: More sophisticated age/height relationships
- **Performance Optimization**: Batch processing for large forest plots
- **Quality Assurance**: Automated validation of generated models

## Technical Stack

### Core Technologies
- **The Grove 22**: Blender addon and core Python library for procedural tree generation
- **Python 3.11+**: Main development language
- **USD (Universal Scene Description)**: 3D scene format for VR integration
- **scikit-learn**: Species classification and data analysis
- **NumPy/Pandas**: Data processing and mathematical operations

### Key Dependencies
- **growpy**: Custom Python wrapper for The Grove core
- **usd-core**: USD library for 3D scene description
- **the_grove_22**: The Grove Python modules

### File Structure
```
src/growpy/           # Custom Grove integration modules
data/
  ├── tree_asset_lookup.csv    # Species to Grove preset mapping
  ├── input/small_demo.csv     # Test data format example
  └── output/                  # Generated USD files
docs/                 # The Grove core documentation
debug_grove_core.py   # Main testing and development script
```

## Grove Core Integration

### Tree Generation Workflow
1. **Input Processing**: Parse CSV with tree positions, species, measurements
2. **Species Mapping**: Map database species names to Grove presets via lookup table
3. **Age Calculation**: Derive tree age from height using species-specific growth curves
4. **Grove Generation**: Use The Grove to create realistic tree geometry
5. **LOD Creation**: Generate multiple detail levels for performance
6. **USD Export**: Export as Universal Scene Description for VR integration

### Species Support
Current species mapping includes:
- **Fagus sylvatica** (European Beech)
- **Quercus robur** (English Oak)
- **Pinus sylvestris** (Scots Pine)
- **Abies alba** (Silver Fir)
- **Picea abies** (Norway Spruce)
- And 10+ additional European forest species

### Growth Modeling
- **Age Calculation**: Height-to-age conversion using species-specific curves
- **DBH Integration**: Diameter at breast height influences trunk thickness
- **Realistic Proportions**: Crown size and shape based on species characteristics
- **Seasonal Variation**: Future support for different growth phases

## Development Patterns

### The Grove Core API Usage
```python
# Initialize Grove with species preset
grove = Grove()
grove.load_preset(species_preset)

# Set tree parameters from database
grove.set_age(calculated_age)
grove.set_height(measured_height)
grove.set_trunk_diameter(dbh_measurement)

# Generate tree geometry
tree_geometry = grove.generate()

# Export with LOD levels
export_usd(tree_geometry, output_path, lod_levels=[1, 2, 3])
```

### CSV Data Format
```csv
tree_id,species,x,y,height_m,dbh_cm
1,Fagus sylvatica,125.3,78.9,24.7,35.2
2,Quercus robur,143.1,92.4,19.2,28.7
```

### Species Mapping Pattern
```python
# Load species lookup table
species_map = pd.read_csv('data/tree_asset_lookup.csv')

# Map database species to Grove presets
grove_preset = species_map[species_map['database_species'] == 'Fagus sylvatica']['grove_preset'].iloc[0]
```

## Critical Issues & Solutions

### Twig Orientation Problem (HIGH PRIORITY)
**Issue**: Point-instanced twigs not oriented correctly in USD export
**Impact**: Affects visual realism in VR forest
**Technical Details**: USD point instancer orientation matrix calculation
**Files Affected**: USD export functions in `src/growpy/`
**Deadline**: August 15, 2025

### Database Integration (MEDIUM PRIORITY)
**Current**: CSV file input via `data/input/small_demo.csv`
**Target**: Direct PostgreSQL connection to Digital Twin database
**API**: Tree API endpoints from Digital Twin repository
**Benefits**: Real-time tree data updates, automated processing

### Performance Optimization (LOW PRIORITY)
**Challenge**: Large forest plots with 1000+ trees
**Solutions**: Batch processing, LOD optimization, caching
**Metrics**: Target <5 minutes for 500-tree forest plot

## Testing & Validation

### Development Workflow
1. **Test with Demo Data**: Use `data/input/small_demo.csv` for testing
2. **Run Generation Script**: Execute `debug_grove_core.py` for development
3. **Validate USD Output**: Check generated files in `data/output/`
4. **VR Integration Test**: Coordinate with Paul for Unity import validation

### Quality Assurance
- **Species Accuracy**: Verify tree characteristics match real species
- **Scale Validation**: Ensure measurements correspond to input data
- **Visual Quality**: Assess realism in VR environment
- **Performance Metrics**: Monitor generation time and file sizes

## Documentation References

### The Grove Core Documentation
- `docs/the_grove_core.md` - Main API documentation
- `docs/the_grove_core.Grove.md` - Grove class reference
- `docs/the_grove_core.Model.md` - Tree model system
- `docs/tldr.md` - Quick reference guide

### Workflow Documentation
- `docs/growpy/TWIG_WORKFLOW.md` - Twig integration process
- `TWIG_ORIENTATION_FIXES.md` - Current orientation issue details
- `LINEAR_WORKSPACE_GUIDE.md` - Project management context

## Coordination with Other Repositories

### Digital Twin Repository (Data Tier)
- **Data Source**: Tree measurements and species information
- **API Integration**: Tree API for real-time data access
- **Spatial Data**: Position coordinates and plot boundaries

### Potree Docker Repository (Logic Tier)
- **Point Cloud Context**: LiDAR data for tree detection validation
- **Visualization Platform**: Web-based forest visualization
- **Coordinate Systems**: Shared spatial reference systems

### External Integration (Presentation Tier)
- **Paul Lakos Unity VR**: Primary consumer of generated tree assets
- **USD Format**: Standard interchange format for VR integration
- **Performance Requirements**: VR-optimized geometry and textures

## Development Environment

### Setup Requirements
```bash
# Install The Grove 22 (Blender addon)
# Install Python dependencies
pip install -r environment.yml

# Test basic functionality
python debug_grove_core.py
```

### Key Environment Variables
- `GROVE_PATH`: Path to The Grove installation
- `USD_PATH`: Path to USD library installation
- `OUTPUT_PATH`: Default output directory for generated assets

## Project Status (August 2025)

- **Foundation**: ✅ Complete - Core pipeline operational
- **Twig Orientation**: 🔧 High Priority - Technical blocker for VR integration
- **Database Integration**: 📋 Planned - API connection to Digital Twin
- **Performance Optimization**: 📋 Future - Batch processing improvements
- **Documentation**: 📋 Ongoing - Usage guides and API documentation

This repository delivers realistic tree assets that bridge forest science data with immersive VR experiences, enabling unprecedented forest visualization and research capabilities.
````
