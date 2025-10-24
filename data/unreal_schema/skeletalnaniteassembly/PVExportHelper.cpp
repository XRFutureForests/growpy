// Copyright Epic Games, Inc. All Rights Reserved.

#include "Helpers/PVExportHelper.h"

#include "DynamicMeshEditor.h"
#if WITH_EDITOR
#include "DynamicWindImportData.h"
#endif
#include "DynamicWindSkeletalData.h"
#include "ProceduralVegetationLink.h"
#include "ProceduralVegetationModule.h"
#include "MeshDescriptionToDynamicMesh.h"
#include "PlanarCut.h"
#include "RenderUtils.h"
#include "StaticMeshAttributes.h"
#include "Animation/Skeleton.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "ConversionUtils/SceneComponentToDynamicMesh.h"
#include "DynamicMesh/DynamicBoneAttribute.h"
#include "DynamicMesh/DynamicVertexSkinWeightsAttribute.h"

#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Facades/PVBranchFacade.h"
#include "Facades/PVPointFacade.h"
#include "GeometryCollection/GeometryCollection.h"
#include "GeometryScript/GeometryScriptTypes.h"
#include "GeometryScript/MeshAssetFunctions.h"
#include "GeometryScript/MeshBoneWeightFunctions.h"
#include "Helpers/PVUtilities.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "ProceduralVegetation.h"
#include "SkinnedAssetCompiler.h"
#include "StaticMeshCompiler.h"
#include "GeometryCollection/Facades/CollectionConstraintOverrideFacade.h"
#include "AssetRegistry/AssetData.h"

namespace PV::Export::Internal
{
	TObjectPtr<UDynamicMesh> CollectionToDynamicMesh(const FManagedArrayCollection& Collection)
	{
		TRACE_CPUPROFILER_EVENT_SCOPE(PV::Export::CollectionToDynamicMesh);
		
		TObjectPtr<UDynamicMesh> NewMesh = NewObject<UDynamicMesh>();

		if (Collection.NumElements(FGeometryCollection::TransformGroup) > 0)
		{
			if (const TUniquePtr<FGeometryCollection> GeomCollection = TUniquePtr<FGeometryCollection>(Collection.NewCopy<FGeometryCollection>()))
			{
				const TManagedArray<FTransform3f>& BoneTransforms = Collection.GetAttribute<FTransform3f>(
					"Transform", FGeometryCollection::TransformGroup);

				TArray<int32> TransformIndices;
				TransformIndices.AddUninitialized(BoneTransforms.Num());

				int32 Idx = 0;
				for (int32& TransformIdx : TransformIndices)
				{
					TransformIdx = Idx++;
				}

				FMeshDescription MeshDescription;
				FStaticMeshAttributes Attributes(MeshDescription);
				Attributes.Register();

				FTransform TransformOut;

				constexpr bool bCenterPivot = false;
				ConvertToMeshDescription(MeshDescription, TransformOut, bCenterPivot, *GeomCollection, BoneTransforms, TransformIndices);

				NewMesh->Reset();

				UE::Geometry::FDynamicMesh3& DynMesh = NewMesh->GetMeshRef();
				{
					FMeshDescriptionToDynamicMesh ConverterToDynamicMesh;
					ConverterToDynamicMesh.Convert(&MeshDescription, DynMesh);
				}
			}
		}

		return NewMesh;
	}

	FGeometryScriptCopyMeshToAssetOptions GetCopyMeshToAssetOptions(TArray<TObjectPtr<UMaterialInterface>> InMaterials)
	{
		FGeometryScriptCopyMeshToAssetOptions Options;
		Options.bEnableRecomputeTangents = true;

		Options.bReplaceMaterials = true;
		Options.NewMaterials = InMaterials;

		return Options;
	}

#if WITH_EDITORONLY_DATA
	FGeometryScriptCopyMeshToAssetOptions GetCopyMeshToAssetOptions(TArray<TObjectPtr<UMaterialInterface>> InMaterials, const FMeshNaniteSettings& InNaniteSettings, const ENaniteShapePreservation InShapePreservation)
	{
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(InMaterials);
		Options.NewNaniteSettings = InNaniteSettings;
		Options.NewNaniteSettings.bEnabled = true;
		Options.NewNaniteSettings.ShapePreservation = InShapePreservation;
		Options.bApplyNaniteSettings = true;

		return Options;
	}
#endif

	FString GetFoliageName(const Facades::FFoliageFacade& FoliageFacade, int32 Id)
	{
		Facades::FFoliageEntryData Data = FoliageFacade.GetFoliageEntry(Id);
		return FoliageFacade.GetFoliageName(Data.NameId);
	}

	TArray<TObjectPtr<UMaterialInterface>> GetMaterialsFromCollection(const FManagedArrayCollection& Collection)
	{
		TArray<TObjectPtr<UMaterialInterface>> Materials;
		if (Collection.HasAttribute("MaterialPath", FGeometryCollection::MaterialGroup))
		{
			const TManagedArray<FString>& MaterialPaths = Collection.GetAttribute<FString>("MaterialPath", FGeometryCollection::MaterialGroup);
			for (const FString& Path : MaterialPaths)
			{
				Materials.Add(LoadObject<UMaterialInterface>(nullptr, *Path));
			}
		}
		return Materials;
	}

	static bool SkeletalMeshToDynamicMesh(const USkeletalMesh* SkeletalMesh, const int32 LodIndex, FDynamicMesh3& ToDynamicMesh)
	{
#if WITH_EDITOR
		if (SkeletalMesh->HasMeshDescription(LodIndex))
		{
			const FMeshDescription* SourceMesh = SkeletalMesh->GetMeshDescription(LodIndex);
			if (!SourceMesh)
			{
				return false;
			}

			FMeshDescriptionToDynamicMesh Converter;
			Converter.Convert(SourceMesh, ToDynamicMesh);
			return true;
		}
#else
		UE_LOG(LogProceduralVegetation, Warning, TEXT("SkeletalMeshToDynamicMesh is only supported in editor."));
#endif
		return false;
	}

