// Copyright Epic Games, Inc. All Rights Reserved.

#include "USDNaniteAssemblyTranslator.h"

#if USE_USD_SDK && WITH_EDITOR
#include "Engine/StaticMesh.h"
#include "IMeshBuilderModule.h"
#include "Misc/Paths.h"
#include "NaniteAssemblyDataBuilder.h"
#include "UObject/Package.h"
#include "Materials/MaterialInterface.h"

#include "USDAssetUserData.h"
#include "USDGeomMeshTranslator.h"
#include "USDErrorUtils.h"
#include "USDObjectUtils.h"
#include "USDPrimConversion.h"
#include "USDMemory.h"
#include "USDTranslatorUtils.h"
#include "USDTypesConversion.h"
#include "USDIntegrationUtils.h"

#include "Objects/USDPrimLinkCache.h"

#include "UsdWrappers/SdfPath.h"
#include "UsdWrappers/UsdGeomXformable.h"
#include "UsdWrappers/UsdPrim.h"
#include "UsdWrappers/UsdStage.h"

#include "USDIncludesStart.h"
#include "pxr/usd/usd/timeCode.h"
#include "pxr/usd/usdGeom/xformable.h"
#include "pxr/usd/usdGeom/pointInstancer.h"
#include "pxr/usd/usdGeom/primvarsAPI.h"
#include "pxr/usd/usdSkel/skeleton.h"
#include "pxr/usd/usdSkel/root.h"
#include "USDIncludesEnd.h"

#include <algorithm> 
#include <unordered_map>

namespace UE::UsdNaniteAssemblyTranslator::Private
{
	namespace Tokens
	{
		static const pxr::TfToken NaniteAssemblyRootAPI			{ "NaniteAssemblyRootAPI" };
		static const pxr::TfToken NaniteAssemblyExternalRefAPI	{ "NaniteAssemblyExternalRefAPI" };
		static const pxr::TfToken NaniteAssemblySkelBindingAPI	{ "NaniteAssemblySkelBindingAPI" };
		static const pxr::TfToken MeshType						{ "unreal:naniteAssembly:meshType" };
		static const pxr::TfToken MeshAssetPath					{ "unreal:naniteAssembly:meshAssetPath" };
		static const pxr::TfToken Skeleton						{ "unreal:naniteAssembly:skeleton" };
		static const pxr::TfToken BindJoints					{ "primvars:unreal:naniteAssembly:bindJoints" };
		static const pxr::TfToken BindJointWeights				{ "primvars:unreal:naniteAssembly:bindJointWeights" };
		static const pxr::TfToken StaticMesh					{ "staticMesh" };
		static const pxr::TfToken SkeletalMesh					{ "skeletalMesh" };
	}

	enum class ERootType : uint32
	{
		/** The prim either does not have the root API schema or has an invalid meshType */
		None,
		/** Static Mesh Nanite Assembly root */
		StaticMesh,
		/** Skeletal Mesh Nanite Assembly root */
		SkeletalMesh
	};

	/**
	* Wrapper for a TArrayView<FNaniteAssemblyBoneInfluence> that also tracks an additional element
	* size, needed to handle the correct per-instance stride on vectorized pointinstancer bindings.
	*/
	class FBindingView
	{
	public:

		FBindingView() = default;

		FBindingView(const TArray<FNaniteAssemblyBoneInfluence>& InBoneInfluences, int32 InElementSize)
			: BoneInfluences(InBoneInfluences)
		{
			// Element size cannot be less that 1
			ElementSize = std::max(1, InElementSize);
		}

		TArrayView<const FNaniteAssemblyBoneInfluence> GetView() const
		{
			return BoneInfluences;
		}

		TArrayView<const FNaniteAssemblyBoneInfluence> GetViewForIndex(int32 Index) const
		{
			const int32 Offset = Index * ElementSize;
			if (Offset + ElementSize <= BoneInfluences.Num())
			{
				return MakeArrayView(BoneInfluences.GetData() + Offset, ElementSize);
			}

			return {};
		}

		bool IsValidForInstanceCount(int32 NumInstances) const
		{
			return BoneInfluences.Num() == NumInstances * ElementSize;
		}

		int32 Num() const
		{
			return BoneInfluences.Num();
		}

	protected:

		TArrayView<const FNaniteAssemblyBoneInfluence> BoneInfluences;
		int32 ElementSize = 1;
	};

	template <class T>
	bool ApplyMaskToArray(std::vector<bool> const& Mask, pxr::VtArray<T>* DataArray, const int ElementSize = 1)
	{
		// XXX Temp replacement/fix for OpenUSD UsdGeomPointInstancer::ApplyMaskToArray implementation
		// which (as of 25.5) does not correctly handle element sizes greater than 1.
		// 
		if (!DataArray)
		{
			return false;
		}

		size_t MaskSize = Mask.size();
		if (MaskSize == 0 || DataArray->size() == static_cast<size_t>(ElementSize))
		{
			return true;
		}
		else if ((MaskSize * ElementSize) != DataArray->size())
		{
			return false;
		}

		T* BeginData = DataArray->data();
		T* CurrData = BeginData;
		size_t NumPreserved = 0;
		for (size_t i = 0; i < MaskSize; ++i)
		{
			if (Mask[i]) 
			{
				for (int j = 0; j < ElementSize; ++j)
				{
					*CurrData = BeginData[(i * ElementSize) + j];
					++CurrData;
				}
				NumPreserved += ElementSize;
			}
		}
		if (NumPreserved < DataArray->size())
		{
			DataArray->resize(NumPreserved);
		}
		return true;
	}

