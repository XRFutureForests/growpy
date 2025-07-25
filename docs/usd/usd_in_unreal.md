# USD Integration in Unreal Engine for Grove Trees

This document covers how Grove's USD export integrates with Unreal Engine's USD Stage system, focusing on transformations, skeletal animation, and instancing for tree models with wind animation and twig instances.

## Overview

Grove trees exported as USD integrate seamlessly with Unreal Engine's USD Stage workflow, providing:

- **Native USD representation** without conversion to Static/Skeletal Meshes
- **Live USD data updates** as source files change
- **Skeletal animation support** for wind effects using USD's skeleton schema
- **Efficient instancing** using USD's PointInstancer primitives
- **Runtime USD loading** for dynamic forest generation

## Unreal Engine USD Stage Workflow

### USD Stage Actor

Grove trees are loaded into Unreal Engine through USD Stage Actors:

```cpp
// Blueprint node to load Grove trees at runtime
Set Root Layer: /path/to/grove_forest.usda

// Or via C++
#include "USDStageActor.h"

AUSDStageActor* StageActor = GetWorld()->SpawnActor<AUSDStageActor>();
StageActor->SetRootLayer(TEXT("/Game/Trees/grove_forest.usda"));
```

### Grove Forest Structure

A typical Grove forest USD file structure in Unreal:

```
/Grove (UsdGeomXform)
├── /Grove/Tree0 (UsdGeomXform)
│   ├── /Grove/Tree0/Geometry (UsdGeomMesh)
│   ├── /Grove/Tree0/Skeleton (UsdSkelSkeleton)
│   └── /Grove/Tree0/TwigInstances (UsdGeomPointInstancer)
├── /Grove/Tree1 (UsdGeomXform)
│   ├── /Grove/Tree1/Geometry (UsdGeomMesh)
│   ├── /Grove/Tree1/Skeleton (UsdSkelSkeleton)  
│   └── /Grove/Tree1/TwigInstances (UsdGeomPointInstancer)
└── /Grove/Environment (UsdGeomXform)
    ├── /Grove/Environment/Terrain (UsdGeomMesh)
    └── /Grove/Environment/Lighting (UsdLuxDomeLight)
```

```

## Coordinate System and Transformations

### Unreal Engine Coordinate System

Unreal Engine uses Z-up, which matches Grove's USD export when configured properly:

```python
# Grove export for Unreal Engine
model.set_up_axis("Z")  # Match Unreal's Z-up system
model.set_winding_order("COUNTER_CLOCKWISE")  # Unreal's default winding
```

### Transform Animation

USD xform animations are imported as Transform tracks in Unreal's Level Sequences:

```usda
def Xform "Tree0"
{
    # Animated transformations for growth or movement
    matrix4d xformOp:transform.timeSamples = {
        1: ((1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1)),
        24: ((1.2,0,0,0), (0,1.2,0,0), (0,0,1.2,0), (2,1,0,1)),
        48: ((1.5,0,0,0), (0,1.5,0,0), (0,0,1.5,0), (5,2,0,1))
    }
    uniform token[] xformOpOrder = ["xformOp:transform"]
}
```

#### Level Sequence Integration

In Unreal Engine:

1. **Automatic Level Sequence**: USD Stage Actor creates Level Sequence for animations
2. **Transform Tracks**: Xform animations become transform tracks
3. **Time Synchronization**: USD timeline maps to Unreal's timeline
4. **Playback Control**: Standard Unreal animation controls apply

### World Positioning

Each tree's world transform is preserved through USD's transform hierarchy:

```cpp
// Access tree transform in Blueprint/C++
FTransform TreeTransform = USDStageActor->GetPrimTransform("/Grove/Tree0");