	void CombineMeshInstancesToDynamicMesh(
		const FManagedArrayCollection& Collection,
		UDynamicMesh* DynamicMesh,
		TArray<TObjectPtr<UMaterialInterface>>& Materials,
		const FMeshInstanceCombined& OnMeshInstanceCombined
	)
	{
		Facades::FFoliageFacade FoliageFacade(Collection);
		int32 NumInstances = FoliageFacade.NumFoliageEntries();
		
		if(NumInstances > 0)
		{
			TMap<FString, FDynamicMesh3> FoliageDynamicMeshes;
			TMap<FString, TObjectPtr<UStaticMesh>> FoliageStaticMeshes;
			TMap<FString, TObjectPtr<USkeletalMesh>> FoliageSkeletalMeshes;
			
			for(int32 FoliageNameIndex = 0; FoliageNameIndex < FoliageFacade.NumFoliageNames(); ++FoliageNameIndex)
			{
				FString FoliageName = FoliageFacade.GetFoliageName(FoliageNameIndex);
				const TObjectPtr<UStaticMesh> StaticMesh = LoadObject<UStaticMesh>(nullptr, *FoliageName);
				const TObjectPtr<USkeletalMesh> SkeletalMesh = LoadObject<USkeletalMesh>(nullptr, *FoliageName);

				FDynamicMesh3 FoliageDynamicMesh;
				FText OutErrorMessage;

				if(StaticMesh)
				{
					FoliageStaticMeshes.FindOrAdd(FoliageName) = StaticMesh;
					
					for (auto Material : StaticMesh->GetStaticMaterials())
					{
						Materials.AddUnique(Material.MaterialInterface);
					}

					UE::Conversion::FStaticMeshConversionOptions Options;
					if(StaticMeshToDynamicMesh(StaticMesh, FoliageDynamicMesh, OutErrorMessage, Options))
					{
						FoliageDynamicMeshes.Add(FoliageName, MoveTemp(FoliageDynamicMesh));
					}
				}
				else if (SkeletalMesh)
				{
					FoliageSkeletalMeshes.FindOrAdd(FoliageName) = SkeletalMesh;
					
					for (auto Material : SkeletalMesh->GetMaterials())
					{
						Materials.AddUnique(Material.MaterialInterface);
					}

					if(SkeletalMeshToDynamicMesh(SkeletalMesh, 0, FoliageDynamicMesh))
					{
						FoliageDynamicMesh.Attributes()->RemoveAttribute("BoneIndex");
						FoliageDynamicMesh.Attributes()->RemoveAttribute("BoneParentIndex");
						FoliageDynamicMeshes.Add(FoliageName, MoveTemp(FoliageDynamicMesh));
					}
				}
			}

			for(int32 Id = 0; Id < NumInstances; Id++)
			{
				FString FoliageName = GetFoliageName(FoliageFacade, Id);

				if(FoliageDynamicMeshes.Find(FoliageName))
				{
					FDynamicMesh3& FoliageDynamicMesh = FoliageDynamicMeshes[FoliageName];

					const TObjectPtr<UStaticMesh> StaticMesh = FoliageStaticMeshes.Contains(FoliageName) ? FoliageStaticMeshes[FoliageName] : nullptr;
					const TObjectPtr<USkeletalMesh> SkeletalMesh = FoliageSkeletalMeshes.Contains(FoliageName) ? FoliageSkeletalMeshes[FoliageName] : nullptr;

					if (SkeletalMesh)
					{
						int32 FoliageParentBoneID = FoliageFacade.GetParentBoneID(Id);

						//Reparent root bone according to the instanced transform
						UE::Geometry::FDynamicMeshAttributeSet* MeshAttributes = FoliageDynamicMesh.Attributes();
						UE::Geometry::FDynamicMeshBoneParentIndexAttribute* BoneParentIndices = MeshAttributes->GetBoneParentIndices();
						BoneParentIndices->SetValue(0,FoliageParentBoneID);
					}
				
					FTransform Transform = FoliageFacade.GetFoliageTransform(Id);
					UE::Geometry::FTransformSRT3d GeoTransform(Transform);

					DynamicMesh->EditMesh([&](FDynamicMesh3& Mesh)
					{
						int32 VertexStart = Mesh.VertexCount();
						UE::Geometry::FDynamicMeshEditor Editor = UE::Geometry::FDynamicMeshEditor(&Mesh);

						UE::Geometry::FMeshIndexMappings IndexMap;
						Editor.AppendMesh(
							&FoliageDynamicMesh,
							IndexMap,
							[&](int, const FVector3d& Position)
							{
								return GeoTransform.TransformPosition(Position);
							},
							[&](int, const FVector3d& Normal)
							{
								return GeoTransform.TransformVectorNoScale(Normal);
							}
						);

						UE::Geometry::FIndexMapi& TriangleMap = IndexMap.GetTriangleMap();
							
						//Remap Material IDs
						if (Mesh.Attributes()->HasMaterialID())
						{
							UE::Geometry::FDynamicMeshMaterialAttribute* MaterialIDs = Mesh.Attributes()->GetMaterialID();

							for (const auto& [OldTid, NewTid] : TriangleMap.GetForwardMap())
							{
								const int32 MaterialID = MaterialIDs->GetValue(OldTid);
								if (StaticMesh)
								{
									UMaterialInterface* Material = StaticMesh->GetMaterial(MaterialID);
									const int32 NewMaterialID = Materials.Find(Material);
									MaterialIDs->SetValue(NewTid, NewMaterialID);
								}
								if (SkeletalMesh)
								{
									UMaterialInterface* Material = SkeletalMesh->GetMaterials()[MaterialID].MaterialInterface;
									const int32 NewMaterialID = Materials.Find(Material);
									MaterialIDs->SetValue(NewTid, NewMaterialID);
								}
							}
						}

						OnMeshInstanceCombined(StaticMesh->GetFullName(), Id, VertexStart, Mesh.VertexCount());
					});
				}
			}
		}
	}