	ERootType GetNaniteAssemblyRootType(const pxr::UsdPrim& Prim)
	{
		if (UsdUtils::PrimHasSchema(Prim, Tokens::NaniteAssemblyRootAPI))
		{
			if (pxr::UsdAttribute MeshTypeAttr = Prim.GetAttribute(Tokens::MeshType))
			{
				// We need to be careful reading the meshType token here. If the user has accidentally authored a string (which is quite easy
				// from many DCC's that support strings but not tokens), querying the attribute as token will succeed, but will give back the 
				// schema default "staticMesh" irrespective of what the user may have authored into the string version of the attribute. So we 
				// check the held type and attempt to read a string if that's the underlying type the attribute is holding.
				pxr::VtValue MeshTypeVtValue;
				if (MeshTypeAttr.Get(&MeshTypeVtValue, pxr::UsdTimeCode::EarliestTime()))
				{
					pxr::TfToken MeshTypeValue;
					if (MeshTypeVtValue.IsHolding<pxr::TfToken>())
					{
						MeshTypeValue = MeshTypeVtValue.UncheckedGet<pxr::TfToken>();
					}
					else if (MeshTypeVtValue.IsHolding<std::string>())
					{
						MeshTypeValue = pxr::TfToken(MeshTypeVtValue.UncheckedGet<std::string>());
					}
					else
					{
						USD_LOG_WARNING(
							TEXT("NaniteAssemblyRootAPI is applied to prim '%s' but attribute '%s' is not a valid type."),
							*UsdToUnreal::ConvertPath(Prim.GetPath()),
							*UsdToUnreal::ConvertToken(MeshTypeAttr.GetName())
						);

						return ERootType::None;
					}

					if (MeshTypeValue == Tokens::StaticMesh)
					{
						return ERootType::StaticMesh;
					}

					if (MeshTypeValue == Tokens::SkeletalMesh)
					{
						return ERootType::SkeletalMesh;
					}
				}
			}
		}

		return ERootType::None;
	}

	bool IsNaniteAssemblyRoot(const pxr::UsdPrim& Prim)
	{
		return GetNaniteAssemblyRootType(Prim) != ERootType::None;
	}

	bool ResolveNaniteAssemblyRootSkeleton(const pxr::UsdPrim& Prim, pxr::UsdSkelSkeleton& Skeleton, pxr::UsdSkelRoot& SkelRoot)
	{
		if (!Prim)
		{
			return false;
		}

		FScopedUsdAllocs UsdAllocs;

		if (pxr::UsdRelationship SkelRel = Prim.GetRelationship(Tokens::Skeleton))
		{
			pxr::SdfPathVector Targets;
			if (SkelRel.GetTargets(&Targets) && !Targets.empty())
			{
				if (Targets[0].HasPrefix(Prim.GetPrimPath()))
				{
					Skeleton = pxr::UsdSkelSkeleton(Prim.GetStage()->GetPrimAtPath(Targets[0]));
					if (Skeleton)
					{
						SkelRoot = pxr::UsdSkelRoot::Find(Skeleton.GetPrim());
						if (!SkelRoot || !SkelRoot.GetPrim().GetPrimPath().HasPrefix(Prim.GetPrimPath()))
						{
							return false;
						}
					}
				}
			}
		}

		return Skeleton && SkelRoot;
	}