// Modify tree position
USDStageActor->SetPrimTransform("/Grove/Tree0", NewTransform);
```

## Skeletal Animation System

### USD Skeleton in Unreal

Grove skeletons are represented as Skeletal Mesh Components in Unreal:

```usda
def SkelRoot "Tree0"
{
    def Skeleton "Skeleton"
    {
        uniform token[] joints = [
            "Root",
            "Root/Trunk", 
            "Root/Trunk/MainBranch0",
            "Root/Trunk/MainBranch0/SubBranch0"
        ]
        
        # Bind poses for each joint
        uniform matrix4d[] bindTransforms = [...]
        
        # Rest poses
        uniform matrix4d[] restTransforms = [...]
    }
    
    def Mesh "TreeMesh" (
        prepend apiSchemas = ["SkelBindingAPI"]
    )
    {
        # Skeleton binding
        rel skel:skeleton = </Tree0/Skeleton>
        
        # Joint influences
        int[] primvars:skel:jointIndices = [...] (
            interpolation = "vertex"
        )
        float[] primvars:skel:jointWeights = [...] (
            interpolation = "vertex" 
        )
    }
}
```

### Wind Animation Implementation

Grove provides sophisticated wind animation through skeletal deformation and shape-based systems:

```usda
def Skeleton "Skeleton"
{
    # Animated joint transforms for wind with Grove-specific parameters
    matrix4d[] jointTransforms.timeSamples = {
        1: [...],   # Frame 1 - rest pose
        2: [...],   # Frame 2 - wind displacement
        50: [...],  # Frame 50 - wind cycle end
        51: [...]   # Frame 51 - loop back to start
    }
    
    # Grove wind attributes preserved in USD
    float[] primvars:flexibility = [...] (
        interpolation = "varying"
        doc = "Branch flexibility based on Grove radius calculation"
    )
    float[] primvars:wind_frequency = [...] (
        interpolation = "varying"
        doc = "Noise frequency per joint (thin branches = higher frequency)"
    )
    float[] primvars:wind_strength = [...] (
        interpolation = "varying" 
        doc = "Deformation strength per joint based on Grove's wind system"
    )
}
```

#### Grove Wind System Parameters

**Flexibility Calculation**: Grove calculates per-bone flexibility using the formula:

```
flexibility = (bone_radius ^ 0.9)
flexibility = 1.0 / flexibility / 100.0
```

**Frequency Modulation**: Thin branches receive higher frequency noise:

```
noise_frequency = 17.0 * (1.0 / flexibility) ^ 0.3
```

**Strength Modulation**: Wind strength varies by branch thickness:

```
deform_strength = flexibility * turbulence_factor
```

#### Unreal Animation Integration

1. **Animation Sequences**: USD skeletal animation converts to Unreal Animation Sequences with Grove wind timing
2. **Level Sequences**: Wind animation can be controlled through Unreal's Level Sequence system
3. **Animation Blueprints**: Grove wind parameters can drive additional Unreal animation logic
4. **Bone Manipulation**: Individual bones retain Grove flexibility data for runtime modification
5. **Physics Integration**: Grove skeleton can interact with Unreal's wind simulation systems

#### Real-Time Wind Enhancement

Combine Grove's USD wind with Unreal's runtime systems:

```cpp
// Enhanced wind system using Grove data
UCLASS(BlueprintType)
class YOURPROJECT_API UGroveWindComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    float WindStrength = 1.0f;
    
    UPROPERTY(BlueprintReadWrite, EditAnywhere) 
    FVector WindDirection = FVector(1, 0, 0);
    
    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    float TurbulenceScale = 1.0f;
    
    // Apply wind using Grove flexibility data
    UFUNCTION(BlueprintCallable)
    void ApplyGroveWindToSkeleton(AUSDStageActor* StageActor, const FString& SkeletonPath)
    {
        // Read Grove flexibility attributes from USD
        TArray<float> FlexibilityData;
        StageActor->GetPrimAttribute(SkeletonPath, "flexibility", FlexibilityData);
        
        // Apply wind forces based on Grove's flexibility calculation
        for (int32 BoneIndex = 0; BoneIndex < FlexibilityData.Num(); BoneIndex++)
        {
            float Flexibility = FlexibilityData[BoneIndex];
            float NoiseFreq = 17.0f * FMath::Pow(1.0f / Flexibility, 0.3f);
            float NoiseStrength = Flexibility * TurbulenceScale;
            
            // Apply to bone transform with Grove-consistent parameters
            ApplyWindToBone(BoneIndex, NoiseFreq, NoiseStrength);
        }
    }
};
```

## Instancing and Point Instancers

### USD PointInstancer in Unreal

Grove's twig instancing uses USD PointInstancers which Unreal handles efficiently:

```usda
def PointInstancer "TwigInstances"
{
    # Instance positions (centers of twig triangles)
    point3f[] positions = [
        (1.2, 2.3, 3.4),
        (2.1, 3.2, 4.1),
        # ... thousands of twig positions
    ]
    
    # Instance orientations from triangle normals
    quath[] orientations = [
        (1, 0, 0, 0),
        (0.707, 0, 0, 0.707),
        # ... corresponding orientations
    ]
    
    # Instance scales for variation
    float3[] scales = [
        (0.8, 0.8, 0.8),
        (1.2, 1.2, 1.2),
        # ... scale variations
    ]
    
    # Which twig prototype to use
    int[] protoIndices = [0, 1, 0, 2, 3, 1, ...]
    
    # References to twig prototypes
    rel prototypes = [
        </TwigPrototypes/TwigLong>,
        </TwigPrototypes/TwigShort>, 
        </TwigPrototypes/TwigUpward>,
        </TwigPrototypes/TwigDead>
    ]
}
```

### Unreal Instancing Performance

Unreal Engine optimizes USD PointInstancers as:

1. **Hierarchical Instanced Static Meshes (HISM)**: Automatic conversion for performance
2. **GPU Instancing**: Efficient rendering of thousands of instances
3. **Culling Support**: Automatic frustum and occlusion culling
4. **LOD Integration**: Distance-based level of detail

#### Instance Data Access

```cpp
// Access instance data in C++
#include "USDStageActor.h"

