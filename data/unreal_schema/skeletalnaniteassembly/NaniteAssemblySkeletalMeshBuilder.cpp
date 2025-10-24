// Copyright Epic Games, Inc. All Rights Reserved.

#include "NaniteAssemblySkeletalMeshBuilder.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/Skeleton.h"

static bool ValidateValidMeshAndSkeleton(const TCHAR* Label, const USkeletalMesh* Mesh)
{
	if (Mesh == nullptr)
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[%s] Target Skeletal Mesh is not valid."),
			Label);
		return false;
	}
	else if (Mesh->GetSkeleton() == nullptr)
	{
		UE_LOG(LogNaniteAssemblyBuilder, Error,
			TEXT("[%s] Target Skeletal Mesh has no valid skeleton: %s"),
			Label,
			*Mesh->GetName());
		return false;
	}

	return true;
}

UNaniteAssemblySkeletalMeshBuilder::UNaniteAssemblySkeletalMeshBuilder(const FObjectInitializer& Initializer)
	: Super(Initializer)
{
}

UNaniteAssemblySkeletalMeshBuilder* UNaniteAssemblySkeletalMeshBuilder::BeginNewSkeletalMeshAssemblyBuild(
	const FNaniteAssemblyCreateNewParameters& Parameters,
	const USkeletalMesh* BaseMesh
)
{
	if (!ValidateValidMeshAndSkeleton(TEXT("BeginNewSkeletalMeshAssemblyBuild"), BaseMesh))
	{
		return nullptr;
	}
	
	if (USkeletalMesh* TargetMesh = CreateNewMeshForAssemblyBuild<USkeletalMesh>(Parameters, BaseMesh))
	{
		return BeginEditSkeletalMeshAssemblyBuild(TargetMesh);
	}
	
	return nullptr;
}

UNaniteAssemblySkeletalMeshBuilder* UNaniteAssemblySkeletalMeshBuilder::BeginEditSkeletalMeshAssemblyBuild(USkeletalMesh* TargetMesh)
{
	if (!ValidateValidMeshAndSkeleton(TEXT("BeginEditSkeletalMeshAssemblyBuild"), TargetMesh))
	{
		return nullptr;
	}
	
	UNaniteAssemblySkeletalMeshBuilder* Builder = NewObject<UNaniteAssemblySkeletalMeshBuilder>();
	if (!Builder->BeginAssemblyBuild(TargetMesh))
	{
		return nullptr;
	}

	return Builder;
}

bool UNaniteAssemblySkeletalMeshBuilder::BeginAssemblyBuild(USkeletalMesh* InTargetMesh)
{
	if (!ValidateBuildStatus(TEXT("BeginSkeletalMeshAssemblyBuild"), false))
	{
		return false;
	}
	if (!ValidateValidMeshAndSkeleton(TEXT("BeginSkeletalMeshAssemblyBuild"), InTargetMesh))
	{
		return false;
	}

	TargetMesh = InTargetMesh;

	// Add any materials on the target mesh to the default slot group
	for (const auto& Material : TargetMesh->GetMaterials())
	{
		AddMaterialSlot(Material.MaterialInterface.Get(), 0, Material.MaterialSlotName);
	}

	return true;
}

bool UNaniteAssemblySkeletalMeshBuilder::FinishAssemblyBuild(USkeletalMesh*& OutSkeletalMesh)
{
	OutSkeletalMesh = TargetMesh;
	if (!ValidateBuildStatus(TEXT("FinishSkeletalMeshAssemblyBuild"), true))
	{
		return false;
	}

	USkeletalMesh::FCommitMeshDescriptionParams Params;
	Params.bMarkPackageDirty = true;
	if (!Builder.ApplyToSkeletalMesh(*TargetMesh, Params))
	{
		UE_LOG(LogNaniteAssemblyBuilder, Display,
			TEXT("[FinishSkeletalMeshAssemblyBuild] Assembly build failed. No assembly parts were added."),
			*TargetMesh->GetPathName());
		return false;
	}

	TargetMesh->NaniteSettings.bEnabled = true;
	TargetMesh->PostEditChange();
	
	TargetMesh = nullptr;
	Reset();

	return true;
}