	TArray<FNaniteAssemblyBoneInfluence> GetJointBindings(
		const pxr::UsdPrim& Prim,
		const pxr::VtArray<pxr::TfToken>& SkelJoints,
		const pxr::VtArray<pxr::TfToken>& SkelJointNames,
		float Time,
		int32& OutElementSize)
	{
		using namespace UE::UsdNaniteAssemblyTranslator::Private;

		if (!UsdUtils::PrimHasSchema(Prim, Tokens::NaniteAssemblySkelBindingAPI))
		{
			return {};
		}

		pxr::VtArray<pxr::TfToken> BindJoints;
		pxr::VtArray<float> BindJointWeights;
		{
			FScopedUsdAllocs UsdAllocs;
		
			const pxr::UsdGeomPrimvarsAPI Primvars(Prim);

			// Retrieve the list of bind joints and weights on the prim. Weights are optional.
			pxr::UsdGeomPrimvar BindJointsPrimvar = Primvars.GetPrimvar(Tokens::BindJoints);
			if (!BindJointsPrimvar)
			{
				USD_LOG_WARNING(
					TEXT("Prim '%s' has schema '%s' applied, but attempt to get primvar '%s' failed."),
					*UsdToUnreal::ConvertPath(Prim.GetPath()),
					*UsdToUnreal::ConvertToken(Tokens::NaniteAssemblySkelBindingAPI),
					*UsdToUnreal::ConvertToken(Tokens::BindJoints)
				);
				return {};
			}

			BindJointsPrimvar.Get(&BindJoints);
			if (BindJoints.empty())
			{
				USD_LOG_WARNING(
					TEXT("Prim '%s' has schema '%s' applied, but primvar '%s' is empty."),
					*UsdToUnreal::ConvertPath(Prim.GetPath()),
					*UsdToUnreal::ConvertToken(Tokens::NaniteAssemblySkelBindingAPI),
					*UsdToUnreal::ConvertToken(Tokens::BindJoints)
				);
				return {};
			}

			OutElementSize = static_cast<int32>(BindJointsPrimvar.GetElementSize());

			// Get weights, if any.
			if (pxr::UsdGeomPrimvar BindJointWeightsPrimvar = Primvars.GetPrimvar(Tokens::BindJointWeights))
			{
				BindJointWeightsPrimvar.Get(&BindJointWeights);
			}

			if (pxr::UsdGeomPointInstancer PointInstancer = pxr::UsdGeomPointInstancer(Prim))
			{
				// If the number of bindings is greater than the instance count multiplied by the authored element size, it's
				// possible we are picking up the default primvar element size of 1 because the user forgot to author it. Rather 
				// than fail, check if the available bindings are an exact multiple of the instance count and if so, use that as 
				// the element size instead. If this attempt fails the invalid size(s) will be reported during assembly construction.
				const size_t NumInstances = PointInstancer.GetInstanceCount(Time);
				const int32 NumBindings = BindJoints.size();
				if (NumInstances > 0 && OutElementSize == 1 && NumBindings > NumInstances * OutElementSize)
				{
					if (NumBindings % NumInstances == 0)
					{
						OutElementSize = NumBindings / NumInstances;

						USD_LOG_WARNING(
							TEXT("Using inferred element size (%d) for Nanite Assembly PointInstancer primvar '%s.%s'"),
							OutElementSize,
							*UsdToUnreal::ConvertPath(Prim.GetPath()),
							*UsdToUnreal::ConvertToken(Tokens::BindJoints)
						);
					}
				}

				// Remove masked joints and weights. Note that attempting to mask an incorrectly sized array will fail
				// because the input data must be the correct element-size multiple of the mask size.
				std::vector<bool> Mask = PointInstancer.ComputeMaskAtTime(Time);
				if (!ApplyMaskToArray(Mask, &BindJoints, OutElementSize))
				{
					USD_LOG_WARNING(
						TEXT("Failed to apply mask data (invisibleIds, inactiveIds) to Nanite Assembly PointInstancer primvar '%s.%s'"),
						*UsdToUnreal::ConvertPath(Prim.GetPath()),
						*UsdToUnreal::ConvertToken(Tokens::BindJoints)
					);
				}
				if (!BindJointWeights.empty())
				{
					if (!ApplyMaskToArray(Mask, &BindJointWeights, OutElementSize))
					{
						USD_LOG_WARNING(
							TEXT("Failed to apply mask data (invisibleIds, inactiveIds) to Nanite Assembly PointInstancer primvar '%s.%s'"),
							*UsdToUnreal::ConvertPath(Prim.GetPath()),
							*UsdToUnreal::ConvertToken(Tokens::BindJoints)
						);
					}
				}
			}
		}

		TArray<FNaniteAssemblyBoneInfluence> Output;
		for (size_t BindJointIndex = 0; BindJointIndex < BindJoints.size(); ++BindJointIndex)
		{
			const pxr::TfToken& BindJoint = BindJoints[BindJointIndex];

			// TODO: replace the linear searches here with table lookups of some kind
			// first, see if it matches a unique joint name
			uint32 JointIndex = std::find(SkelJointNames.begin(), SkelJointNames.end(), BindJoint) - SkelJointNames.begin();
			if (JointIndex >= SkelJointNames.size())
			{
				// fall back to finding them by joint path
				JointIndex = std::find(SkelJoints.begin(), SkelJoints.end(), BindJoint) - SkelJoints.begin();
			}
			if (JointIndex >= SkelJoints.size())
			{
				USD_LOG_WARNING(
					TEXT("Joint '%s' not found on Nanite Assembly Root skeleton (referenced by '%s')"),
					*UsdToUnreal::ConvertToken(BindJoint),
					*UsdToUnreal::ConvertPath(Prim.GetPrimPath())
				);
			}
			else
			{
				const float JointWeight = BindJointIndex < BindJointWeights.size() ? BindJointWeights[BindJointIndex] : 1.0f;
				Output.Emplace(JointIndex, JointWeight);
			}
		}

		return Output;
	}

	FTopLevelAssetPath GetExternalAssetRef(const pxr::UsdPrim& Prim)
	{
		if (UsdUtils::PrimHasSchema(Prim, Tokens::NaniteAssemblyExternalRefAPI))
		{
			if (pxr::UsdAttribute Attr = Prim.GetAttribute(Tokens::MeshAssetPath))
			{
				pxr::TfToken AttrValue;
				if (Attr.Get(&AttrValue) && !AttrValue.IsEmpty())
				{	
					return FTopLevelAssetPath(UsdToUnreal::ConvertToken(AttrValue));
				}
			}
		}

		return {};
	}

	TArray<UE::FSdfPath> GetPointInstancerPrototypePaths(const UE::FUsdPrim& Prim)
	{		
		FScopedUsdAllocs UsdAllocs;

		pxr::UsdGeomPointInstancer PointInstancer(Prim);
		const pxr::UsdRelationship& Prototypes = PointInstancer.GetPrototypesRel();

		pxr::SdfPathVector UsdPrototypePaths;
		Prototypes.GetTargets(&UsdPrototypePaths);
		{
			FScopedUnrealAllocs UnrealAllocs;

			TArray<UE::FSdfPath> PrototypePaths;
			PrototypePaths.Reserve(static_cast<int32>(UsdPrototypePaths.size()));
			for (const pxr::SdfPath& UsdPath : UsdPrototypePaths)
			{
				PrototypePaths.Add(UE::FSdfPath{ UsdPath });
			}

			return PrototypePaths;
		}
	}