	bool ContainsFoliageName(const Facades::FFoliageFacade& FoliageFacade, const FString& InFoliageName)
	{
		int32 NumInstances = FoliageFacade.NumFoliageEntries();
			
		for(int32 Id = 0; Id < NumInstances; Id++)
		{
			FString FoliageName = GetFoliageName(FoliageFacade, Id);
			if(FoliageName == InFoliageName)
			{
				return true;
			}
		}

		return false;
	}

	void GetUsedFoliage(const Facades::FFoliageFacade& FoliageFacade, TArray<FString>& OutFoliageNames)
	{
		for(int32 FoliageNameIndex = 0; FoliageNameIndex < FoliageFacade.NumFoliageNames(); ++FoliageNameIndex)
		{
			FString FoliageName = FoliageFacade.GetFoliageName(FoliageNameIndex);
			if (ContainsFoliageName(FoliageFacade, FoliageName))
			{
				OutFoliageNames.Add(FoliageName);
			}
		}
	}

#if WITH_EDITOR
	void BuildNaniteAssemblyData(
		const FManagedArrayCollection& Collection,
		UStaticMesh* StaticMesh
	)
	{
		//Create NaniteAssemblyDataBuilder and the main static mesh materials to it
		FNaniteAssemblyDataBuilder AssemblyBuilder;
		for (const FStaticMaterial& Material : StaticMesh->GetStaticMaterials())
		{
			AssemblyBuilder.AddMaterialSlot(Material.MaterialInterface);
		}

		Facades::FFoliageFacade FoliageFacade(Collection);
		
		TMap<FString, int32> MeshNamePartMap;
		TMap<FString, TArray<TObjectPtr<UMaterialInterface>>> MeshMaterialsMap;

		TArray<FString> UsedFoliage;
		GetUsedFoliage(FoliageFacade, UsedFoliage);
		
		for (const FString& FoliageName : UsedFoliage)
		{
			TObjectPtr<UStaticMesh> PartStaticMesh = LoadObject<UStaticMesh>(nullptr, *FoliageName);
			TObjectPtr<USkeletalMesh> PartSkeletalMesh = LoadObject<USkeletalMesh>(nullptr, *FoliageName);

			if(PartStaticMesh)
			{
				int32 PartIndex = AssemblyBuilder.FindOrAddPart(PartStaticMesh.GetPath());
				MeshNamePartMap.FindOrAdd(PartStaticMesh.GetPath()) = PartIndex;

				for (auto Material : PartStaticMesh->GetStaticMaterials())
				{
					MeshMaterialsMap.FindOrAdd(FoliageName).AddUnique(Material.MaterialInterface);
				}
			}
			else if(PartSkeletalMesh)
			{
				auto StaticMeshName = "SM_" + PartSkeletalMesh.GetName();
				auto StaticMeshPath = PartSkeletalMesh.GetPath().Replace(*PartSkeletalMesh.GetName(), *StaticMeshName);
				int32 PartIndex = AssemblyBuilder.FindOrAddPart(StaticMeshPath);
				MeshNamePartMap.FindOrAdd(FoliageName) = PartIndex;
		
				TArray<FAssetData> AssetData;
				IAssetRegistry::Get()->GetAssetsByPath(*PartSkeletalMesh.GetPackage()->GetName(), AssetData);
		
				if(AssetData.Num() <= 0)
				{
					FDynamicMesh3 PartDynamicMesh;
					FText OutErrorMessage;

					TObjectPtr<UDynamicMesh> DynamicMesh = NewObject<UDynamicMesh>();
					
					TArray<TObjectPtr<UMaterialInterface>> PartMaterials;
					for (auto Material : PartSkeletalMesh->GetMaterials())
					{
						PartMaterials.Add(Material.MaterialInterface);
						MeshMaterialsMap.FindOrAdd(FoliageName).AddUnique(Material.MaterialInterface);
					}

					if (SkeletalMeshToDynamicMesh(PartSkeletalMesh, 0, PartDynamicMesh))
					{
						auto MeshPackagePath = PartSkeletalMesh->GetPackage()->GetName().Replace(*PartSkeletalMesh.GetName(), *StaticMeshName);
						UPackage* MeshPackage = CreatePackage(*MeshPackagePath);
						
						// Create a skeletal mesh to save in content browser
						PartStaticMesh = NewObject<UStaticMesh>(MeshPackage, FName(StaticMeshName), RF_Standalone | RF_Public);

						//Convert the dynamic mesh to static mesh
						EGeometryScriptOutcomePins Output;
#if WITH_EDITORONLY_DATA
						FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(PartMaterials, PartStaticMesh->GetNaniteSettings(), ENaniteShapePreservation::Voxelize);
#else
						FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(PartMaterials);
#endif
						DynamicMesh->SetMesh(MoveTemp(PartDynamicMesh));

						UGeometryScriptLibrary_StaticMeshFunctions::CopyMeshToStaticMesh(DynamicMesh, PartStaticMesh, Options, {}, Output);
						IAssetRegistry::Get()->AssetCreated(PartStaticMesh);
					}
				}
			}
		}

		AddNodeToBuilder(AssemblyBuilder, Collection, MeshNamePartMap, MeshMaterialsMap);
		AssemblyBuilder.ApplyToStaticMesh(*StaticMesh);
	}

