// Copyright Epic Games, Inc. All Rights Reserved.
#pragma once

#include "UDynamicMesh.h"
#include "NaniteAssemblyDataBuilder.h"
#include "Engine/EngineTypes.h"
#include "GeometryCollection/ManagedArrayCollection.h"
#include "Materials/MaterialInterface.h"
#include "Facades/PVBoneFacade.h"
#include "PVExportHelper.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;
class USkeletalMesh;
class UProceduralVegetation;
struct FGeometryScriptCopyMeshToAssetOptions;

UENUM()
enum class EPVExportMeshType: uint8
{
	StaticMesh,
	SkeletalMesh,
};

USTRUCT()
struct PROCEDURALVEGETATION_API FPVExportParams
{
	GENERATED_BODY()

	UPROPERTY()
	bool bShouldExport = true;

	UPROPERTY(EditAnywhere, Category = "Export", Meta = (ContentDir, DisplayName = "Content Browser Folder"))
	FDirectoryPath ContentBrowserFolder;

	UPROPERTY(EditAnywhere, Category = "Export", Meta = (DisplayName = "Mesh Name"))
	FName MeshName;

	UPROPERTY(EditAnywhere, Category = "Export", Meta = (DisplayName = "Export Mesh Type"))
	EPVExportMeshType ExportMeshType = EPVExportMeshType::StaticMesh;

	UPROPERTY(EditAnywhere, Category = "Export", Meta = (DisplayName = "Create Nanite Foliage"))
	bool bCreateNaniteFoliage = true;
	
	UPROPERTY(EditAnywhere, Category = "Export", Meta = (DisplayName = "Nanite Shape Preservation Method"))
	ENaniteShapePreservation NaniteShapePreservation = ENaniteShapePreservation::Voxelize;

	void Initialize(const FString& InAssetPath, const FString& InName)
	{
		FString DefaultDirectory = FPaths::GetPath(InAssetPath);
		ContentBrowserFolder.Path = DefaultDirectory;
		
		MeshName = FName(InName);
	}

	FString GetOutputObjectPath() const
	{
		const FString AssetName = MeshName.ToString();
		const FString OutputPath = ContentBrowserFolder.Path / AssetName + '.' + AssetName;
		return OutputPath;
	}
};

namespace PV::Export::Internal
{
	typedef TFunction<void(const FString& MeshName, int32 InstanceID, int32 VertexStart, int32 VertexCount)> FMeshInstanceCombined;
	
	TObjectPtr<UDynamicMesh> CollectionToDynamicMesh(const FManagedArrayCollection& Collection);

	FGeometryScriptCopyMeshToAssetOptions GetCopyMeshToAssetOptions(
		TArray<TObjectPtr<UMaterialInterface>> InMaterials
	);
	
#if WITH_EDITORONLY_DATA
	FGeometryScriptCopyMeshToAssetOptions GetCopyMeshToAssetOptions(
		TArray<TObjectPtr<UMaterialInterface>> InMaterials,
		const FMeshNaniteSettings& InNaniteSettings,
		const ENaniteShapePreservation InShapePreservation
	);
#endif
	
	void CombineMeshInstancesToDynamicMesh(
		const FManagedArrayCollection& Collection,
		UDynamicMesh* DynamicMesh,
		TArray<TObjectPtr<UMaterialInterface>>& Materials,
		const FMeshInstanceCombined& OnMeshInstanceCombined
	);

#if WITH_EDITOR
	void BuildNaniteAssemblyData(
		const FManagedArrayCollection& Collection,
		UStaticMesh* StaticMesh
	);

	void AddNodeToBuilder(FNaniteAssemblyDataBuilder& AssemblyBuilder,
		const FManagedArrayCollection& Collection,
		const TMap<FString, int32>& InMeshNamePartMap,
		const TMap<FString, TArray<TObjectPtr<UMaterialInterface>>>& InMeshMaterialsMap);
	
#endif

	void ExportCollectionToStaticMesh(
		TObjectPtr<UStaticMesh> ExportMesh,
		const FManagedArrayCollection& Collection,
		bool bBuildNaniteAssemblies,
		ENaniteShapePreservation ShapePreservation
	);

	void ExportCollectionToSkeletalMesh(
		TObjectPtr<USkeletalMesh> ExportMesh,
		const FManagedArrayCollection& Collection,
		ENaniteShapePreservation ShapePreservation,
		bool bBuildNaniteAssemblies
	);

	void AttachProceduralVegetationLink(UObject* InExportedMesh, const TObjectPtr<UProceduralVegetation>& InProceduralVegetation);
	
	void AssignBoneIDsToFoliage(const TArray<Facades::FBoneNode>& Bones, FManagedArrayCollection& Collection);

	void RemoveUnwantedSkinWeights(TObjectPtr<UDynamicMesh> DynamicMesh, const FName ProfileName, const TArray<int32>& VertexBoneIDs,
		int32 FoliageVertexStart, const TArray<Facades::FBoneNode>& BoneNodes);

	void ConvertToDefaultSkeletalMesh(USkeletalMesh* SkeletalMesh,
		FDynamicMesh3* Mesh,
		TArray<TObjectPtr<UMaterialInterface>> Materials
		);
	
}

namespace PV::Export
{
	void PROCEDURALVEGETATION_API ExportCollectionAsMesh(
		const TObjectPtr<UProceduralVegetation> InProceduralVegetation,
		const FManagedArrayCollection& Collection,
		const FManagedArrayCollection& FoliageCollection,
		const FPVExportParams& ExportParams
	);
}
