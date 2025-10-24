// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Engine/NaniteAssemblyData.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"

/** Helper class for building a Nanite assembly */
class FNaniteAssemblyDataBuilder
{
public:
	struct FMaterialSlot
	{
		int32 MaterialSlotGroup = 0;
		FName Name = NAME_None;
		TObjectPtr<UMaterialInterface> Material;

		FMaterialSlot() = default;
		explicit FMaterialSlot(const TObjectPtr<UMaterialInterface>& InMaterial, int32 InMaterialSlotGroup = 0) :
			MaterialSlotGroup(InMaterialSlotGroup), Name(InMaterial.GetFName()), Material(InMaterial)
		{
		}

		FMaterialSlot(const TObjectPtr<UMaterialInterface>& InMaterial, FName SlotName, int32 InMaterialSlotGroup = 0) :
			MaterialSlotGroup(InMaterialSlotGroup), Name(SlotName), Material(InMaterial)
		{
		}
	};

	friend FArchive& operator<<(FArchive& Ar, FNaniteAssemblyDataBuilder& Builder);

	FNaniteAssemblyDataBuilder() { Reset(); }
	ENGINE_API void Reset();
	
	const FNaniteAssemblyData& GetData() const { return AssemblyData; }

	ENGINE_API int32 AddPart(const FSoftObjectPath& MeshPath, int32 MaterialSlotGroup = 0);
	ENGINE_API int32 FindPart(const FSoftObjectPath& MeshPath);
	ENGINE_API int32 FindOrAddPart(const FSoftObjectPath& MeshPath, int32 MaterialSlotGroup, bool& bOutNewPart);
	int32 FindOrAddPart(const FSoftObjectPath& MeshPath, int32 MaterialSlotGroup = 0)
	{
		bool bNewPart;
		return FindOrAddPart(MeshPath, MaterialSlotGroup, bNewPart);
	}
	
	ENGINE_API int32 AddNode(
		int32 PartIndex,
		const FTransform3f& Transform = FTransform3f::Identity,
		ENaniteAssemblyNodeTransformSpace TransformSpace = ENaniteAssemblyNodeTransformSpace::Local,
		TArrayView<const FNaniteAssemblyBoneInfluence> AttachWeights = {}
	);

	int32 AddMaterialSlotGroup() { return MaterialSlotGroups.AddDefaulted(); }
	int32 NumMaterialSlotGroups() const { return MaterialSlotGroups.Num(); }
	int32 IsValidMaterialSlotGroup(int32 MaterialSlotGroup) const { return MaterialSlotGroups.IsValidIndex(MaterialSlotGroup); }
	const TArray<FMaterialSlot>& GetMaterialSlots(int32 MaterialSlotGroup = 0) const { return MaterialSlotGroups[MaterialSlotGroup]; };

	int32 AddMaterialSlot(const FMaterialSlot& NewSlot)
	{
		return MaterialSlotGroups[NewSlot.MaterialSlotGroup].Add(NewSlot);
	}
	int32 AddMaterialSlot(int32 MaterialSlotGroup, TObjectPtr<UMaterialInterface> Material = {})
	{
		return AddMaterialSlot(FMaterialSlot(Material, MaterialSlotGroup));
	}
	int32 AddMaterialSlot(TObjectPtr<UMaterialInterface> Material = {}) { return AddMaterialSlot(0, Material); }
	
	ENGINE_API void SetNumMaterialSlots(int32 MaterialSlotGroup, int32 NumMaterialSlots);
	void SetNumMaterialSlots(int32 NumMaterialSlots) { SetNumMaterialSlots(0, NumMaterialSlots); }

	void SetMaterialSlot(int32 MaterialSlotIndex, const FMaterialSlot& Slot)
	{
		MaterialSlotGroups[Slot.MaterialSlotGroup][MaterialSlotIndex] = Slot;
	}
	void SetMaterial(int32 MaterialSlotGroup, int32 MaterialSlotIndex, TObjectPtr<UMaterialInterface> Material)
	{
		SetMaterialSlot(MaterialSlotIndex, FMaterialSlot(Material, MaterialSlotGroup));
	}
	void SetMaterial(int32 MaterialSlotIndex, TObjectPtr<UMaterialInterface> Material) { SetMaterial(0, MaterialSlotIndex, Material); }

	ENGINE_API void RemapPartMaterial(int32 PartIndex, int32 LocalMaterialIndex, int32 MaterialIndex);
	ENGINE_API void RemapBaseMeshMaterial(int32 LocalMaterialIndex, int32 MaterialIndex);

	ENGINE_API bool ApplyToStaticMesh(
		UStaticMesh& TargetMesh,
		const UStaticMesh::FCommitMeshDescriptionParams& CommitParams = UStaticMesh::FCommitMeshDescriptionParams()
	);
	
	ENGINE_API bool ApplyToSkeletalMesh(
		USkeletalMesh& TargetMesh,
		const USkeletalMesh::FCommitMeshDescriptionParams& CommitParams = USkeletalMesh::FCommitMeshDescriptionParams()
	);

private:
	int32 RemapBaseMaterialIndex(int32 MaterialIndex, int32 NumMaterialSlots);
	template <typename TMaterial>
	TArray<FMaterialSlot> FinalizeMaterialSlots(
		const TArray<TMaterial>& PreviousMaterials,
		FNaniteAssemblyData& InOutData,
		FMeshDescription& InOutMeshDescription
	);

private:
	using FMaterialSlotGroup = TArray<FMaterialSlot>;

	FNaniteAssemblyData AssemblyData;
	TArray<FMaterialSlotGroup> MaterialSlotGroups;
	TArray<int32> PartMaterialSlotGroups;
	TArray<int32> BaseMeshMaterialRemap;
};

inline FArchive& operator<<(FArchive& Ar, FNaniteAssemblyDataBuilder::FMaterialSlot& Slot)
{
	Ar << Slot.MaterialSlotGroup;
	Ar << Slot.Name;
	Ar << Slot.Material;

	return Ar;
}

inline FArchive& operator<<(FArchive& Ar, FNaniteAssemblyDataBuilder& Builder)
{
	Ar << Builder.AssemblyData;
	Ar << Builder.MaterialSlotGroups;
	Ar << Builder.PartMaterialSlotGroups;
	Ar << Builder.BaseMeshMaterialRemap;

	return Ar;
}

#endif // WITH_EDITOR