	void BuildNaniteAssemblyData(
		const FManagedArrayCollection& Collection,
		USkeletalMesh* SkeletalMesh
	)
	{
		//Create NaniteAssemblyDataBuilder and the main static mesh materials to it
		FNaniteAssemblyDataBuilder AssemblyBuilder;
		Facades::FFoliageFacade FoliageFacade(Collection);
		
		for (const FSkeletalMaterial& Material : SkeletalMesh->GetMaterials())
		{
			AssemblyBuilder.AddMaterialSlot(Material.MaterialInterface);
		}

		TMap<FString, int32> MeshNamePartMap;
		TMap<FString, TArray<TObjectPtr<UMaterialInterface>>> MeshMaterialsMap;

		TArray<FString> UsedFoliage;
		GetUsedFoliage(FoliageFacade, UsedFoliage);
			
		for (const FString& FoliageName : UsedFoliage)
		{
			TObjectPtr<UStaticMesh> PartStaticMesh = LoadObject<UStaticMesh>(nullptr, *FoliageName);
			TObjectPtr<USkeletalMesh> PartSkeletalMesh = LoadObject<USkeletalMesh>(nullptr, *FoliageName);

			if(PartStaticMesh)
			{
				auto SkeletalMeshName = "SKM_" + PartStaticMesh.GetName();
				auto SkeletalMeshPath = PartStaticMesh.GetPath().Replace(*PartStaticMesh.GetName(), *SkeletalMeshName);
				int32 PartIndex = AssemblyBuilder.FindOrAddPart(SkeletalMeshPath);
				MeshNamePartMap.FindOrAdd(FoliageName) = PartIndex;
	
				TArray<FAssetData> AssetData;
				IAssetRegistry::Get()->GetAssetsByPath(*PartStaticMesh.GetPackage()->GetName(), AssetData);
	
				if(AssetData.Num() <= 0)
				{
					FDynamicMesh3 PartDynamicMesh;
					FText OutErrorMessage;

					TArray<TObjectPtr<UMaterialInterface>> PartMaterials;
					for (auto Material : PartStaticMesh->GetStaticMaterials())
					{
						PartMaterials.Add(Material.MaterialInterface);
						MeshMaterialsMap.FindOrAdd(FoliageName).AddUnique(Material.MaterialInterface);
					}

					UE::Conversion::FStaticMeshConversionOptions Options;

					if (StaticMeshToDynamicMesh(PartStaticMesh, PartDynamicMesh, OutErrorMessage, Options))
					{
						auto MeshPackagePath = PartStaticMesh->GetPackage()->GetName().Replace(*PartStaticMesh.GetName(), *SkeletalMeshName);
						UPackage* MeshPackage = CreatePackage(*MeshPackagePath);
						auto SkeletonName = "SK_" + PartStaticMesh.GetName();
						auto SkeletonPath = PartStaticMesh.GetPackage()->GetName().Replace(*PartStaticMesh.GetName(), *SkeletonName);
						UPackage* SkeletonPackage = CreatePackage(*(SkeletonPath));

						// Create a skeletal mesh to save in content browser
						PartSkeletalMesh = NewObject<USkeletalMesh>(MeshPackage, FName(SkeletalMeshName), RF_Standalone | RF_Public);
						const TObjectPtr<USkeleton> PartSkeleton = NewObject<USkeleton>(SkeletonPackage, FName(SkeletonName),
																						  RF_Standalone | RF_Public);
						PartSkeletalMesh->SetSkeleton(PartSkeleton);

						ConvertToDefaultSkeletalMesh(PartSkeletalMesh, &PartDynamicMesh, PartMaterials);

						IAssetRegistry::Get()->AssetCreated(PartSkeletalMesh);
						IAssetRegistry::Get()->AssetCreated(PartSkeleton);
					}
				}
			}
			else if (PartSkeletalMesh)
			{
				int32 PartIndex = AssemblyBuilder.FindOrAddPart(PartSkeletalMesh.GetPath());
				MeshNamePartMap.FindOrAdd(PartSkeletalMesh.GetPath()) = PartIndex;

				for (auto Material : PartSkeletalMesh->GetMaterials())
				{
					MeshMaterialsMap.FindOrAdd(FoliageName).AddUnique(Material.MaterialInterface);
				}
			}
		}

		AddNodeToBuilder(AssemblyBuilder, Collection, MeshNamePartMap, MeshMaterialsMap);
		AssemblyBuilder.ApplyToSkeletalMesh(*SkeletalMesh);
	}

	void AddNodeToBuilder(FNaniteAssemblyDataBuilder& AssemblyBuilder, const FManagedArrayCollection& Collection,
		const TMap<FString, int32>& InMeshNamePartMap, const TMap<FString, TArray<TObjectPtr<UMaterialInterface>>>& InMeshMaterialsMap)
	{
		Facades::FFoliageFacade FoliageFacade(Collection);
		int32 NumInstances = FoliageFacade.NumFoliageEntries();
			
		for(int32 Id = 0; Id < NumInstances; Id++)
		{
			FString FoliageName = GetFoliageName(FoliageFacade, Id);

			if(InMeshNamePartMap.Find(FoliageName))
			{
				int32 PartIndex = InMeshNamePartMap[FoliageName];
				
				FTransform Transform = FoliageFacade.GetFoliageTransform(Id);
				UE::Geometry::FTransformSRT3d GeoTransform(Transform);

				int32 FoliageParentBoneID = FoliageFacade.GetParentBoneID(Id);
				
				FNaniteAssemblyBoneInfluence Influence;
				Influence.BoneIndex = FoliageParentBoneID;
				//UE_LOG(LogProceduralVegetation, Warning, TEXT("Adding bone influence FoliageParentBoneID {%i}, Position{%s}, Scale{%s} , Rotation{%s}"),
				//	FoliageParentBoneID, *Transform.GetLocation().ToString(), *Transform.GetScale3D().ToString(), *Transform.GetRotation().ToString());
				Influence.BoneWeight = 1.0;
				
				AssemblyBuilder.AddNode(PartIndex, FTransform3f(GeoTransform), ENaniteAssemblyNodeTransformSpace::Local, { Influence });

				//Add the materials for part to the assembly builder
				int32 LocalMaterialIndex = 0;
				auto FoliageMaterials = InMeshMaterialsMap.Find(FoliageName);
				for (auto PartMaterial : *FoliageMaterials)
				{
					int32 PartMaterialIndex = AssemblyBuilder.GetMaterialSlots().IndexOfByPredicate(
						[&] (const auto& Slot) { return Slot.Material == PartMaterial; }
					);
					if (PartMaterialIndex == INDEX_NONE)
					{
						PartMaterialIndex = AssemblyBuilder.AddMaterialSlot(PartMaterial);
					}

					AssemblyBuilder.RemapPartMaterial(PartIndex, LocalMaterialIndex, PartMaterialIndex);
					LocalMaterialIndex++;
				}
			}
		}
	}