// Get instance transforms
TArray<FTransform> InstanceTransforms;
USDStageActor->GetInstanceTransforms("/Grove/Tree0/TwigInstances", InstanceTransforms);

// Modify individual instances
USDStageActor->SetInstanceTransform("/Grove/Tree0/TwigInstances", InstanceIndex, NewTransform);
```

### Twig Prototype Management

Twig prototypes are managed as separate USD references:

```usda
def "TwigPrototypes"
{
    def Mesh "TwigLong" (
        prepend references = @./twigs/long_twig.usda@
    )
    {
        # Twig geometry and materials
    }
    
    def Mesh "TwigShort" (
        prepend references = @./twigs/short_twig.usda@
    )
    {
        # Different twig variation
    }
}
```

## Material and Shading Integration

### USD Preview Surface to UE Materials

Grove's USD materials convert to Unreal Engine materials:

```usda
def Material "BarkMaterial"
{
    token outputs:surface.connect = </BarkMaterial/PreviewSurface.outputs:surface>
    
    def Shader "PreviewSurface"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.6, 0.4, 0.2)
        float inputs:roughness = 0.8
        float inputs:metallic = 0.0
        asset inputs:diffuseColor.connect = </BarkMaterial/DiffuseTexture.outputs:rgb>
        asset inputs:normal.connect = </BarkMaterial/NormalTexture.outputs:rgb>
    }
    
    def Shader "DiffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bark_diffuse.jpg@
        token inputs:sourceColorSpace = "sRGB"
    }
}
```

#### Unreal Material Conversion

1. **Preview Surface → Material**: Automatic conversion to Unreal material nodes
2. **Texture Loading**: USD texture references load as Unreal texture assets
3. **Parameter Exposure**: Material parameters can be modified in real-time
4. **Custom Shaders**: Support for custom material expressions

### Attribute-Driven Materials

Grove's custom attributes can drive material parameters:

```cpp
// Use Grove attributes in materials
// Create dynamic material instances based on Grove data

