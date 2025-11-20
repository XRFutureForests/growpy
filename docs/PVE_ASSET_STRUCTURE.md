# PVE Asset Structure and Properties Reference

Comprehensive reference for understanding PVE (Procedural Vegetation Editor) asset types, folder structure, and property configuration based on plugin source code analysis.

## Overview

This document explains:
- ProceduralVegetationPreset data asset properties and their behavior
- Expected folder structure and asset types
- How PVE resolves asset paths at runtime
- Best practices for organizing tree assets in Unreal

Derived from analyzing [ProceduralVegetationPreset.cpp](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp) and [ProceduralVegetationPreset.h](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Public/ProceduralVegetationPreset.h).

## ProceduralVegetationPreset Properties

### Json Directory Path

**Type**: `FDirectoryPath JsonDirectoryPath`
**Category**: Internal (DevelopmentOnly)
**Purpose**: Points to folder containing MegaPlants-format `.json` preset files

**Behavior**:
- Plugin scans this folder for `*.json` files when `UpdateDataAsset()` is called
- Each valid JSON becomes a variant in the `Variants` TMap
- Variant name = JSON filename without extension
- Also looks for `*_meta.json` files for additional metadata

**Example**: `/Game/Trees/Tree_Common_Hazel_01/Instances`

**Code Reference** ([ProceduralVegetationPreset.cpp:75-101](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L75-L101)):

```cpp
IFileManager& FileManager = IFileManager::Get();
TArray<FString> FileNames;
FileManager.FindFiles(FileNames, *JsonDirectoryPath.Path, TEXT("*.json"));

Variants.Empty();
TArray<TSharedPtr<FJsonObject>> MetaFiles;

for (const auto& FileName : FileNames) {
    FString FullPath = JsonDirectoryPath.Path / FileName;
    FManagedArrayCollection Collection;
    FString OutError;

    if (PV::LoadMegaPlantsJsonToCollection(Collection, FullPath, OutError)) {
        Variants.Add(FPaths::GetBaseFilename(FullPath), Collection);
    }
    else if (TSharedPtr<FJsonObject> MetaJson = PV::LoadMetaFileIntoJsonObject(FullPath, OutError)) {
        MetaFiles.Add(MetaJson);
    }
}
```

**Requirements**:
- At least one valid PVE JSON file must exist
- JSON must follow MegaPlants format (globalAttributes, points, primitives)

---

### Foliage Folder

**Type**: `FDirectoryPath FoliageFolder`
**Category**: Internal (DevelopmentOnly)
**Purpose**: Path prefix for foliage mesh asset resolution

**Default Behavior** ([ProceduralVegetationPreset.cpp:38-39](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L38-L39)):

```cpp
UProceduralVegetationPreset::UProceduralVegetationPreset()
{
    FString AssetPath = FPackageName::GetLongPackagePath(GetPackage()->GetName());
    FoliageFolder.Path = FPaths::Combine(AssetPath, TEXT("Instances"));
}
```

Automatically set to `<DataAssetPath>/Instances` when data asset is created.

**Override**: Enable `bOverrideFolderPaths` to manually specify different path.

**Resolution Behavior** ([ProceduralVegetationPreset.cpp:202-205](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L202-L205)):

```cpp
for (int32 FoliageIndex = 0; FoliageIndex < FoliageFacade.NumFoliageNames(); FoliageIndex++)
{
    FString ShortName = FoliageFacade.GetFoliageName(FoliageIndex);  // From JSON
    FString FullObjectName = FPaths::Combine(*FoliageFolder.Path, *ShortName);
    FoliageFacade.SetFoliageName(FoliageIndex, FullObjectName);
}
```

**Key Insight**: JSON files contain only **short names** (e.g., `BrLeaf_000`). PVE automatically prefixes with `FoliageFolder.Path` during import.

**Example**:
- JSON contains: `"BrLeaf_000"`
- FoliageFolder: `/Game/Trees/Tree_Common_Hazel_01/Instances`
- Resolved path: `/Game/Trees/Tree_Common_Hazel_01/Instances/BrLeaf_000`

---

### Materials Folder

**Type**: `FDirectoryPath MaterialsFolder`
**Category**: Internal (DevelopmentOnly)
**Purpose**: Path prefix for material asset resolution

**Default Behavior** ([ProceduralVegetationPreset.cpp:40](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L40)):

```cpp
MaterialsFolder.Path = FPaths::Combine(AssetPath, TEXT("Materials"));
```

