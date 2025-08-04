# The Grove Repository - Logic Tier Tree Asset Generation

> **Multi-Repository Architecture**: Logic Tier - Tree Asset Generation Service  
> **University**: University of Freiburg, Department of Forest Sciences  
> **Status**: Core Implementation Phase | **Priority**: Twig Orientation Fixes (Due Aug 15)

This repository implements the **Tree Asset Generation Service** within the Logic Tier of the XR Future Forests Lab multi-repository architecture, generating realistic 3D tree models for VR forest visualization.

## **Repository Role in XR Future Forests Lab**

### **🌲 Logic Tier - Tree Asset Generation Service**

- **The Grove 22**: Procedural tree generation using forest science data
- **Species Modeling**: Realistic tree characteristics based on database species
- **USD Export**: Universal Scene Description format for VR integration
- **Growth Simulation**: Age-based tree development and morphology

### **🔗 Multi-Repository Architecture**

- **📋 [Planning Hub](../xr-future-forests-lab)**: Central coordination and architecture documentation
- **🗄️ [Digital Twin](../digital-twin)**: Data Tier - provides Tree API for species and measurement data
- **☁️ [Potree Docker](../potree-docker)**: Logic Tier - Point Cloud Processing (coordinate validation)

## **Project Integration**

### **Input Sources (Data Tier)**

- **Tree Database**: PostgreSQL tree measurements and species data via Tree API
- **CSV Format**: Tree positions, species, heights, DBH measurements from Digital Twin
- **Species Mapping**: Database species names mapped to Grove presets via lookup table

### **Processing (Logic Tier)**

- **The Grove Core**: Procedural tree generation engine with Python integration
- **Growth Modeling**: Age calculations and realistic development cycles
- **Species Accuracy**: Scientifically accurate tree characteristics per European species
- **LOD Generation**: Multiple levels of detail for VR performance optimization

### **Output (Presentation Tier)**

- **USD Files**: Universal Scene Description format for Unity/Unreal integration
- **Point Instancing**: Optimized twig and leaf rendering for VR performance
- **Multi-LOD**: Distance-based detail switching for immersive experiences
- **VR Integration**: Delivered to Paul Lakos Unity VR forest system

## **Current Implementation Status**

### ✅ **Completed Foundation**

- **Core Pipeline**: Functional tree generation from CSV input (`debug_grove_core.py`)
- **Species Mapping**: Complete lookup table with 15+ European forest species
- **Grove Integration**: Python wrapper around The Grove core (`src/growpy/`)
- **LOD System**: Multiple detail levels for VR performance optimization
- **Basic USD Export**: Tree models exported in Universal Scene Description format
- **Twig Integration**: Point-instanced small branches and leaves implementation

### 🔧 **Current Priority (HIGH - Due Aug 15)**

- **Twig Orientation Fixes**: Point-instanced twigs not facing correct direction in USD export
- **Technical Challenge**: USD point instancer orientation matrix calculation
- **Impact**: Critical for visual realism in VR forest visualization
- **Blocker**: Affects integration with Paul's Unity VR system

### 📋 **Planned Enhancements**

- **Database API Integration**: Direct connection to Digital Twin PostgreSQL database
- **Growth Model Improvements**: More sophisticated age/height relationships
- **Performance Optimization**: Batch processing for large forest plots (500+ trees)
- **Quality Assurance**: Automated validation of generated tree models

## **Technical Stack**

### **Core Technologies**

- **The Grove 22**: Blender addon and core Python library for procedural tree generation
- **Python 3.11+**: Main development language with scientific computing libraries
- **USD (Universal Scene Description)**: 3D scene format for VR application integration
- **scikit-learn**: Species classification and data analysis
- **NumPy/Pandas**: Mathematical operations and data processing

### **File Structure**

```
src/growpy/                           # Custom Grove integration modules
data/
  ├── tree_asset_lookup.csv          # Species to Grove preset mapping
  ├── input/small_demo.csv           # Test data format example
  └── output/                        # Generated USD tree files
docs/                               # The Grove core API documentation
debug_grove_core.py                 # Main testing and development script
environment.yml                    # Python environment dependencies
```

## **Grove Core Integration Workflow**

### **Tree Generation Process**

1. **Input Processing**: Parse CSV with tree positions, species, height/DBH measurements
2. **Species Mapping**: Map database species names to Grove presets via lookup table
3. **Age Calculation**: Derive tree age from height using species-specific growth curves
4. **Grove Generation**: Use The Grove to create realistic tree geometry and structure
5. **LOD Creation**: Generate multiple detail levels for VR performance optimization
6. **USD Export**: Export as Universal Scene Description for Unity/Unreal integration

### **Species Support (15+ European Species)**