	void ConvertToDefaultSkeletalMesh(USkeletalMesh* SkeletalMesh, FDynamicMesh3* Mesh,TArray<TObjectPtr<UMaterialInterface>> Materials)
	{
		TObjectPtr<UDynamicMesh> DynamicMesh = NewObject<UDynamicMesh>();
		DynamicMesh->SetMesh(MoveTemp(*Mesh));
		
		//Figure out the correct parent bone index
		int ParentBoneIndex = INDEX_NONE;
		UE::Geometry::FDynamicMeshAttributeSet* MeshAttributes = DynamicMesh->GetMeshPtr()->Attributes();
		MeshAttributes->EnableBones(1);

		UE::Geometry::FDynamicMeshBoneNameAttribute* BoneNames = MeshAttributes->GetBoneNames();
		UE::Geometry::FDynamicMeshBoneParentIndexAttribute* BoneParentIndices = MeshAttributes->GetBoneParentIndices();
		UE::Geometry::FDynamicMeshBonePoseAttribute* BonePoses = MeshAttributes->GetBonePoses();

		int BoneIndex = 0;
		BoneNames->SetValue(BoneIndex, "Root");
		BonePoses->SetValue(BoneIndex, FTransform::Identity);
		BoneParentIndices->SetValue(BoneIndex, ParentBoneIndex);
		
		//Convert the dynamic mesh to static mesh
		EGeometryScriptOutcomePins Output;
#if WITH_EDITORONLY_DATA
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(Materials, SkeletalMesh->GetNaniteSettings(), ENaniteShapePreservation::Voxelize);
#else
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(PartMaterials);
#endif
		Options.BoneHierarchyMismatchHandling = EGeometryScriptBoneHierarchyMismatchHandling::CreateNewReferenceSkeleton;
		
		UGeometryScriptLibrary_StaticMeshFunctions::CopyMeshToSkeletalMesh(
			DynamicMesh,
			SkeletalMesh,
			Options,
			{},
			Output
		);

		TObjectPtr<USkeleton> Skeleton = SkeletalMesh->GetSkeleton();
		Skeleton->RecreateBoneTree(SkeletalMesh);

		const FGeometryScriptBoneWeightProfile SkinProfile = FGeometryScriptBoneWeightProfile();
		FGeometryScriptSmoothBoneWeightsOptions SmoothBoneWeightsOptions;
		SmoothBoneWeightsOptions.DistanceWeighingType = EGeometryScriptSmoothBoneWeightsType::GeodesicVoxel;
		SmoothBoneWeightsOptions.MaxInfluences = 2;
		SmoothBoneWeightsOptions.VoxelResolution = 512;
		UGeometryScriptLibrary_MeshBoneWeightFunctions::ComputeSmoothBoneWeights(
			DynamicMesh,
			Skeleton,
			SmoothBoneWeightsOptions,
			SkinProfile
		);

		const FName ProfileName = SkinProfile.GetProfileName();
		UGeometryScriptLibrary_StaticMeshFunctions::CopySkinWeightProfileToSkeletalMesh(
			DynamicMesh,
			SkeletalMesh,
			ProfileName,
			ProfileName,
			{},
			{},
			Output
		);
	}
#endif

	void ExportCollectionToStaticMesh(
		TObjectPtr<UStaticMesh> ExportMesh,
		const FManagedArrayCollection& Collection,
		bool bBuildNaniteAssemblies,
		ENaniteShapePreservation ShapePreservation
	)
	{
		FManagedArrayCollection ExportedCollection;
		Collection.CopyTo(&ExportedCollection);
		
		TObjectPtr<UDynamicMesh> DynamicMesh = CollectionToDynamicMesh(ExportedCollection);

		//Get the materials from the collection
		TArray<TObjectPtr<UMaterialInterface>> Materials = GetMaterialsFromCollection(ExportedCollection);

		//Get the foliage data from facade, spawn an actor attach the foliage to the actor
		Facades::FFoliageFacade FoliageFacade(ExportedCollection);
		
		//Combine all the foliage instances into one dynamic mesh if not building nanite assemblies
		if (!bBuildNaniteAssemblies)
		{
			CombineMeshInstancesToDynamicMesh(ExportedCollection, DynamicMesh, Materials,
				[](FString MeshName, int32 InstanceID, int32 VertexStart, int32 VertexCount){});
		}

		//Convert the dynamic mesh to static mesh
		EGeometryScriptOutcomePins Output;
#if WITH_EDITORONLY_DATA
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(Materials, ExportMesh->GetNaniteSettings(), ShapePreservation);
		
#else
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(Materials);
#endif
		UGeometryScriptLibrary_StaticMeshFunctions::CopyMeshToStaticMesh(DynamicMesh, ExportMesh, Options, {}, Output);

#if WITH_EDITOR
		if (bBuildNaniteAssemblies)
		{
			if (NaniteAssembliesSupported())
			{
				//Build the nanite assemblies
            	BuildNaniteAssemblyData(ExportedCollection, ExportMesh);
            	ExportMesh->Build(true);
				FStaticMeshCompilingManager::Get().FinishAllCompilation();
			}
			else
			{
				UE_LOG(LogProceduralVegetation, Warning, TEXT("Failed to build Nanite Assemblies, because neither Nanite Foliage nor Nanite Assemblies are enabled for the project."));
			}
		}
#endif
	}

#if WITH_EDITOR
	void BuildWindImportData(FDynamicWindSkeletalImportData& OutImportData, const FManagedArrayCollection& Collection, const TArray<PV::Facades::FBoneNode>& Bones)
	{
		Facades::FBranchFacade BranchFacade(Collection);

		for (const auto& Bone : Bones)
		{
			int32 SimulationGroupIndex = BranchFacade.GetBranchSimulationGroupIndex(Bone.BranchIndex);
			OutImportData.Joints.Add({Bone.BoneName, SimulationGroupIndex});
		}
	}
#endif

