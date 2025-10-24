// Copyright Epic Games, Inc. All Rights Reserved.

#include "NaniteAssemblyBuilder.h"
#include "AssetToolsModule.h"
#include "PackageTools.h"

UNaniteAssemblyBuilder::UNaniteAssemblyBuilder(const FObjectInitializer& Initializer)
	: Super(Initializer)
{
}

int32 UNaniteAssemblyBuilder::AddMaterialSlot(
	UMaterialInterface* Material,
	int32 MaterialSlotGroup,
	FName SlotName
)
{
	if (!Builder.IsValidMaterialSlotGroup(MaterialSlotGroup))
	{
		return INDEX_NONE;
	}

	const FNaniteAssemblyDataBuilder::FMaterialSlot NewSlot(Material, SlotName, MaterialSlotGroup);
	return Builder.AddMaterialSlot(NewSlot);
}

void UNaniteAssemblyBuilder::Reset()
{
	Builder.Reset();
	PartMaterialMergeOptions.Reset();
}

UNaniteAssemblyBuilder::FAddPartsResult UNaniteAssemblyBuilder::FindOrAddPartMesh(
	FSoftObjectPath MeshObjectPath,
	const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions)
{
	const auto& Parts = Builder.GetData().Parts;
	check(Parts.Num() == PartMaterialMergeOptions.Num());

	int32 PartIndex = INDEX_NONE;
	for (int32 i = 0; i < Parts.Num(); ++i)
	{
		if (Parts[i].MeshObjectPath == MeshObjectPath &&
			PartMaterialMergeOptions[i] == MaterialMergeOptions)
		{
			PartIndex = i;
			break;
		}
	}

	const bool bNewPart = PartIndex == INDEX_NONE;
	if (bNewPart)
	{
		PartIndex = Builder.AddPart(MeshObjectPath, MaterialMergeOptions.MaterialSlotGroup);
		PartMaterialMergeOptions.Emplace(MaterialMergeOptions);
	}

	return { PartIndex, INDEX_NONE, bNewPart };
}

UNaniteAssemblyBuilder::FAddPartsResult UNaniteAssemblyBuilder::AddParts(
	FSoftObjectPath MeshObjectPath,
	TArrayView<const FTransform> LocalTransforms,
	const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions
)
{
	check(LocalTransforms.Num() > 0);
	auto [PartIndex, FirstNodeIndex, bNewPart] = FindOrAddPartMesh(MeshObjectPath, MaterialMergeOptions);
	FirstNodeIndex = Builder.GetData().Nodes.Num();
	for (const FTransform& Transform : LocalTransforms)
	{
		Builder.AddNode(PartIndex, FTransform3f(Transform));
	}
	return { PartIndex, FirstNodeIndex, bNewPart };
}

UNaniteAssemblyBuilder::FAddPartsResult UNaniteAssemblyBuilder::AddParts(
	FSoftObjectPath MeshObjectPath,
	TArrayView<const FNaniteAssemblySkeletalMeshPartBinding> Bindings,
	const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions
)
{
	check(Bindings.Num() > 0);
	auto [PartIndex, FirstNodeIndex, bNewPart] = FindOrAddPartMesh(MeshObjectPath, MaterialMergeOptions);
	FirstNodeIndex = Builder.GetData().Nodes.Num();
	for (const auto& Binding : Bindings)
	{
		Builder.AddNode(PartIndex, FTransform3f(Binding.Transform), Binding.TransformSpace, Binding.BoneInfluences);
	}
	return { PartIndex, FirstNodeIndex, bNewPart };
}