	TArray<int32> GetPointInstancerProtoIndices(const UE::FUsdPrim& Prim, float Time)
	{
		FScopedUsdAllocs UsdAllocs;

		pxr::UsdGeomPointInstancer PointInstancer(Prim);
		if (const pxr::UsdAttribute ProtoIndicesAttr = PointInstancer.GetProtoIndicesAttr())
		{
			pxr::VtArray<int> ProtoIndicesArr;
			if (ProtoIndicesAttr.Get(&ProtoIndicesArr, Time))
			{
				std::vector<bool> Mask = PointInstancer.ComputeMaskAtTime(Time);
				ApplyMaskToArray(Mask, &ProtoIndicesArr);

				FScopedUnrealAllocs UnrealAllocs;

				TArray<int32> ProtoIndices;
				ProtoIndices.Reserve(ProtoIndicesArr.size());

				for (auto Index = 0; Index < ProtoIndicesArr.size(); ++Index)
				{
					ProtoIndices.Add(static_cast<int32>(ProtoIndicesArr[Index]));
				}

				return ProtoIndices;
			}
		}

		USD_LOG_WARNING(
			TEXT("Failed to get PointInstancer proto indices for prim '%s'"),
			*Prim.GetPrimPath().GetString()
		);

		return {};
	}

	TArray<FTransform> GetPointInstancerTransforms(const UE::FUsdPrim& Prim, const FTransform& Transform, float Time)
	{
		FScopedUsdAllocs UsdAllocs;

		pxr::UsdGeomPointInstancer PointInstancer(Prim);
		pxr::VtMatrix4dArray UsdInstanceTransforms;

		// We don't want the prototype root prims transforms to be included in these, as they'll already be baked into the meshes themselves
		if (!PointInstancer.ComputeInstanceTransformsAtTime(&UsdInstanceTransforms, Time, Time, pxr::UsdGeomPointInstancer::ExcludeProtoXform))
		{
			USD_LOG_WARNING(
				TEXT("Failed to compute PointInstancer transforms for prim '%s'"),
				*Prim.GetPrimPath().GetString()
			);

			return {};
		}

		{
			FScopedUnrealAllocs UnrealAllocs;

			FUsdStageInfo StageInfo{ Prim.GetStage() };
			TArray<FTransform> InstanceTransforms;
			InstanceTransforms.Reserve(static_cast<int32>(UsdInstanceTransforms.size()));
			for (const pxr::GfMatrix4d& UsdMatrix : UsdInstanceTransforms)
			{
				InstanceTransforms.Add(UsdToUnreal::ConvertMatrix(StageInfo, UsdMatrix) * Transform);
			}

			return InstanceTransforms;
		}
	}
}

class FUsdNaniteAssemblyCreateAssetsTaskChain : public FBaseBuildStaticMeshTaskChain
{
public:
	explicit FUsdNaniteAssemblyCreateAssetsTaskChain(
		const TSharedRef<FUsdSchemaTranslationContext>& InContext,
		const UE::FSdfPath& InPrimPath)
		: FBaseBuildStaticMeshTaskChain(InContext, InPrimPath)
	{
		SetupCommonTasks();
		SetupStaticMeshTasks();
	}

	explicit FUsdNaniteAssemblyCreateAssetsTaskChain(
		const TSharedRef<FUsdSchemaTranslationContext>& InContext,
		const UE::FSdfPath& InPrimPath,
		const pxr::UsdSkelSkeleton& InSkeleton,
		const pxr::UsdSkelRoot& InSkelRoot)
		: FBaseBuildStaticMeshTaskChain(InContext, InPrimPath)
		, Skeleton(InSkeleton)
		, SkelRoot(InSkelRoot)
	{
		const UE::FSdfPath SkeletonPath = UE::FUsdPrim(Skeleton.Get().GetPrim()).GetPrimPath();

		BaseSkeletalMesh = Context->PrimLinkCache->GetSingleAssetForPrim<USkeletalMesh>(SkeletonPath);
		if (BaseSkeletalMesh == nullptr)
		{
			USD_LOG_WARNING(
				TEXT("Failed to find Skeletal Mesh asset for USD Skeleton '%s'"),
				*SkeletonPath.GetString()
			);

			return;
		}

		// Cache the joints and their unique names for binding lookups
		pxr::UsdAttribute JointsAttr = Skeleton.Get().GetJointsAttr();
		pxr::UsdAttribute JointNamesAttr = Skeleton.Get().GetJointNamesAttr();
		if (JointsAttr)
		{
			JointsAttr.Get(&SkelJoints.Get());
		}
		if (JointNamesAttr)
		{
			JointNamesAttr.Get(&SkelJointNames.Get());
		}

		// Initialize the materials from the base skeletal mesh
		for (const FSkeletalMaterial& Material : BaseSkeletalMesh->GetMaterials())
		{
			Builder.AddMaterialSlot(Material.MaterialInterface);
		}

		SetupCommonTasks();
		SetupSkelMeshTasks();
	}

protected:
	FNaniteAssemblyDataBuilder Builder;
	TUsdStore<pxr::UsdSkelSkeleton> Skeleton;
	TUsdStore<pxr::UsdSkelRoot> SkelRoot;
	TUsdStore<pxr::VtArray<pxr::TfToken>> SkelJoints;
	TUsdStore<pxr::VtArray<pxr::TfToken>> SkelJointNames;
	USkeletalMesh* BaseSkeletalMesh = nullptr;
	USkeletalMesh* SkeletalMesh = nullptr;