	void ExportCollectionToSkeletalMesh(
		TObjectPtr<USkeletalMesh> ExportMesh,
		const FManagedArrayCollection& Collection,
		ENaniteShapePreservation ShapePreservation,
		bool bBuildNaniteAssemblies
	)
	{
		FManagedArrayCollection ExportedCollection;
		Collection.CopyTo(&ExportedCollection);

		Facades::FFoliageFacade FoliageFacade(ExportedCollection);
		Facades::FPointFacade PointFacade(ExportedCollection);
		Facades::FBranchFacade BranchFacade(ExportedCollection);
		Facades::FBoneFacade BoneFacade = Facades::FBoneFacade(ExportedCollection);
		
		TObjectPtr<UDynamicMesh> DynamicMesh = CollectionToDynamicMesh(ExportedCollection);
		UE::Geometry::FDynamicMeshAttributeSet* MeshAttributes = DynamicMesh->GetMeshPtr()->Attributes();
		
		//Get the materials from the collection
		TArray<TObjectPtr<UMaterialInterface>> Materials = GetMaterialsFromCollection(ExportedCollection);

		TArray<Facades::FBoneNode> BoneNodes;
		BoneNodes = BoneFacade.GetBoneDataFromCollection();

		//if bones already not created with bone reduction node create bones with full density
		if (BoneNodes.IsEmpty())
		{
			BoneFacade.CreateBoneData(BoneNodes, 0);
		}
		
		AssignBoneIDsToFoliage(BoneNodes, ExportedCollection);
		
		int32 BoneCount = BoneNodes.Num();
		MeshAttributes->EnableBones(BoneCount);

		TArray<int32> VertexPointIDs;
		BoneFacade.GetPointIds(VertexPointIDs);

		TArray<int32> VertexBoneIDs;
		//Assign the Bone id to every vertex in the base mesh through VertexPointIDs
		for (const int32& PointID : VertexPointIDs)
		{
			if (Facades::FBoneNode* BoneNode = Facades::FBoneFacade::FindClosestBone(ExportedCollection, BoneNodes, PointID))
			{
				VertexBoneIDs.Add(BoneNode->BoneIndex);
			}
			else
			{
				VertexBoneIDs.Add(INDEX_NONE);
				UE_LOG(LogProceduralVegetation, Log, TEXT("Invalid Bone Assigned to PointID %i") , PointID);
			}
		}
		int FoliageVertexStart = VertexBoneIDs.Num();

		UE::Geometry::FDynamicMeshBoneNameAttribute* BoneNames = MeshAttributes->GetBoneNames();
		UE::Geometry::FDynamicMeshBoneParentIndexAttribute* BoneParentIndices = MeshAttributes->GetBoneParentIndices();
		UE::Geometry::FDynamicMeshBonePoseAttribute* BonePoses = MeshAttributes->GetBonePoses();

		for (int i = 0; i < BoneCount; i++)
		{
			BoneNames->SetValue(i, BoneNodes[i].BoneName);
			BonePoses->SetValue(i, BoneNodes[i].BoneTransform);
			BoneParentIndices->SetValue(i, BoneNodes[i].ParentBoneIndex);
		}

		if (!bBuildNaniteAssemblies)
		{
			//Combine all the foliage instances into one dynamic mesh if not building nanite assemblies
			CombineMeshInstancesToDynamicMesh(ExportedCollection, DynamicMesh, Materials,
			[&](const FString& MeshName, int32 InstanceID, int32 VertexStart, int32 VertexCount)
			{
				//Assign parent bone id to foliage vertices
				int32 FoliageParentBoneID = FoliageFacade.GetParentBoneID(InstanceID);
					
				for (int VertexID = VertexStart; VertexID < VertexCount; ++VertexID)
				{
					VertexBoneIDs.Add(FoliageParentBoneID);
					//UE_LOG(LogProceduralVegetation, Warning, TEXT("Adding VertexBoneIDs, VertexId{%i} BoneID{%i}, VertexStart{%i}, VertexCount{%i}, MeshName{%s}, InstanceID{%i}"),
					//VertexID, FoliageParentBoneID, VertexStart, VertexCount, *MeshName, InstanceID);
				}
			});
		}

		//Convert the dynamic mesh to static mesh
		EGeometryScriptOutcomePins Output;
		
#if WITH_EDITORONLY_DATA
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(Materials, ExportMesh->GetNaniteSettings(), ShapePreservation);
		
#else
		FGeometryScriptCopyMeshToAssetOptions Options = GetCopyMeshToAssetOptions(Materials);
#endif
		Options.BoneHierarchyMismatchHandling = EGeometryScriptBoneHierarchyMismatchHandling::CreateNewReferenceSkeleton;

		UGeometryScriptLibrary_StaticMeshFunctions::CopyMeshToSkeletalMesh(
			DynamicMesh,
			ExportMesh,
			Options,
			{},
			Output
		);

		TObjectPtr<USkeleton> Skeleton = ExportMesh->GetSkeleton();
		Skeleton->RecreateBoneTree(ExportMesh);

		const FGeometryScriptBoneWeightProfile SkinProfile = FGeometryScriptBoneWeightProfile();
		FGeometryScriptSmoothBoneWeightsOptions SmoothBoneWeightsOptions;

		SmoothBoneWeightsOptions.DistanceWeighingType = EGeometryScriptSmoothBoneWeightsType::DirectDistance;
		SmoothBoneWeightsOptions.MaxInfluences = 3;
		SmoothBoneWeightsOptions.Stiffness = 0.5;
		
		UGeometryScriptLibrary_MeshBoneWeightFunctions::ComputeSmoothBoneWeights(
			DynamicMesh,
			Skeleton,
			SmoothBoneWeightsOptions,
			SkinProfile
		);

		const FName ProfileName = SkinProfile.GetProfileName();
		
		//Here we make the correction to the weights
		RemoveUnwantedSkinWeights(DynamicMesh, ProfileName, VertexBoneIDs, FoliageVertexStart,BoneNodes);
		
		UGeometryScriptLibrary_StaticMeshFunctions::CopySkinWeightProfileToSkeletalMesh(
			DynamicMesh,
			ExportMesh,
			ProfileName,
			ProfileName,
			{},
			{},
			Output
		);

#if WITH_EDITOR
		if (bBuildNaniteAssemblies)
		{
			if (NaniteAssembliesSupported())
			{
				//Build the nanite assemblies
				BuildNaniteAssemblyData(ExportedCollection, ExportMesh);
			}
			else
			{
				UE_LOG(LogProceduralVegetation, Warning, TEXT("Failed to build Nanite Assemblies, because neither Nanite Foliage nor Nanite Assemblies are enabled for the project."));
			}
		}

		FDynamicWindSkeletalImportData ImportData;
		BuildWindImportData(ImportData,ExportedCollection, BoneNodes);
				
		if (!DynamicWind::ImportSkeletalData(*ExportMesh, ImportData))
		{
			UE_LOG(LogTemp, Warning, TEXT("Failed to build wind data"));
		}
				
		ExportMesh->Build();
		FSkinnedAssetCompilingManager::Get().FinishAllCompilation();
#endif
	}

