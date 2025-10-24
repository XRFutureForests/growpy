// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "NaniteAssemblyDataBuilder.h"
#include "NaniteAssemblyEditorUtilsModule.h"

#include "NaniteAssemblyBuilder.generated.h"

UENUM(BlueprintType)
enum class ENaniteAssemblyPartMaterialMerge : uint8
{
	/**
	 * Will remap the part mesh's material slots to material slots with identical materials and will only 
	 * create new material slots for those that are unmatched.
	 */
	MergeIdenticalMaterials,
	/**
	 * Will remap the part mesh's material slots to material slots with identical slot names and will only 
	 * create new material slots for those that are unmatched.
	 */
	MergeIdenticalSlotNames,
	/**
	 * Will remap the part mesh's material slots to material slots in the group by their index, and will
	 * only create new slots if the part mesh has more materials than is currently in the slot group.
	 */
	MergeMaterialIndices
};

USTRUCT(BlueprintType)
struct FNaniteAssemblyMaterialMergeOptions
{
	GENERATED_BODY()

	/** The material slot group index. Only use 0, or values provided by `AddMaterialSlotGroup` on the Nanite Assembly Builder. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	int32 MaterialSlotGroup = 0;

	/** Specifies how to merge the materials within the material slot group. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	ENaniteAssemblyPartMaterialMerge MergeBehavior = ENaniteAssemblyPartMaterialMerge::MergeIdenticalMaterials;

	/** (Optional) An array of material overrides to use. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	TArray<TObjectPtr<UMaterialInterface>> MaterialOverrides;

	bool operator==(const FNaniteAssemblyMaterialMergeOptions& Other)
	{
		return MaterialSlotGroup == Other.MaterialSlotGroup &&
			MergeBehavior == Other.MergeBehavior &&
			MaterialOverrides == Other.MaterialOverrides;
	}
};

USTRUCT(BlueprintType)
struct FNaniteAssemblyCreateNewParameters
{
	GENERATED_BODY()

	/** The content directory in which to store the new mesh asset */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default, meta = (RelativePath, ContentDir))
	FDirectoryPath TargetDirectory;

	/**
	 * The desired name of the new asset.
	 * NOTE: Will be amended if bOverwriteExisting=false
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	FString AssetName;

	/** Whether or not to overwrite the asset if it already exists */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	bool bOverwriteExisting = false;
};

USTRUCT(BlueprintType)
struct FNaniteAssemblySkeletalMeshPartBinding
{
	GENERATED_BODY()

	/** The bone influences and their weights for the binding. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	TArray<FNaniteAssemblyBoneInfluence> BoneInfluences;
	
	/** The transform of the binding. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	FTransform Transform;

	/** Identifies the space to treat `Transform` as being in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Default)
	ENaniteAssemblyNodeTransformSpace TransformSpace = ENaniteAssemblyNodeTransformSpace::Local;
};

UCLASS(Abstract)
class NANITEASSEMBLYEDITORUTILS_API UNaniteAssemblyBuilder : public UObject
{
	GENERATED_BODY()

public:
	UNaniteAssemblyBuilder(const FObjectInitializer& Initializer);


	/** Retrieves the target object of the current assembly build */
	UFUNCTION(BlueprintCallable, Category = Default)
	virtual UObject* GetTargetMeshObject() const PURE_VIRTUAL(UNaniteAssemblyBuilder::GetTargetMeshObject, return nullptr;)

	/** Returns whether or not this object is in the middle of an assembly build */
	UFUNCTION(BlueprintCallable, Category = Default)
	bool IsBuildingAssembly() const	{ return GetTargetMeshObject() != nullptr; }

	/**
	 * Creates a new material slot group on the builder, which allows you to be selective about which assembly
	 * parts' materials can be merged together. Use the return value when adding a part to the assembly.
	 */
	UFUNCTION(BlueprintCallable, Category = "Materials")
	int32 AddMaterialSlotGroup() { return Builder.AddMaterialSlotGroup(); }
	
	/**
	 * Creates a material slot in the specified material slot group with a given material. If the slot name
	 * provided is "None", the resulting material slot will take the name of the material.
	 */
	UFUNCTION(BlueprintCallable, Category = "Materials")
	int32 AddMaterialSlot(UMaterialInterface* Material, int32 MaterialSlotGroup = 0, FName SlotName = NAME_None);

protected:
	struct FAddPartsResult
	{
		int32 PartIndex;
		int32 FirstNodeIndex;
		bool bNewPart;
	};

	void Reset();

	FAddPartsResult FindOrAddPartMesh(FSoftObjectPath MeshObjectPath, const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions);

	FAddPartsResult AddParts(
		FSoftObjectPath MeshObjectPath,
		TArrayView<const FTransform> LocalTransforms,
		const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions
	);

	FAddPartsResult AddParts(
		FSoftObjectPath MeshObjectPath,
		TArrayView<const FNaniteAssemblySkeletalMeshPartBinding> Bindings,
		const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions
	);

	int32 MergeMaterialSlot(
		int32 SourceSlotIndex,
		const FNaniteAssemblyDataBuilder::FMaterialSlot& Slot,
		ENaniteAssemblyPartMaterialMerge MergeOption
	);

	bool ValidateBuildStatus(const TCHAR* Label, bool bExpectedIsBuilding) const;
	template <typename TMesh>
	bool ValidateCandidatePartMesh(const TMesh* Mesh) const;

	static UObject* CreateNewMeshForAssemblyBuild(
		const FNaniteAssemblyCreateNewParameters& Parameters,
		const UClass* Class,
		const UObject* ObjectToDuplicate = nullptr
	);
	template <typename TMesh>
	static TMesh* CreateNewMeshForAssemblyBuild(
		const FNaniteAssemblyCreateNewParameters& Parameters,
		const TMesh* ObjectToDuplicate = nullptr
	)
	{
		return CastChecked<TMesh>(CreateNewMeshForAssemblyBuild(Parameters, TMesh::StaticClass(), ObjectToDuplicate), ECastCheckedType::NullAllowed);
	}

protected:
	FNaniteAssemblyDataBuilder Builder;
	UPROPERTY(Transient)
	TArray<FNaniteAssemblyMaterialMergeOptions> PartMaterialMergeOptions;
};

template <typename TMesh>
bool UNaniteAssemblyBuilder::ValidateCandidatePartMesh(const TMesh* PartMesh) const
{
	if (!ValidateBuildStatus(TEXT("AddAssemblyParts"), true))
	{
		return false;
	}

	if (PartMesh == nullptr)
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[AddAssemblyParts] Part mesh is not valid."));
		return false;
	}

	if (PartMesh == GetTargetMeshObject())
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[AddAssemblyParts] Adding target mesh as a part not supported."));
		return false;
	}

	if (PartMesh->IsNaniteAssembly())
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[AddAssemblyParts] Adding Nanite Assembly mesh as a part not currently supported. Part Mesh: %s"),
			*PartMesh->GetPathName());
		return false;
	}

	return true;
}