int32 UNaniteAssemblyBuilder::MergeMaterialSlot(
	int32 SourceSlotIndex,
	const FNaniteAssemblyDataBuilder::FMaterialSlot& Slot,
	ENaniteAssemblyPartMaterialMerge MergeOption
)
{
	const TArray<FNaniteAssemblyDataBuilder::FMaterialSlot>& DestSlots = Builder.GetMaterialSlots(Slot.MaterialSlotGroup);
	int32 DestSlotIndex = INDEX_NONE;
	switch (MergeOption)
	{
	case ENaniteAssemblyPartMaterialMerge::MergeMaterialIndices:
		DestSlotIndex = SourceSlotIndex;
		break;
	case ENaniteAssemblyPartMaterialMerge::MergeIdenticalSlotNames:
		DestSlotIndex = DestSlots.IndexOfByPredicate([A=Slot.Name] (const auto& B) { return A == B.Name; });
		break;
	case ENaniteAssemblyPartMaterialMerge::MergeIdenticalMaterials:
		DestSlotIndex = DestSlots.IndexOfByPredicate([A=Slot.Material] (const auto& B) { return A == B.Material; });
		break;
	default:
		checkf(false, TEXT("Unhandled merge type!"));
		break;
	}

	if (DestSlotIndex == INDEX_NONE)
	{
		DestSlotIndex = Builder.AddMaterialSlot(Slot);
	}
	else if (DestSlotIndex >= DestSlots.Num())
	{
		Builder.SetNumMaterialSlots(Slot.MaterialSlotGroup, DestSlotIndex + 1);
		Builder.SetMaterialSlot(DestSlotIndex, Slot);
	}

	return DestSlotIndex;
}

bool UNaniteAssemblyBuilder::ValidateBuildStatus(const TCHAR* Label, bool bExpectedIsBuilding) const
{
	const bool bIsBuilding = IsBuildingAssembly();
	if (bIsBuilding != bExpectedIsBuilding)
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[%s] This builder is %scurrently building an assembly."),
			Label, bIsBuilding ? TEXT("") : TEXT("not "));
		return false;
	}

	return true;
}

UObject* UNaniteAssemblyBuilder::CreateNewMeshForAssemblyBuild(
	const FNaniteAssemblyCreateNewParameters& Parameters,
	const UClass* Class,
	const UObject* ObjectToDuplicate
)
{
	if (ObjectToDuplicate && !ObjectToDuplicate->IsA(Class))
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[CreateNewMeshForAssemblyBuild] Cannot duplicate %s as a new %s asset. Incompatible types."),
			*ObjectToDuplicate->GetName(),
			*Class->GetName());
		return nullptr;
	}

	FString DesiredPackageName = Parameters.TargetDirectory.Path / Parameters.AssetName;
	FString PackageName;
	FString AssetName;
	if (Parameters.bOverwriteExisting)
	{
		PackageName = UPackageTools::SanitizePackageName(DesiredPackageName);
		AssetName = FPaths::GetBaseFilename(PackageName);
	}
	else
	{
		static const FString Suffix = TEXT("");
		const FAssetToolsModule& AssetToolsModule = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
		AssetToolsModule.Get().CreateUniqueAssetName(
			DesiredPackageName,
			Suffix,
			PackageName,
			AssetName
		);
	}
	
	UPackage* Package = CreatePackage(*PackageName);

	if (!Package)
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[CreateNewMeshForAssemblyBuild] Failed to create new package for Nanite Assembly asset: %s"),
			*PackageName);
		return nullptr;
	}

	Package->FullyLoad();

	// Create the new mesh
	UObject* NewMesh = nullptr;
	const FName NewAssetName { *AssetName };
	if (ObjectToDuplicate)
	{
		NewMesh = DuplicateObject(ObjectToDuplicate, Package, NewAssetName);
		if (NewMesh)
		{
			NewMesh->SetFlags(EObjectFlags::RF_Public | EObjectFlags::RF_Standalone);
		}
	}
	else
	{
		NewMesh = NewObject<UObject>(
			Package,
			Class,
			NewAssetName,
			EObjectFlags::RF_Public | EObjectFlags::RF_Standalone
		);
	}

	if (NewMesh == nullptr)
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[CreateNewMeshForAssemblyBuild] Failed to create new %s for Nanite Assembly asset: %s.%s"),
			*Class->GetName(),
			*PackageName,
			*AssetName);
		return nullptr;
	}

	return NewMesh;
}