	using PrototypeAssetsTable = std::unordered_map<int, TArray<TWeakObjectPtr<UObject>>>;
	using FBindingView = UE::UsdNaniteAssemblyTranslator::Private::FBindingView;

	UE::FUsdPrim GetPrim() const
	{
		return Context->Stage.GetPrimAtPath(PrimPath);
	}

	bool IsSkelMesh() const
	{
		if (*Skeleton)
		{
			return true;
		}
		return false;
	}

	bool AddNode(
		const pxr::UsdPrim& Prim,
		const UObject* PartMesh,
		const FTransform& LocalTransform,
		TArrayView<const FNaniteAssemblyBoneInfluence> Bindings,
		int32 &OutPartIndex)
	{
		using namespace UE::UsdNaniteAssemblyTranslator::Private;

		const FSoftObjectPath MeshPath(PartMesh);
		OutPartIndex = Builder.FindPart(MeshPath);

		const bool bNewPart = (OutPartIndex == INDEX_NONE);
		if (bNewPart)
		{
			OutPartIndex = Builder.AddPart(MeshPath);
		}

		Builder.AddNode(OutPartIndex, FTransform3f(LocalTransform), ENaniteAssemblyNodeTransformSpace::Local, Bindings);

		return bNewPart;
	}

	void AddNodeAndBindMaterials(
		const pxr::UsdPrim& Prim,
		const UObject* PartMesh,
		const FTransform& LocalTransform,
		TArrayView<const FNaniteAssemblyBoneInfluence> Bindings)
	{
		int32 PartIndex;
		if (AddNode(Prim, PartMesh, LocalTransform, Bindings, PartIndex))
		{
			ForEachPartMeshMaterial(
				PartMesh,
				[this, PartIndex](int32 LocalMaterialIndex, const TObjectPtr<UMaterialInterface>& PartMaterial)
				{
					int32 MaterialIndex = INDEX_NONE;

					// TODO: We should probably add more control to the import options than just a bool (i.e. merge by index,
					// slot name, identical materials, or append)
					if (Context->bMergeIdenticalMaterialSlots)
					{
						MaterialIndex = Builder.GetMaterialSlots().IndexOfByPredicate(
							[&PartMaterial](const FNaniteAssemblyDataBuilder::FMaterialSlot& ExistingMaterial)
							{
								return ExistingMaterial.Material == PartMaterial;
							}
						);
					}
					
					if (MaterialIndex == INDEX_NONE)
					{
						MaterialIndex = Builder.AddMaterialSlot(PartMaterial);
					}

					Builder.RemapPartMaterial(PartIndex, LocalMaterialIndex, MaterialIndex);
				}
			);
		}
	}

	template <typename TFunc>
	void ForEachPartMeshMaterial(const UObject* MeshObject, TFunc&& Func)
	{
		int32 LocalMaterialIndex = 0;
		if (IsSkelMesh())
		{
			for (const FSkeletalMaterial& SkeletalMaterial : CastChecked<USkeletalMesh>(MeshObject)->GetMaterials())
			{
				Func(LocalMaterialIndex++, SkeletalMaterial.MaterialInterface);
			}
		}
		else
		{
			for (const FStaticMaterial& StaticMaterial : CastChecked<UStaticMesh>(MeshObject)->GetStaticMaterials())
			{
				Func(LocalMaterialIndex++, StaticMaterial.MaterialInterface);
			}
		}
	}

	PrototypeAssetsTable CollectPointInstancerAssets(const UE::FUsdPrim& PointInstancerPrim, const TArray<UE::FSdfPath>& PrototypePaths)
	{
		PrototypeAssetsTable AssetsByPrototypeIndex;
		AssetsByPrototypeIndex.reserve(PrototypePaths.Num());
		if (IsSkelMesh())
		{
			for (int Index = 0; Index < PrototypePaths.Num(); ++Index)
			{
				const UE::FUsdPrim PrototypePrim = Context->Stage.GetPrimAtPath(PrototypePaths[Index]);
				const TArray<UE::FUsdPrim> SkeletonPrims = UsdUtils::GetAllPrimsOfType(PrototypePrim, TEXT("UsdSkelSkeleton"));
				for (const UE::FUsdPrim& SkeletonPrim : SkeletonPrims)
				{
					for (USkeletalMesh* SkelMesh : Context->PrimLinkCache->GetAssetsForPrim<USkeletalMesh>(SkeletonPrim.GetPrimPath()))
					{
						AssetsByPrototypeIndex[Index].Emplace(SkelMesh);
					}
				}
			}
		}
		else
		{
			// Static Mesh assets for the prototypes should have been generated by the PointInstancer translator, 
			// however they will be associated with the pointinstancer instead of each individual prototype.
			// The corresponding prototype path is available as user data however so we consult that.
			TArray<UStaticMesh*> AllPrototypeMeshes = Context->PrimLinkCache->GetAssetsForPrim<UStaticMesh>(PointInstancerPrim.GetPrimPath());
			for (UStaticMesh* PrototypeMesh : AllPrototypeMeshes)
			{
				if (UUsdAssetUserData* UserData = PrototypeMesh->GetAssetUserData<UUsdAssetUserData>())
				{
					for (const FString& SourcePrimPath : UserData->PrimPaths)
					{
						int32 Index;
						if (PrototypePaths.Find(UE::FSdfPath(*SourcePrimPath), Index))
						{
							AssetsByPrototypeIndex[Index].Emplace(PrototypeMesh);
						}
					}
				}
			}
		}

		for (int32 Index = 0; Index < PrototypePaths.Num(); ++Index)
		{
			if (!AssetsByPrototypeIndex.count(Index))
			{
				USD_LOG_WARNING(
					TEXT("Failed to find %s Mesh asset for PointInstancer prototype '%s'"),
					IsSkelMesh() ? TEXT("Skeletal") : TEXT("Static"),
					*UsdToUnreal::ConvertPath(PrototypePaths[Index])
				);

				AssetsByPrototypeIndex.insert({ Index, {} });
			}
		}

		return AssetsByPrototypeIndex;
	}