UMaterialInstanceDynamic* TreeMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);

// Set parameters based on Grove attributes
float TreeAge = GetGroveAttribute("age");
TreeMaterial->SetScalarParameterValue("TreeAge", TreeAge);

float TreeHealth = GetGroveAttribute("photosynthesis"); 
TreeMaterial->SetScalarParameterValue("Health", TreeHealth);
```

## Runtime USD Manipulation

### Dynamic Forest Generation

Grove trees can be loaded and positioned at runtime:

```cpp
// Runtime forest generation
UCLASS(BlueprintType)
class YOURPROJECT_API AForestGenerator : public AActor
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    TArray<FString> TreeUSDPaths;
    
    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    int32 ForestSize = 100;
    
    UFUNCTION(BlueprintCallable)
    void GenerateForest();
    
private:
    UPROPERTY()
    AUSDStageActor* ForestStage;
};

void AForestGenerator::GenerateForest()
{
    // Create USD stage for forest
    ForestStage = GetWorld()->SpawnActor<AUSDStageActor>();
    
    // Generate forest layout
    for (int32 i = 0; i < ForestSize; i++)
    {
        FVector TreePosition = GenerateTreePosition(i);
        FString TreePath = TreeUSDPaths[FMath::RandRange(0, TreeUSDPaths.Num() - 1)];
        
        // Add tree reference to stage
        AddTreeToStage(TreePath, TreePosition, i);
    }
    
    ForestStage->ReloadStage();
}
```

### Live USD Updates

Unreal Engine supports live updates to USD data:

```cpp
// Monitor USD file changes
UFUNCTION()
void OnUSDFileChanged(const FString& FilePath)
{
    // Automatically reload stage when source USD files change
    if (USDStageActor && USDStageActor->GetRootLayer().ToString().Contains(FilePath))
    {
        USDStageActor->ReloadStage();
    }
}
```

## Animation and Sequencer Integration

### Growth Animation

Grove growth animation integrates with Unreal's Sequencer:

1. **Time-Varying Geometry**: Animated mesh topology over time
2. **Sequence Tracks**: Growth stages as keyframe animation
3. **Morph Targets**: Smooth transitions between growth stages
4. **Event Triggers**: Gameplay events based on growth stages

### Wind Animation Control

Combine USD skeleton animation with Unreal's systems:

```cpp
// Wind animation controller
UCLASS(BlueprintType)
class YOURPROJECT_API AWindController : public AActor
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    UCurveFloat* WindIntensityCurve;
    
    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    FVector GlobalWindDirection = FVector(1, 0, 0);
    
    UFUNCTION(BlueprintCallable)
    void UpdateTreeWindAnimation(AUSDStageActor* StageActor, float DeltaTime);
    