Automatically set to `<DataAssetPath>/Materials`.

**Override**: Enable `bOverrideFolderPaths` to manually specify.

**Used in combination with `TrunkMaterialName`** (see next section).

---

### Trunk Material Name

**Type**: `FString TrunkMaterialName`
**Category**: Internal (DevelopmentOnly)
**Purpose**: Base name (no path/extension) of trunk material

**Resolution Behavior** ([ProceduralVegetationPreset.cpp:207-215](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L207-L215)):

```cpp
if (!TrunkMaterialName.IsEmpty())
{
    FString FullMaterialName = FPaths::Combine(*MaterialsFolder.Path,
        TrunkMaterialName + '.' + TrunkMaterialName);
    BranchFacade.SetTrunkMaterialPath(FullMaterialName);
}
else
{
    UE_LOG(LogProceduralVegetation, Warning, TEXT("Material name is empty"));
}
```

**Example**:
- TrunkMaterialName: `MI_Broadleaf_Common_Hazel_Bark_01`
- MaterialsFolder: `/Game/Trees/Tree_Common_Hazel_01/Materials`
- Resolved path: `/Game/Trees/Tree_Common_Hazel_01/Materials/MI_Broadleaf_Common_Hazel_Bark_01.MI_Broadleaf_Common_Hazel_Bark_01`

**Important**: Must match exact material instance asset name (without path/extension).

---

### Create Profile Data Asset

**Type**: `bool bCreateProfileDataAsset`
**Category**: Internal (DevelopmentOnly)
**Purpose**: Extract plantProfile arrays into separate `UPlantProfileAsset`

**Behavior** ([ProceduralVegetationPreset.cpp:118-121](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L118-L121)):

```cpp
if (bCreateProfileDataAsset)
{
    CreateProfileDataAsset();
}
```

When enabled during `UpdateDataAsset()`:
1. Creates new `UPlantProfileAsset` with name from `PlantProfileName`
2. Extracts `plantProfile_1` through `plantProfile_5` from each variant
3. Saves as separate data asset in same folder as preset