	void BuildAssemblyForPointInstancer(
		const UE::FUsdPrim& PointInstancerPrim, 
		const FTransform& Transform, 
		FBindingView Bindings)
	{
		using namespace UE::UsdNaniteAssemblyTranslator::Private;

		// Get masked prototype indices and instance transforms. Note that the input Bindings are 
		// assumed to already be masked. The bindings size must be a multiple of the number of
		// instances (depending on the element size of the originating primvars).
		const TArray<int32> ProtoIndices = GetPointInstancerProtoIndices(PointInstancerPrim, Context->Time);
		if (ProtoIndices.IsEmpty())
		{
			return;
		}
		const int32 NumInstances = ProtoIndices.Num();
		
		const TArray<FTransform> InstanceTransforms = GetPointInstancerTransforms(PointInstancerPrim, Transform, Context->Time);
		if (InstanceTransforms.Num() != NumInstances)
		{
			return;
		}

		// Get the instancer prototypes
		const TArray<UE::FSdfPath> PrototypePaths = GetPointInstancerPrototypePaths(PointInstancerPrim);
		if (PrototypePaths.IsEmpty())
		{
			return;
		}

		// For skeletal meshes only, bail if the input bindings are not the correct size for the instance count. 
		if (IsSkelMesh() && !Bindings.IsValidForInstanceCount(NumInstances))
		{
			USD_LOG_WARNING(
				TEXT("Skipping Nanite Assembly Skeletal Mesh PointInstancer '%s' with (%d) instances and invalid joint binding size (%d)."),
				*PointInstancerPrim.GetPrimPath().GetString(),
				NumInstances,
				Bindings.Num()
			);
			return;
		}

		const PrototypeAssetsTable AssetsByPrototypeIndex = CollectPointInstancerAssets(PointInstancerPrim, PrototypePaths);

		for (int32 Index = 0; Index < NumInstances; ++Index)
		{
			const int32 ProtoIndex = ProtoIndices[Index];

			if (AssetsByPrototypeIndex.count(ProtoIndex))
			{
				// NOTE: empty binding is expected for static meshes.
				TArrayView<const FNaniteAssemblyBoneInfluence> Binding = Bindings.GetViewForIndex(Index);

				for (const TWeakObjectPtr<UObject> Asset : AssetsByPrototypeIndex.at(ProtoIndex))
				{
					AddNodeAndBindMaterials(PointInstancerPrim, Asset.Get(), InstanceTransforms[Index], Binding);
				}
			}
		}
	}

