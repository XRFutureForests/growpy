// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "NaniteAssemblyBuilder.h"

#include "NaniteAssemblySkeletalMeshBuilder.generated.h"

class USceneComponent;
class USkeletalMesh;
class USkeletalMeshComponent;

UCLASS(BlueprintType)
class NANITEASSEMBLYEDITORUTILS_API UNaniteAssemblySkeletalMeshBuilder : public UNaniteAssemblyBuilder
{
	GENERATED_BODY()

public:	
	UNaniteAssemblySkeletalMeshBuilder(const FObjectInitializer& Initializer);

	virtual UObject* GetTargetMeshObject() const override { return TargetMesh; }
	
	/**
	 * Creates a Nanite Assembly Skeletal Mesh builder to generate a new Skeletal Mesh asset. Requires a base mesh with a valid
	 * skeleton to be duplicated for the base mesh.
	 */
	UFUNCTION(BlueprintCallable, Category = "Skeletal Mesh")
	static UNaniteAssemblySkeletalMeshBuilder* BeginNewSkeletalMeshAssemblyBuild(
		const FNaniteAssemblyCreateNewParameters& Parameters,
		const USkeletalMesh* BaseMesh
	);
	
	/**
	 * Creates a Nanite Assembly Skeletal Mesh builder to add assembly parts to the specified Skeletal Mesh, or overwrite its
	 * assembly parts if it is an existing Nanite Assembly mesh.
	 */
	UFUNCTION(BlueprintCallable, Category = "Skeletal Mesh")
	static UNaniteAssemblySkeletalMeshBuilder* BeginEditSkeletalMeshAssemblyBuild(USkeletalMesh* BaseMesh);
	
	bool BeginAssemblyBuild(USkeletalMesh* InTargetMesh);

	/** Finalizes the assembly build and returns the finished assembly mesh. */
	UFUNCTION(BlueprintCallable, Category = "Skeletal Mesh", meta = ( ReturnDisplayName = "Success" ))
	bool FinishAssemblyBuild(USkeletalMesh*& OutSkeletalMesh);

	bool AddAssemblyParts(
		const USkeletalMesh* PartMesh,
		TArrayView<const FNaniteAssemblySkeletalMeshPartBinding> Bindings,
		const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions = FNaniteAssemblyMaterialMergeOptions()
	);

	/** Adds instances of the specified mesh to the assembly with the specified bindings */
	UFUNCTION(BlueprintCallable, Category = "Assembly Parts", meta = ( ReturnDisplayName = "Success", AutoCreateRefTerm = "MaterialMergeOptions" ))
	bool AddAssemblyParts(
		const USkeletalMesh* PartMesh,
		const TArray<FNaniteAssemblySkeletalMeshPartBinding>& Bindings,
		const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions = FNaniteAssemblyMaterialMergeOptions()
	)
	{
		return AddAssemblyParts(PartMesh, TArrayView<const FNaniteAssemblySkeletalMeshPartBinding>(Bindings), MaterialMergeOptions);
	}

	/** Adds an instance of the specified mesh to the assembly with the specified binding */
	UFUNCTION(BlueprintCallable, Category = "Assembly Parts", meta = ( ReturnDisplayName = "Success", AutoCreateRefTerm = "MaterialMergeOptions" ))
	bool AddAssemblyPart(
		const USkeletalMesh* PartMesh,
		const FNaniteAssemblySkeletalMeshPartBinding& Binding,
		const FNaniteAssemblyMaterialMergeOptions& MaterialMergeOptions = FNaniteAssemblyMaterialMergeOptions()
	)
	{
		return AddAssemblyParts(PartMesh, MakeConstArrayView(&Binding, 1), MaterialMergeOptions);
	}

	/**
	 * Attempts to create a new skeletal mesh part binding from the specified bone's name. For multiple bone influence, use
	 * `AddBoneInfluenceByName` for each additional bone.
	 */
	UFUNCTION(BlueprintCallable, Category = Default, meta = ( ReturnDisplayName = "Success", AutoCreateRefTerm = "Transform" ))
	bool CreateBindingByBoneName(
		FNaniteAssemblySkeletalMeshPartBinding& OutBinding,
		FName BoneName,
		float Weight = 1.0f,
		const FTransform& Transform = FTransform(),
		ENaniteAssemblyNodeTransformSpace TransformSpace = ENaniteAssemblyNodeTransformSpace::BoneRelative
	);

	/**
	* Attempts to create a new skeletal mesh part binding from a socket's name.
	* WARNING: Don't add additional bone influences to the binding when creating from a socket, or the attachment won't look right.
	*/
	UFUNCTION(BlueprintCallable, Category = Default, meta = ( ReturnDisplayName = "Success", AutoCreateRefTerm = "Transform" ))
	bool CreateBindingBySocketName(
		FNaniteAssemblySkeletalMeshPartBinding& OutBinding,
		FName SocketName,
		const FTransform& Transform = FTransform(),
		ENaniteAssemblyNodeTransformSpace TransformSpace = ENaniteAssemblyNodeTransformSpace::BoneRelative);

	/** Attempts to add a bone influence to a skeletal mesh binding based on the bone's name. */
	UFUNCTION(BlueprintCallable, Category = Default, meta = ( ReturnDisplayName = "Success" ))
	bool AddBoneInfluenceByName(
		UPARAM(ref) FNaniteAssemblySkeletalMeshPartBinding& Binding,
		FName BoneName,
		float Weight = 1.0f
	);

private:
	bool ValidateBindings(TArrayView<const FNaniteAssemblySkeletalMeshPartBinding> Bindings) const;

private:
	UPROPERTY(Transient)
	TObjectPtr<USkeletalMesh> TargetMesh;
};