private:
    float CurrentWindTime = 0.0f;
};
```

## Performance Optimization

### LOD Systems

Implement distance-based LOD for Grove trees:

```cpp
// LOD management for Grove trees
UCLASS()
class YOURPROJECT_API UGroveLODManager : public UObject
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere)
    float HighDetailDistance = 500.0f;
    
    UPROPERTY(EditAnywhere)
    float MediumDetailDistance = 1000.0f;
    
    UPROPERTY(EditAnywhere)
    float LowDetailDistance = 2000.0f;
    
    UFUNCTION()
    void UpdateTreeLOD(AUSDStageActor* StageActor, const FVector& ViewerLocation);
};
```

### Culling and Visibility

Optimize large forests with proper culling:

```cpp
// Frustum culling for tree instances
void UpdateTreeVisibility(const FVector& CameraLocation, const FMatrix& ViewProjectionMatrix)
{
    for (const FString& TreePath : VisibleTreePaths)
    {
        bool bIsVisible = IsTreeInFrustum(TreePath, ViewProjectionMatrix);
        USDStageActor->SetPrimVisibility(TreePath, bIsVisible);
    }
}
```

## Blueprint Integration

### Blueprint Accessible Functions

Key USD operations exposed to Blueprints:

```cpp
// Blueprint library for Grove USD operations
UCLASS(BlueprintType)
class YOURPROJECT_API UGroveBlueprintLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Grove USD")
    static void LoadGroveTree(AUSDStageActor* StageActor, const FString& TreeUSDPath);
    
    UFUNCTION(BlueprintCallable, Category = "Grove USD")
    static void SetTreeTransform(AUSDStageActor* StageActor, const FString& TreePath, const FTransform& Transform);
    
    UFUNCTION(BlueprintCallable, Category = "Grove USD")
    static float GetTreeAttribute(AUSDStageActor* StageActor, const FString& TreePath, const FString& AttributeName);
    
    UFUNCTION(BlueprintCallable, Category = "Grove USD")
    static void SetWindStrength(AUSDStageActor* StageActor, const FString& TreePath, float WindStrength);
    
    UFUNCTION(BlueprintCallable, Category = "Grove USD")
    static TArray<FTransform> GetTwigInstanceTransforms(AUSDStageActor* StageActor, const FString& InstancerPath);
};
```

### Event System

Create events for Grove tree interactions:

```cpp
// Event delegates for Grove trees
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnTreeLoaded, const FString&, TreePath);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTreeAttributeChanged, const FString&, TreePath, const FString&, AttributeName);

UCLASS(BlueprintType)
class YOURPROJECT_API AGroveTreeManager : public AActor
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintAssignable)
    FOnTreeLoaded OnTreeLoaded;
    
    UPROPERTY(BlueprintAssignable) 
    FOnTreeAttributeChanged OnTreeAttributeChanged;
};
```

## Troubleshooting and Best Practices

### Common Issues

1. **Coordinate System Mismatch**: Ensure USD exported with Z-up for Unreal
2. **Performance**: Large forests may need LOD and culling systems
3. **Material Conversion**: Complex materials may need manual adjustment
4. **Animation Sync**: Verify USD animation timeline matches Unreal's expected frame rate

### Best Practices

1. **File Organization**: Use relative paths and organized directory structures
2. **Reference Management**: Use USD references for shared twig prototypes
3. **Performance Testing**: Profile large scenes early in development
4. **Version Control**: Use USD text format (.usda) for version control
5. **Validation**: Test USD files in `usdview` before importing to Unreal
6. **Streaming**: Consider USD payload system for large worlds
7. **Backup**: Keep source Grove files separate from USD exports

### Performance Guidelines

- **Instance Count**: Optimize for 10,000+ twig instances per tree
- **Draw Calls**: Use HISM for efficient instanced rendering
- **Memory**: Monitor texture memory usage with high-resolution bark textures
- **CPU**: Minimize real-time USD manipulations in performance-critical code
- **GPU**: Leverage GPU instancing for twig rendering

## Advanced Integration

### Custom USD Schemas

Extend USD with Grove-specific schemas:

```cpp
// Define custom Grove schema
class UsdGroveTree : public UsdGeomXform
{
public:
    // Grove-specific attributes and methods
    UsdAttribute GetAgeAttr() const;
    UsdAttribute GetSpeciesAttr() const;
    UsdAttribute GetHealthAttr() const;
    
    // Grove-specific operations
    bool SetWindResponse(float strength, const GfVec3f& direction);
    bool TriggerGrowth(int years);
};
```

### Plugin Development

Create Unreal Engine plugins for Grove USD integration:

```cpp
// Grove USD plugin module
class FGroveUSDModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
    
private:
    void RegisterGroveUSDTypes();
    void SetupGroveImporters();
};
```

This comprehensive integration enables Grove trees to work seamlessly within Unreal Engine's USD pipeline, providing efficient rendering, animation, and real-time manipulation capabilities for forest visualization and interactive applications.