	void RecursivelyBuildAssembly(
		const UE::FUsdPrim& Prim,
		const FTransform& ParentTransform,
		FBindingView Bindings)
	{
		using namespace UE::UsdNaniteAssemblyTranslator::Private;

		FTransform LocalTransform = ParentTransform;
		TArray<FNaniteAssemblyBoneInfluence> LocalBindings;
		bool bRecurseChildren = true;

		if (pxr::UsdGeomImageable Imageable = pxr::UsdGeomImageable(Prim))
		{
			if (!UsdUtils::IsVisible(Prim, Context->Time))
			{
				// ignore invisible prims
				return;
			}
		}

		if (IsNaniteAssemblyRoot(Prim))
		{
			// TODO: Nanite-Assemblies-USD: Support importing assemblies with references to assemblies.
			USD_LOG_WARNING(
				TEXT("Assembly prim '%s' cannot currently compose child assembly '%s'. Not supported yet."),
				*PrimPath.GetString(),
				*Prim.GetPrimPath().GetString()
			);

			return;
		}

		if (pxr::UsdGeomXformable Xformable = pxr::UsdGeomXformable(Prim))
		{
			bool bResetXformStack = false;
			UsdToUnreal::ConvertXformable(Prim.GetStage(), Xformable, LocalTransform, Context->Time, &bResetXformStack);
			if (!bResetXformStack)
			{
				LocalTransform *= ParentTransform;
			}
		}

		if (IsSkelMesh())
		{
			if (SkelRoot.Get().GetPrim() == Prim)
			{
				// Don't traverse down the "base" skeletal mesh of the assembly
				return;
			}

			int32 ElementSize = 1;
			LocalBindings = GetJointBindings(Prim, SkelJoints.Get(), SkelJointNames.Get(), Context->Time, ElementSize);
			if (LocalBindings.Num() > 0)
			{
				// Replace the current bindings for this prim and its descendants
				Bindings = { LocalBindings, ElementSize };
			}
		}
		
		if (Prim.IsA(TEXT("PointInstancer")))
		{
			return BuildAssemblyForPointInstancer(Prim, LocalTransform, Bindings);
		}

		TArray<UObject*, TInlineAllocator<1>> PrimAssets;
		FTopLevelAssetPath AssetPath = GetExternalAssetRef(Prim);
		if (AssetPath.IsValid())
		{
			UClass* AssetClass = IsSkelMesh() ? USkeletalMesh::StaticClass() : UStaticMesh::StaticClass();
			UObject* MeshObject = StaticLoadAsset(AssetClass, AssetPath);
			if (MeshObject)
			{
				PrimAssets.Add(MeshObject);
			}
			else
			{
				USD_LOG_ERROR(
					TEXT("Failed to load '%s' '%s' referenced by prim '%s'"),
					*AssetClass->GetName(),
					*AssetPath.ToString(),
					*Prim.GetPrimPath().GetString()
				);
			}
		}

		// Use the prim link cache to determine what meshes are associated with this node, if any, and create a part from them
		UE::FSdfPath PrototypePrimPath;

		PrototypePrimPath = UsdUtils::GetPrototypePrimPath(Prim);

		for (const TWeakObjectPtr<UObject>& AssetPtr : Context->PrimLinkCache->GetAllAssetsForPrim(PrototypePrimPath))
		{
			UObject* Asset = AssetPtr.Get();
			if (Asset == nullptr ||
				(IsSkelMesh() && !Asset->IsA<USkeletalMesh>()) ||
				(!IsSkelMesh() && !Asset->IsA<UStaticMesh>()))
			{
				continue;
			}
			PrimAssets.Add(Asset);
		}

		if (IsSkelMesh() && pxr::UsdPrim(Prim).IsA<pxr::UsdSkelRoot>())
		{
			// Special case: gather up skeletons because that's what the skeletal mesh is tied to in the prim link cache
			for (const UE::FUsdPrim& SkeletonPrim : UsdUtils::GetAllPrimsOfType(Prim, TEXT("UsdSkelSkeleton")))
			{
				for (USkeletalMesh* SkelMesh : Context->PrimLinkCache->GetAssetsForPrim<USkeletalMesh>(SkeletonPrim.GetPrimPath()))
				{
					PrimAssets.Add(SkelMesh);
				}
			}
			bRecurseChildren = false;
		}

		if (!PrimAssets.IsEmpty())
		{
			// Submitting nodes for Skeletal Meshes that have no bindings can currently lead to instability, so avoid for now. 
			if (IsSkelMesh() && Bindings.Num() == 0)
			{
				USD_LOG_WARNING(
					TEXT("Skipping Nanite Assembly Skeletal Mesh prim '%s' with zero joint bindings."),
					*Prim.GetPrimPath().GetString()
				);
			}
			else
			{
				for (UObject* Asset : PrimAssets)
				{
					AddNodeAndBindMaterials(Prim, Asset, LocalTransform, Bindings.GetView());
				}
			}
		}
		
		if (bRecurseChildren)
		{
			for (const UE::FUsdPrim& ChildPrim : Prim.GetFilteredChildren(true))
			{
				RecursivelyBuildAssembly(ChildPrim, LocalTransform, Bindings);
			}
		}
	}

	void SetupCommonTasks()
	{
		FScopedUnrealAllocs UnrealAllocs;

		// Build the Nanite Assembly data
		Do(ESchemaTranslationLaunchPolicy::Sync,
			[this]()->bool
			{
				for (const UE::FUsdPrim& ChildPrim : GetPrim().GetFilteredChildren(true))
				{
					RecursivelyBuildAssembly(ChildPrim, FTransform::Identity, {});
				}

				// bail if we didn't get any valid parts/nodes
				return Builder.GetData().IsValid();
			}
		);
	}

	void SetupStaticMeshTasks()
	{
		FScopedUnrealAllocs UnrealAllocs;

		// Create Nanite Assembly static mesh (main thread)
		Then(ESchemaTranslationLaunchPolicy::Sync,
			[this]() -> bool
			{			
				// Force load MeshBuilderModule so that it's ready for the async tasks
#if WITH_EDITOR
				FModuleManager::LoadModuleChecked<IMeshBuilderModule>(TEXT("MeshBuilder"));
#endif	// WITH_EDITOR

				UE::FUsdPrim Prim = GetPrim();

				// The Nanite Assembly structure is defined by the xforms of its child components in the USD stage, so
				// we can just use the prototype path as a hash to de-duplicate copied references
				FString Hash = PrimPath.GetString();
				const FString DesiredName = FPaths::GetBaseFilename(Hash);
				if (Prim.IsInstance())
				{
					Hash = Prim.GetPrototype().GetPrimPath().GetString();
				}
				else if (Prim.IsInstanceProxy())
				{
					Hash = Prim.GetPrimInPrototype().GetPrimPath().GetString();
				}

				bool bIsNew;
				StaticMesh = Context->UsdAssetCache->GetOrCreateCachedAsset<UStaticMesh>(
					Hash,
					DesiredName,
					Context->ObjectFlags,
					&bIsNew
				);
				
				if (StaticMesh)
				{
					StaticMesh->GetNaniteSettings().bEnabled = true;
					Builder.ApplyToStaticMesh(*StaticMesh);

					if (Context->PrimLinkCache)
					{
						Context->PrimLinkCache->LinkAssetToPrim(PrimPath, StaticMesh);
					}

					if (UUsdMeshAssetUserData* UserData = UsdUnreal::ObjectUtils::GetOrCreateAssetUserData<UUsdMeshAssetUserData>(StaticMesh))
					{
						UserData->PrimPaths.AddUnique(PrimPath.GetString());

						// TODO: Metadata? Material slot prims?
					}

					if (bIsNew)
					{
						// TODO: Nanite-Assemblies-USD: This isn't going to do the right thing for assemblies. Needs to be done
						// after caching render data.
						const bool bRebuildAll = true;
						StaticMesh->UpdateUVChannelData(bRebuildAll);
					}
				}

				return bIsNew;
			}
		);

		FBaseBuildStaticMeshTaskChain::SetupTasks();
	}