**Code Reference** ([ProceduralVegetationPreset.cpp:168-191](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp#L168-L191)):

```cpp
void UProceduralVegetationPreset::CreateProfileDataAsset()
{
    FString ProfilePackageName(PlantProfileName);
    FString PackagePath = FPaths::Combine(
        FPackageName::GetLongPackagePath(GetPackage()->GetName()),
        ProfilePackageName
    );
    UPackage* PlantProfilePackage = CreatePackage(*PackagePath);

    UPlantProfileAsset* NewPlantProfileAsset = NewObject<UPlantProfileAsset>(
        PlantProfilePackage, *ProfilePackageName, RF_Public | RF_Standalone
    );

    for (auto& Pair : Variants) {
        PV::Facades::FPlantProfileFacade Facade = PV::Facades::FPlantProfileFacade(Pair.Value);
        for (int32 Index = 0; Index < Facade.NumProfileEntries(); Index++) {
            FPlantProfile Profile;
            Profile.ProfileName = FString::Format(TEXT("Profile_{0}"), {Index});
            auto Points = Facade.GetProfilePoints(Index);
            Profile.ProfilePoints = Points;
            NewPlantProfileAsset->Profiles.Add(Profile);
        }
    }

    IAssetRegistry::Get()->AssetCreated(NewPlantProfileAsset);
    PlantProfilePackage->SetDirtyFlag(true);
}
```

**Use Case**: Share crown profiles across multiple species or create reusable profile libraries.

---

### Plant Profile Name

**Type**: `FString PlantProfileName`
**Category**: Internal (DevelopmentOnly)
**Condition**: Only editable when `bCreateProfileDataAsset` is true
**Purpose**: Name for generated `UPlantProfileAsset`

**Example**: `CommonHazel_PlantProfile`

**Structure of Generated Asset**:

```cpp
UCLASS(BlueprintType)
class UPlantProfileAsset : public UDataAsset
{
    UPROPERTY(VisibleAnywhere, Category="PlantProfile")
    TArray<FPlantProfile> Profiles;
};

USTRUCT(BlueprintType)
struct FPlantProfile
{
    UPROPERTY(VisibleAnywhere, Category="PlantProfile")
    FString ProfileName;  // "Profile_0", "Profile_1", etc.

    UPROPERTY(VisibleAnywhere, Category="PlantProfile")
    TArray<float> ProfilePoints;  // 100-value crown envelope array
};
```

---

## Expected Folder Structure

Based on Quixel MegaPlants sample ([Tree_Common_Hazel_01](../data/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01)):

```
Content/Trees/Tree_Common_Hazel_01/
├── PVE_CommonHazel_01.uasset                # ProceduralVegetation graph asset
├── PVE_Broadleaf_Common_Hazel_01.uasset     # Optional variation graph
├── PVE_CommonHazel_Data.uasset              # ProceduralVegetationPreset
│   ├─ JsonDirectoryPath → "./Instances"
│   ├─ FoliageFolder → "./Instances"
│   ├─ MaterialsFolder → "./Materials"
│   ├─ TrunkMaterialName → "MI_Broadleaf_Common_Hazel_Bark_01"
│   └─ bCreateProfileDataAsset → false
│
├── SK_CommonHazel_01.uasset                 # Skeletal mesh variations
├── SK_CommonHazel_01_Skeleton.uasset        # Skeleton for wind animation
├── SK_CommonHazel_01_Physics.uasset         # Physics asset
├── SK_CommonHazel_02.uasset
├── SK_CommonHazel_02_Skeleton.uasset
├── SK_CommonHazel_02_Physics.uasset
│
├── Instances/                               # JsonDirectoryPath + FoliageFolder
│   ├── Broadleaf_Hazel_01.json              # PVE preset (variant 1)
│   ├── Broadleaf_Hazel_02.json              # PVE preset (variant 2)
│   ├── Broadleaf_Hazel_03.json
│   ├── Broadleaf_Hazel_04.json
│   ├── BrLeaf_000.uasset                    # Static leaf mesh
│   ├── BrLeaf_001.uasset
│   ├── ...
│   ├── BrLeaf_020.uasset
│   ├── BrTwig_000.uasset                    # Twig meshes
│   ├── BrTwig_001.uasset
│   ├── CH_Branch_A.uasset                   # Branch segment meshes
│   ├── CH_Branch_B.uasset
│   ├── CH_Branch_Bent_A.uasset
│   ├── CH_Branch_Up_A.uasset
│   ├── SK_BrLeaf_000.uasset                 # Skeletal leaf (wind)
│   ├── SKM_BrLeaf_000.uasset                # Skeletal mesh instance
│   └── ...
│
├── Materials/                               # MaterialsFolder
│   ├── MI_Broadleaf_Common_Hazel_Bark_01.uasset    # Trunk material
│   ├── MI_Broadleaf_Common_Hazel_Bark_02.uasset
│   └── MI_Broadleaf_Common_Hazel_Foliage_01.uasset # Leaf material
│
└── Textures/
    ├── Common_Hazel_Trunkmat_C.uasset       # Bark color
    ├── Common_Hazel_Trunkmat_NAH.uasset     # Bark normal+AO+height
    ├── Common_Hazel_Trunkmat_Single_C.uasset
    ├── Common_Hazel_Trunkmat_Single_NAH.uasset
    ├── Common_Hazel_Branch_CA.uasset        # Branch color+alpha
    └── Common_Hazel_Branch_NT.uasset        # Branch normal
```

---

## Asset Types by Folder

### Instances/ Folder

**Purpose**: Contains JSON presets and foliage geometry meshes

**Expected Assets**:

| Asset Type | Naming Pattern | Example | Purpose |
|------------|----------------|---------|---------|
| JSON presets | `<Species>_<Variant>.json` | `Broadleaf_Hazel_01.json` | MegaPlants format preset |
| Static leaf meshes | `BrLeaf_###.uasset` | `BrLeaf_000.uasset` | Individual leaf/leaflet geometry |
| Static twig meshes | `BrTwig_###.uasset` | `BrTwig_000.uasset` | Small branch/twig segments |
| Static branch meshes | `<SP>_Branch_<Var>.uasset` | `CH_Branch_A.uasset` | Larger branch segments |
| Skeletal leaf base | `SK_BrLeaf_###.uasset` | `SK_BrLeaf_000.uasset` | Skeletal mesh for wind |
| Skeletal leaf instance | `SKM_BrLeaf_###.uasset` | `SKM_BrLeaf_000.uasset` | Instance of SK_ mesh |
| Skeletons | `SK_*_Skeleton.uasset` | `SK_BrLeaf_000_Skeleton.uasset` | Skeleton asset |

**JSON Format**:
- Must contain: `globalAttributes`, `points`, `primitives` sections
- Foliage mesh names: Short names only (e.g., `"BrLeaf_000"`)
- Material references: May be empty or relative paths

---

### Materials/ Folder

**Purpose**: Material instances for tree rendering

**Expected Assets**:

| Asset Type | Naming Pattern | Example | Purpose |
|------------|----------------|---------|---------|
| Trunk material | `MI_<Species>_Bark_##.uasset` | `MI_Broadleaf_Common_Hazel_Bark_01.uasset` | Tree trunk/branch material |
| Foliage material | `MI_<Species>_Foliage_##.uasset` | `MI_Broadleaf_Common_Hazel_Foliage_01.uasset` | Leaf material |

**Important**: Use material **instances** (MI_), not base materials (M_), for easier per-tree customization.

---

### Textures/ Folder

**Purpose**: Texture assets referenced by materials

**Expected Assets**:

| Texture Type | Naming Pattern | Example | Channels |
|--------------|----------------|---------|----------|
| Bark color | `<Species>_Trunkmat_C.uasset` | `Common_Hazel_Trunkmat_C.uasset` | RGB: Color/Albedo |
| Bark packed | `<Species>_Trunkmat_NAH.uasset` | `Common_Hazel_Trunkmat_NAH.uasset` | R: Normal X, G: Normal Y, B: AO, A: Height |
| Bark single-tile | `<Species>_Trunkmat_Single_*.uasset` | `Common_Hazel_Trunkmat_Single_C.uasset` | Same as above, single tile |
| Branch color+alpha | `<Species>_Branch_CA.uasset` | `Common_Hazel_Branch_CA.uasset` | RGB: Color, A: Opacity mask |
| Branch normal | `<Species>_Branch_NT.uasset` | `Common_Hazel_Branch_NT.uasset` | Normal map |

**Packing Format** (NAH texture):
- **R**: Normal X (compressed)
- **G**: Normal Y (compressed)
- **B**: Ambient Occlusion
- **A**: Height/Displacement

---

## Asset Resolution Flow

```
ProceduralVegetationPreset Data Asset
    │
    ├─ JsonDirectoryPath ──────→ Instances/*.json
    │                               │
    │                               └─ Contains short names: "BrLeaf_000"
    │
    ├─ FoliageFolder ──────────────→ Instances/BrLeaf_000.uasset
    │   (Combines folder + short name from JSON)
    │
    └─ MaterialsFolder + TrunkMaterialName
        │
        └─→ Materials/MI_Bark_01.MI_Bark_01
            (Constructs: Folder/Name.Name)

ProceduralVegetation Graph Asset
    │
    └─ References ProceduralVegetationPreset
        │
        └─ Creates PCG nodes for each variant
            (One output pin per JSON file)
```

---

## Configuration Best Practices

### 1. Use Default Folder Paths

Unless you have special requirements, rely on auto-generated folder paths:
- `FoliageFolder`: `<AssetPath>/Instances`
- `MaterialsFolder`: `<AssetPath>/Materials`

**Why**: Simplifies organization and matches Quixel MegaPlants conventions.

---

### 2. Consistent Material Naming

Ensure `TrunkMaterialName` **exactly matches** the material instance asset name:

```
✓ CORRECT:
  TrunkMaterialName: "MI_Broadleaf_Common_Hazel_Bark_01"
  Asset: MI_Broadleaf_Common_Hazel_Bark_01.uasset

✗ INCORRECT:
  TrunkMaterialName: "MI_Broadleaf_Common_Hazel_Bark_01.MI_Broadleaf_Common_Hazel_Bark_01"
  (Don't include path or duplicate extension)
```

---

### 3. JSON Short Names Only

Keep mesh names in JSON files short (no paths):

```json
// JSON file
{
  "foliage": {
    "meshes": ["BrLeaf_000", "BrLeaf_001", "BrTwig_000"]
  }
}
```

PVE automatically resolves to:
- `/Game/Trees/Tree_Species/Instances/BrLeaf_000`
- `/Game/Trees/Tree_Species/Instances/BrLeaf_001`
- `/Game/Trees/Tree_Species/Instances/BrTwig_000`

---

### 4. Material Instances Over Base Materials

Always use material instances (MI_) not base materials (M_):

**Advantages**:
- Easier per-tree customization
- Parameter overrides without duplicating shaders
- Better for creating seasonal variations

---

### 5. Profile Data Assets for Shared Profiles

Enable `bCreateProfileDataAsset` only when:
- Sharing crown profiles across multiple species
- Building reusable profile libraries
- Need to version-control profile data separately

**Otherwise**: Leave disabled to keep profiles embedded in preset.

---

### 6. Variation Structure

Multiple JSON files in `Instances/` folder create multiple preset variations in single data asset:

```
Instances/
├── Broadleaf_Hazel_01.json  →  Variant "Broadleaf_Hazel_01"
├── Broadleaf_Hazel_02.json  →  Variant "Broadleaf_Hazel_02"
└── Broadleaf_Hazel_03.json  →  Variant "Broadleaf_Hazel_03"

ProceduralVegetationPreset.Variants TMap:
{
  "Broadleaf_Hazel_01": <Collection>,
  "Broadleaf_Hazel_02": <Collection>,
  "Broadleaf_Hazel_03": <Collection>
}
```

Each variant becomes an output pin in the PCG graph.

---

## GrowPy Integration

### Generating Compatible Assets

When using GrowPy to generate PVE-compatible JSON:

```bash
python src/growpy/cli/generate_forest.py --generate-pve-json --quality high
```

**Output Structure**:

```
data/output/forest/
└── pve_presets/
    └── european_beech/
        ├── european_beech_tree_0000.json  # PVE preset
        ├── european_beech_tree_0001.json
        └── european_beech_tree_0002.json
```

**Import to Unreal**:

1. Create folder: `Content/Trees/Tree_European_Beech/Instances/`
2. Copy JSON files to `Instances/` folder
3. Create `ProceduralVegetationPreset` data asset
4. Set `JsonDirectoryPath` to `Instances/` folder
5. Set `TrunkMaterialName` to your bark material
6. Click "Update Data Asset" to load variants

**Result**: 3 variants automatically loaded from JSON files.

---

### Mesh Asset Requirements

PVE expects foliage meshes in `Instances/` folder. For GrowPy workflow:

**Option 1: Import USD Foliage Separately**
- Export twigs from Grove as USD
- Import as static meshes into `Instances/` folder
- Ensure naming matches JSON references

**Option 2: Use Placeholder Meshes**
- Use simple quad/plane meshes as placeholders
- Replace with detailed meshes later
- JSON structure remains compatible

**Option 3: Generate Foliage Meshes Procedurally**
- Use Unreal's procedural mesh tools
- Create meshes at import time from JSON point data
- Advanced: Requires custom PVE node implementation

---

## Troubleshooting

### Material Not Found

**Symptom**: Warning in log: `"Material name is empty"` or material not applied to trunk

**Solution**:
1. Check `TrunkMaterialName` is set in preset data asset
2. Verify material instance exists in `Materials/` folder
3. Ensure name matches exactly (case-sensitive)
4. Check `MaterialsFolder` points to correct path

---

### Foliage Meshes Missing

**Symptom**: Tree generates but no foliage/leaves visible

**Solution**:
1. Verify mesh assets exist in `Instances/` folder
2. Check `FoliageFolder` points to correct path
3. Ensure mesh names in JSON match asset names exactly
4. Look for warnings in Output Log about missing assets

---

### JSON Not Loading

**Symptom**: No variants appear after "Update Data Asset"

**Solution**:
1. Check `JsonDirectoryPath` points to folder containing `.json` files
2. Verify JSON format (use reference from Quixel samples)
3. Look for JSON parsing errors in Output Log
4. Ensure JSON files have `.json` extension (case-sensitive on some platforms)

---

### Profile Data Asset Creation Fails

**Symptom**: Error when `bCreateProfileDataAsset` is enabled

**Solution**:
1. Ensure `PlantProfileName` is set and valid
2. Check JSON contains `plantProfile_1` through `plantProfile_5` arrays
3. Verify write permissions in data asset folder
4. Look for errors in Output Log

---

## Source Code References

All information derived from analyzing:

- [ProceduralVegetationPreset.h](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Public/ProceduralVegetationPreset.h)
- [ProceduralVegetationPreset.cpp](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/ProceduralVegetationPreset.cpp)
- [PVPresetLoaderSettings.h](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Nodes/PVPresetLoaderSettings.h)
- [PVPresetLoaderSettings.cpp](../data/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Nodes/PVPresetLoaderSettings.cpp)

Sample asset structure:
- [Tree_Common_Hazel_01](../data/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/)

---

## See Also

- [PVE Preset Workflow](PVE_PRESET_WORKFLOW.md) - Complete import workflow and usage guide
- [PVE Attribute Reference](PVE_ATTRIBUTE_REFERENCE.md) - Detailed JSON attribute documentation
- [PlantProfile Reference](PLANTPROFILE_REFERENCE.md) - Crown profile array specification