bool UNaniteAssemblySkeletalMeshBuilder::AddAssemblyParts(
	const USkeletalMesh* PartMesh,
	TArrayView<const FNaniteAssemblySkeletalMeshPartBinding> Bindings,
	const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions
)
{
	if (!ValidateCandidatePartMesh(PartMesh))
	{
		return false;
	}

	if (!ValidateBindings(Bindings))
	{
		return false;
	}

	auto [PartIndex, FirstNodeIndex, bNewPart] = AddParts(FSoftObjectPath(PartMesh), Bindings, MaterialMergeOptions);

	if (bNewPart)
	{
		// We need to merge and remap this part mesh's materials
		int32 SourceMaterialIndex = 0;
		for (const auto& Material : PartMesh->GetMaterials())
		{
			TObjectPtr<UMaterialInterface> MaterialInterface = Material.MaterialInterface;
			if (MaterialMergeOptions.MaterialOverrides.IsValidIndex(SourceMaterialIndex))
			{
				MaterialInterface = MaterialMergeOptions.MaterialOverrides[SourceMaterialIndex];
			}
			const FNaniteAssemblyDataBuilder::FMaterialSlot NewSlot(
				MaterialInterface,
				Material.MaterialSlotName,
				MaterialMergeOptions.MaterialSlotGroup
			);
			const int32 MaterialIndex = MergeMaterialSlot(SourceMaterialIndex, NewSlot, MaterialMergeOptions.MergeBehavior);
			Builder.RemapPartMaterial(PartIndex, SourceMaterialIndex, MaterialIndex);

			++SourceMaterialIndex;
		}
	}

	return true;
}

bool UNaniteAssemblySkeletalMeshBuilder::CreateBindingByBoneName(
	FNaniteAssemblySkeletalMeshPartBinding& OutBinding,
	FName BoneName,
	float Weight,
	const FTransform& Transform,
	ENaniteAssemblyNodeTransformSpace TransformSpace
)
{
	OutBinding.BoneInfluences.Reset(1);
	OutBinding.Transform = Transform;
	OutBinding.TransformSpace = TransformSpace;

	return AddBoneInfluenceByName(OutBinding, BoneName, Weight);
}

bool UNaniteAssemblySkeletalMeshBuilder::CreateBindingBySocketName(
	FNaniteAssemblySkeletalMeshPartBinding& OutBinding,
	FName SocketName,
	const FTransform& Transform,
	ENaniteAssemblyNodeTransformSpace TransformSpace
)
{
	if (!ValidateBuildStatus(TEXT("CreateBindingBySocketName"), true))
	{
		return false;
	}

	OutBinding.BoneInfluences.Reset(1);

	FTransform SocketTransform;
	int32 BoneIndex, SocketIndex;
	if (TargetMesh->FindSocketInfo(SocketName, SocketTransform, BoneIndex, SocketIndex))
	{
		OutBinding.BoneInfluences.Add({ BoneIndex, 1.0f });
		OutBinding.Transform = Transform;
		OutBinding.TransformSpace = TransformSpace;

		if (TransformSpace == ENaniteAssemblyNodeTransformSpace::BoneRelative)
		{
			OutBinding.Transform *= SocketTransform;
		}
		return true;
	}

	return false;
}

bool UNaniteAssemblySkeletalMeshBuilder::AddBoneInfluenceByName(
	FNaniteAssemblySkeletalMeshPartBinding& Binding,
	FName BoneName,
	float Weight
)
{
	if (!ValidateBuildStatus(TEXT("AddBoneInfluenceByName"), true))
	{
		return false;
	}

	check(TargetMesh->GetSkeleton() != nullptr);

	const FReferenceSkeleton& RefSkel = TargetMesh->GetSkeleton()->GetReferenceSkeleton();

	int32 BoneIndex = RefSkel.FindBoneIndex(BoneName);
	if (BoneIndex == INDEX_NONE)
	{
		return false;
	}

	Binding.BoneInfluences.Add( { BoneIndex, Weight });
	return true;
}

bool UNaniteAssemblySkeletalMeshBuilder::ValidateBindings(TArrayView<const FNaniteAssemblySkeletalMeshPartBinding> Bindings) const
{
	check(TargetMesh != nullptr);
	check(TargetMesh->GetSkeleton() != nullptr);

	const FReferenceSkeleton& RefSkel = TargetMesh->GetSkeleton()->GetReferenceSkeleton();

	for (const auto& Binding : Bindings)
	{
		if (Binding.BoneInfluences.Num() == 0)
		{
			UE_LOG(LogNaniteAssemblyBuilder, Error,
				TEXT("[AddAssemblyParts] An invalid binding was encountered with 0 bone influences."));
			return false;
		}
		for (const auto& BoneInfluence : Binding.BoneInfluences)
		{
			if(!RefSkel.IsValidIndex(BoneInfluence.BoneIndex))
			{
				UE_LOG(LogNaniteAssemblyBuilder, Error,
					TEXT("[AddAssemblyParts] Binding with invalid bone index %d encountered."),
					BoneInfluence.BoneIndex);
				return false;
			}
		}
	}

	return true;
}