	void SetupSkelMeshTasks()
	{
		FScopedUnrealAllocs UnrealAllocs;

		// Create Nanite Assembly skeletal mesh (main thread)
		Then(ESchemaTranslationLaunchPolicy::Sync,
			[this]()->bool
			{
				UE::FUsdPrim Prim = GetPrim();

				// The Nanite Assembly structure is defined by the xforms of its child components in the USD stage, so
				// we can just use the prototype path as a hash to de-duplicate copied references
				FString Hash = PrimPath.GetString();
				const FString DesiredName = FPaths::GetBaseFilename(Hash);
				if (Prim.IsInstance())
				{
					Hash = Prim.GetPrototype().GetPrimPath().GetString();
				}
				else if (Prim.IsInstanceProxy())
				{
					Hash = UsdUtils::GetPrototypePrimPath(Prim).GetString();
				}

				bool bIsNew;
				SkeletalMesh = Context->UsdAssetCache->GetOrCreateCustomCachedAsset<USkeletalMesh>(
					Hash,
					DesiredName,
					Context->ObjectFlags,
					[this](UPackage* PackageOuter, FName SanitizedName, EObjectFlags Flags) -> UObject*
					{
						// Hack: create a copy of the "base skeletal mesh" asset that was already created
						// TODO: we should be creating the child assets internally instead of relying on this translator running as a
						// post-step
						UObject* NewObject = DuplicateObject<USkeletalMesh>(BaseSkeletalMesh, PackageOuter, SanitizedName);
						NewObject->SetFlags(Flags);
						return NewObject;
					},
					&bIsNew
				);
				
				if (SkeletalMesh)
				{
					SkeletalMesh->NaniteSettings.bEnabled = true;
					Builder.ApplyToSkeletalMesh(*SkeletalMesh);
					SkeletalMesh->RecacheNaniteAssemblyReferences();

					if (Context->PrimLinkCache)
					{
						Context->PrimLinkCache->LinkAssetToPrim(PrimPath, SkeletalMesh);
					}

					if (UUsdMeshAssetUserData* UserData = UsdUnreal::ObjectUtils::GetOrCreateAssetUserData<UUsdMeshAssetUserData>(SkeletalMesh))
					{
						UserData->PrimPaths.AddUnique(PrimPath.GetString());

						// TODO: Metadata? Material slot prims?
					}

					SkeletalMesh->Build();
				}

				return true;
			}
		);
	}
};

void FUsdNaniteAssemblyTranslator::CreateAssets()
{
	using namespace UE::UsdNaniteAssemblyTranslator::Private;

	// TODO: Stop relying on the prim link cache and initiate mesh asset creation by ourselves
	if (Context->PrimLinkCache == nullptr)
	{
		return;
	}
	
	UE::FUsdPrim Prim = GetPrim();
	ERootType RootType = GetNaniteAssemblyRootType(Prim);
	if (RootType == ERootType::None)
	{
		return;
	}
	
	// Manually translate skeletal meshes located in pointinstancer prototypes for now since they are not currently
	// recognized by the pointinstancer translator.
	const TArray<UE::FUsdPrim> PointInstancers = UsdUtils::GetAllPrimsOfType(Prim, TEXT("UsdGeomPointInstancer"));

	for (const UE::FUsdPrim& PointInstancer : PointInstancers)
	{
		const TArray<UE::FSdfPath> PrototypePaths = GetPointInstancerPrototypePaths(PointInstancer);

		for (const UE::FSdfPath& PrototypePath : PrototypePaths)
		{
			const UE::FUsdPrim PrototypePrim = Context->Stage.GetPrimAtPath(PrototypePath);
			const TArray<UE::FUsdPrim> SkeletonPrims = UsdUtils::GetAllPrimsOfType(PrototypePrim, TEXT("UsdSkelSkeleton"));

			for (const UE::FUsdPrim& SkeletonPrim : SkeletonPrims)
			{
				if (TSharedPtr<FUsdSchemaTranslator> SchemaTranslator = FUsdSchemaTranslatorRegistry::Get().CreateTranslatorForSchema(Context, UE::FUsdTyped(SkeletonPrim)))
				{
					SchemaTranslator->CreateAssets();
				}
			}
		}
	}

	Context->CompleteTasks();

	TSharedPtr<FUsdNaniteAssemblyCreateAssetsTaskChain> TaskChain;
	if (RootType == ERootType::SkeletalMesh)
	{
		pxr::UsdSkelSkeleton Skeleton;
		pxr::UsdSkelRoot SkelRoot;
		if (!ResolveNaniteAssemblyRootSkeleton(Prim, Skeleton, SkelRoot))
		{
			USD_LOG_INFO(
				TEXT("Failed to resolve %s prim for Nanite Assembly root %s"),
				Skeleton ? TEXT("SkelRoot") : TEXT("Skeleton"),
				*PrimPath.GetString()
			);
			return;
		}
		TaskChain = MakeShared<FUsdNaniteAssemblyCreateAssetsTaskChain>(Context, PrimPath, Skeleton, SkelRoot).ToSharedPtr();
	}
	else
	{
		TaskChain = MakeShared<FUsdNaniteAssemblyCreateAssetsTaskChain>(Context, PrimPath).ToSharedPtr();
	}

	Context->TranslatorTasks.Add(TaskChain.ToSharedRef());
}

#endif // USE_USD_SDK && WITH_EDITOR