	void AttachProceduralVegetationLink(UObject* InExportedMesh, const TObjectPtr<UProceduralVegetation>& InProceduralVegetation)
	{
		if (IInterface_AssetUserData* IAssetUserData = Cast<IInterface_AssetUserData>(InExportedMesh))
		{
			UProceduralVegetationLink* Data = NewObject<UProceduralVegetationLink>(InExportedMesh);
			Data->Source = InProceduralVegetation;
		
			IAssetUserData->AddAssetUserData(Data);	
		}
	}

	void AssignBoneIDsToFoliage(const TArray<Facades::FBoneNode>& Bones, FManagedArrayCollection& Collection)
	{
		Facades::FPointFacade PointFacade(Collection);
		Facades::FFoliageFacade FoliageFacade(Collection);
		
		int32 NumInstances = FoliageFacade.NumFoliageEntries();

		auto FindBoneById = ( [&](const int32 Id)
		{
			const Facades::FBoneNode* BoneNode = Bones.FindByPredicate([Id](const Facades::FBoneNode& Node)
			{
				return Node.BoneIndex == Id;
			});
			return BoneNode;
		});
		
		for(int32 Id = 0; Id < NumInstances; Id++)
		{
			Facades::FFoliageEntryData Data = FoliageFacade.GetFoliageEntry(Id);
			float FoliageLFR = Data.LengthFromRoot;

			TArray<int32> BoneIDs;
			for (Facades::FBoneNode BoneNode : Bones)
			{
				if (Data.BranchId == BoneNode.BranchIndex)
				{
					BoneIDs.Add(BoneNode.BoneIndex);
				}
			}

			bool bBoneIDAssigned = false;
			for (const int32& BoneId : BoneIDs)
			{
				const Facades::FBoneNode* BoneNode = FindBoneById(BoneId);
				check(BoneNode);
				
				int PointIndex = BoneNode->PointIndex;
				const Facades::FBoneNode* BoneParentNode = FindBoneById(BoneNode->ParentBoneIndex);
				
				int ParentPointIndex = BoneParentNode ? BoneParentNode->PointIndex : INDEX_NONE;
				float BoneLFR = PointFacade.GetLengthFromRoot(PointIndex);
				float BoneParentLFR = PointFacade.GetLengthFromRoot(ParentPointIndex);

				if (FoliageLFR <= BoneLFR && FoliageLFR >= BoneParentLFR)
				{
					FoliageFacade.SetParentBoneID(Id, BoneId);
					bBoneIDAssigned = true;
					break;
				}
			}

			if (!bBoneIDAssigned)
			{
				UE_LOG(LogProceduralVegetation, Warning, TEXT("No bone assigned for foliage Id {%i} , Branch Bone count {%i}"), Id , BoneIDs.Num());
			}
		}
	}