- **Fagus sylvatica** (European Beech) - Deciduous broad-leaved
- **Quercus robur** (English Oak) - Deciduous broad-leaved with distinctive branching
- **Pinus sylvestris** (Scots Pine) - Coniferous with characteristic crown shape
- **Abies alba** (Silver Fir) - Coniferous with regular branching pattern
- **Picea abies** (Norway Spruce) - Coniferous with drooping branches
- **Betula pendula** (Silver Birch) - Deciduous with distinctive bark
- And 10+ additional Central European forest species

### **Growth Modeling Features**

- **Age Calculation**: Height-to-age conversion using species-specific growth curves
- **DBH Integration**: Diameter at breast height influences trunk thickness and taper
- **Realistic Proportions**: Crown size and shape based on species characteristics
- **Seasonal Variation**: Support for different growth phases and maturity levels

## **Development Environment**

### **Setup Requirements**

```bash
# Install Conda environment
conda env create -f environment.yml
conda activate the-grove

# Install The Grove 22 (Blender addon)
# Download and install The Grove from official source

# Test basic functionality
python debug_grove_core.py
```

### **Key Environment Variables**

- `GROVE_PATH`: Path to The Grove installation directory
- `USD_PATH`: Path to USD library installation
- `OUTPUT_PATH`: Default output directory for generated tree assets

## **Integration with Multi-Repository Architecture**

### **Digital Twin Repository (Data Tier)**

- **Tree API**: Species data, measurements, growth parameters
- **Spatial Data**: Tree positions and plot boundaries in shared coordinate system
- **Species Database**: Scientific names mapped to Grove generation presets
- **Measurement Validation**: Height, DBH, crown dimensions for accuracy

### **Potree Docker Repository (Logic Tier)**

- **Point Cloud Context**: LiDAR data for tree detection validation
- **Spatial Coordination**: Shared coordinate systems and spatial reference
- **Detection Results**: Tree positions from point cloud analysis
- **Quality Assessment**: Compare generated models with LiDAR scans

### **External VR Integration (Presentation Tier)**

- **Paul Lakos Unity VR**: Primary consumer of generated tree assets
- **USD Standard**: Universal interchange format for VR applications
- **Performance Requirements**: VR-optimized geometry and texture resolution
- **Real-time Loading**: Efficient asset streaming for immersive experiences

## **Critical Technical Issues**

### **🔥 Twig Orientation Problem (HIGH PRIORITY)**

- **Issue**: Point-instanced twigs not oriented correctly in USD export
- **Impact**: Affects visual realism and scientific accuracy in VR forest
- **Technical Details**: USD point instancer orientation matrix calculation
- **Files Affected**: USD export functions in `src/growpy/` modules
- **Deadline**: August 15, 2025 - Required for VR integration milestone

### **Database Integration (MEDIUM PRIORITY)**

- **Current State**: CSV file input via `data/input/small_demo.csv`
- **Target State**: Direct PostgreSQL connection to Digital Twin database
- **Benefits**: Real-time tree data updates, automated processing, data consistency
- **API Integration**: Tree API endpoints for species and measurement data

### **Performance Optimization (LOW PRIORITY)**

- **Challenge**: Large forest plots with 500-1000+ trees
- **Solutions**: Batch processing, intelligent LOD optimization, result caching
- **Target Metrics**: <5 minutes generation time for 500-tree forest plot

## **Testing and Validation**

### **Development Workflow**

1. **Test with Demo Data**: Use `data/input/small_demo.csv` for development testing
2. **Run Generation Script**: Execute `debug_grove_core.py` for rapid iteration
3. **Validate USD Output**: Check generated files in `data/output/` directory
4. **VR Integration Test**: Coordinate with Paul for Unity import validation

### **Quality Assurance Criteria**

- **Species Accuracy**: Tree characteristics match real species morphology
- **Scale Validation**: Generated dimensions correspond to input measurements
- **Visual Quality**: Realistic appearance suitable for scientific VR applications
- **Performance Metrics**: Generation time and file size optimization

## **Documentation and Resources**

### **The Grove Core Documentation**

- `docs/the_grove_core.md` - Main API reference and usage patterns
- `docs/the_grove_core.Grove.md` - Grove class methods and properties
- `docs/the_grove_core.Model.md` - Tree model system and customization
- `docs/tldr.md` - Quick reference guide for common operations

### **Workflow and Integration**

- `docs/growpy/TWIG_WORKFLOW.md` - Twig integration process documentation
- `TWIG_ORIENTATION_FIXES.md` - Current orientation issue analysis
- `LINEAR_WORKSPACE_GUIDE.md` - Project management and team coordination

## **Project Status (August 2025)**

- **✅ Foundation**: Complete - Core pipeline operational and tested
- **🔧 Twig Orientation**: High Priority - Technical blocker for VR integration
- **📋 Database Integration**: Planned - API connection to Digital Twin repository
- **📋 Performance**: Future - Batch processing for large forest visualizations
- **📋 Documentation**: Ongoing - Usage guides and integration documentation

This repository bridges forest science data with immersive VR experiences, enabling unprecedented forest visualization and research capabilities through realistic, scientifically accurate tree asset generation.