	void RemoveUnwantedSkinWeights(TObjectPtr<UDynamicMesh> DynamicMesh, const FName ProfileName, const TArray<int32>& VertexBoneIDs, int32 FoliageVertexStart, const TArray<Facades::FBoneNode>& BoneNodes)
	{
		auto InMesh = DynamicMesh->GetMeshPtr();
		check(InMesh)
		const int32 NumVertices = VertexBoneIDs.Num();
		
		DynamicMesh->EditMesh([&](FDynamicMesh3& EditMesh)
		{
			UE::Geometry::FDynamicMeshVertexSkinWeightsAttribute *SkinWeights = EditMesh.Attributes()->GetSkinWeightsAttribute(ProfileName);

			ParallelFor(NumVertices, [&](const int32 VertexIdx)
			{
				int32 BoneID = VertexBoneIDs[VertexIdx];
				//UE_LOG(LogProceduralVegetation, Warning, TEXT("Remove Bones, VertexId{%i} BoneID{%i} BoneParentIndex{%i}"), VertexIdx, BoneID, ParentBoneID);

				if(BoneID != INDEX_NONE)
				{
					int32 ParentBoneID = BoneNodes[BoneID].ParentBoneIndex;
				
					//UE_LOG(LogProceduralVegetation, Warning, TEXT("Remove Bones, VertexId{%i} BoneID{%i} BoneParentIndex{%i}"), VertexIdx, BoneID, ParentBoneID);

					UE::AnimationCore::FBoneWeights Weights;
					SkinWeights->GetValue(VertexIdx, Weights);

					auto NextBone = BoneNodes.FindByPredicate([&](const Facades::FBoneNode& Node)
					{
						return Node.BoneIndex == BoneID + 1 && Node.BranchIndex == BoneNodes[BoneID].BranchIndex;
					});

					for (int32 WeightID = Weights.Num() - 1 ; WeightID >= 0; WeightID--)
					{
						auto Weight = Weights[WeightID];

						bool bValidBone = (Weight.GetBoneIndex() == ParentBoneID);
						bValidBone |= (Weight.GetBoneIndex() == BoneID);
						bValidBone |= NextBone && (Weight.GetBoneIndex() == NextBone->BoneIndex);
						
						if (!bValidBone || VertexIdx > FoliageVertexStart || BoneID == 0)
						{
							UE::AnimationCore::FBoneWeightsSettings Settings;
							Settings.SetNormalizeType(UE::AnimationCore::EBoneWeightNormalizeType::Always);
							Weights.RemoveBoneWeight(Weight.GetBoneIndex(),Settings);
						}
					}

					if (VertexIdx > FoliageVertexStart || BoneID == 0 || Weights.Num() == 0)
					{
						UE::AnimationCore::FBoneWeightsSettings Settings;
						Settings.SetNormalizeType(UE::AnimationCore::EBoneWeightNormalizeType::Always);
						Weights.SetBoneWeight(UE::AnimationCore::FBoneWeight(BoneID, 1.0f), Settings);
					}
					
					SkinWeights->SetNewValue(VertexIdx, Weights);
				}
				else
				{
					UE_LOG(LogProceduralVegetation, Log, TEXT("Invalid bone index found while removing bones for vertex %i"), VertexIdx);
				}
			});
				
		}, EDynamicMeshChangeType::GeneralEdit, EDynamicMeshAttributeChangeFlags::Unknown, false);
	}
}

namespace PV::Export
{
	void ExportCollectionAsMesh(
		const TObjectPtr<UProceduralVegetation> InProceduralVegetation,
		const FManagedArrayCollection& Collection,
		const FManagedArrayCollection& FoliageCollection,
		const FPVExportParams& ExportParams
	)
	{
		// Set up the Package path and name from ExportParams
		const FString PackageName = ExportParams.ContentBrowserFolder.Path;
		const FString MeshName = ExportParams.MeshName.ToString();

		const FString FullPath = FPaths::Combine(PackageName, MeshName);

		if (ExportParams.ExportMeshType == EPVExportMeshType::StaticMesh)
		{
			UPackage* MeshPackage = CreatePackage(*FullPath);

			// Create a static mesh to save in content browser
			const TObjectPtr<UStaticMesh> ExportMesh = NewObject<UStaticMesh>(MeshPackage, FName(MeshName), RF_Standalone | RF_Public);

			Internal::AttachProceduralVegetationLink(ExportMesh, InProceduralVegetation);
			
			PV::Export::Internal::ExportCollectionToStaticMesh(
				ExportMesh,
				Collection,
				ExportParams.bCreateNaniteFoliage,
				ExportParams.NaniteShapePreservation
			);

			MeshPackage->SetDirtyFlag(true);

			IAssetRegistry::Get()->AssetCreated(ExportMesh);
		}
		else if (ExportParams.ExportMeshType == EPVExportMeshType::SkeletalMesh)
		{
			UPackage* MeshPackage = CreatePackage(*FullPath);
			UPackage* SkeletonPackage = CreatePackage(*(FullPath + "_Skeleton"));

			FAssetData AssetData;
			FString ErrorMessage;

			TObjectPtr<USkeletalMesh> ExportMesh = nullptr;
			
			if (Utilities::CanOverwriteAsset(FullPath, USkeletalMesh::StaticClass(), AssetData, ErrorMessage))
			{
				ExportMesh = CastChecked<USkeletalMesh>(AssetData.GetAsset());
			}
			else
			{
				ExportMesh = NewObject<USkeletalMesh>(MeshPackage, FName(MeshName), RF_Standalone | RF_Public);
			}

			TObjectPtr<USkeleton> ExportSkeleton = nullptr;
			if (Utilities::CanOverwriteAsset(*(FullPath + "_Skeleton"), USkeleton::StaticClass(), AssetData, ErrorMessage))
			{
				ExportSkeleton = CastChecked<USkeleton>(AssetData.GetAsset());
			}
			else
			{
				ExportSkeleton = NewObject<USkeleton>(SkeletonPackage, FName(MeshName + "_Skeleton"),RF_Standalone | RF_Public);
			}
			
			Internal::AttachProceduralVegetationLink(ExportMesh, InProceduralVegetation);
			Internal::AttachProceduralVegetationLink(ExportSkeleton, InProceduralVegetation);
			
			ExportMesh->SetSkeleton(ExportSkeleton);

			PV::Export::Internal::ExportCollectionToSkeletalMesh(
				ExportMesh,
				Collection,
				ExportParams.NaniteShapePreservation,
				ExportParams.bCreateNaniteFoliage
			);

			MeshPackage->SetDirtyFlag(true);
			SkeletonPackage->SetDirtyFlag(true);

			IAssetRegistry::Get()->AssetCreated(ExportMesh);
			IAssetRegistry::Get()->AssetCreated(ExportSkeleton);
		}
	}
}
