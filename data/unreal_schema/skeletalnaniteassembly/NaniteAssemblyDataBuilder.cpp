// Copyright Epic Games, Inc. All Rights Reserved.

#include "NaniteAssemblyDataBuilder.h"

#if WITH_EDITOR

#include "Engine/StaticMesh.h"
#include "Materials/Material.h"
#include "StaticMeshAttributes.h"
#include "NaniteDefinitions.h"
#include "EngineLogs.h"
#include "Rendering/SkeletalMeshModel.h"

static void AddMaterialRemap(TArray<int32>& RemapTable, int32 LocalMaterialIndex, int32 MaterialIndex)
{
	const int32 NumRemapElements = RemapTable.Num();
	if (LocalMaterialIndex >= NumRemapElements)
	{
		RemapTable.SetNumUninitialized(LocalMaterialIndex + 1);
		for (int32 i = NumRemapElements; i < LocalMaterialIndex; ++i)
		{
			RemapTable[i] = INDEX_NONE;
		}
	}
	RemapTable[LocalMaterialIndex] = MaterialIndex;
}

void FNaniteAssemblyDataBuilder::Reset()
{
	AssemblyData = FNaniteAssemblyData();
	MaterialSlotGroups.SetNum(1);
	MaterialSlotGroups[0].Reset();
	PartMaterialSlotGroups.Reset();
	BaseMeshMaterialRemap.Reset();
}

int32 FNaniteAssemblyDataBuilder::AddPart(const FSoftObjectPath& MeshPath, int32 MaterialSlotGroup)
{
	int32 NewPartIndex = AssemblyData.Parts.Num();
	FNaniteAssemblyPart& Part = AssemblyData.Parts.Emplace_GetRef();
	Part.MeshObjectPath = MeshPath;

	PartMaterialSlotGroups.Add(MaterialSlotGroup);
	check(PartMaterialSlotGroups.Num() == AssemblyData.Parts.Num());

	return NewPartIndex;
}

int32 FNaniteAssemblyDataBuilder::FindPart(const FSoftObjectPath& MeshPath)
{
	return AssemblyData.Parts.IndexOfByPredicate(
		[&MeshPath](const FNaniteAssemblyPart& Part)
		{
			return Part.MeshObjectPath == MeshPath;
		}
	);
}

int32 FNaniteAssemblyDataBuilder::FindOrAddPart(const FSoftObjectPath& MeshPath, int32 MaterialSlotGroup, bool& bOutNewPart)
{
	for (int32 i = 0; i < AssemblyData.Parts.Num(); ++i)
	{
		check(PartMaterialSlotGroups.IsValidIndex(i));
		if (AssemblyData.Parts[i].MeshObjectPath == MeshPath &&
			PartMaterialSlotGroups[i] == MaterialSlotGroup)
		{
			bOutNewPart = false;
			return i;
		}
	}
	
	bOutNewPart = true;
	return AddPart(MeshPath, MaterialSlotGroup);
}

int32 FNaniteAssemblyDataBuilder::AddNode(
	int32 PartIndex, 
	const FTransform3f& Transform, 
	ENaniteAssemblyNodeTransformSpace TransformSpace,
	TArrayView<const FNaniteAssemblyBoneInfluence> AttachWeights)
{
	check(AssemblyData.Parts.IsValidIndex(PartIndex));

	int32 NewNodeIndex = AssemblyData.Nodes.Num();
	FNaniteAssemblyNode& Node = AssemblyData.Nodes.Emplace_GetRef();
	Node.PartIndex = PartIndex;
	Node.Transform = Transform;
	Node.TransformSpace = TransformSpace;
	Node.BoneInfluences = AttachWeights;

	return NewNodeIndex;
}

void FNaniteAssemblyDataBuilder::SetNumMaterialSlots(int32 MaterialSlotGroup, int32 NumMaterialSlots)
{
	FMaterialSlotGroup& MaterialSlots = MaterialSlotGroups[MaterialSlotGroup];
	int32 PrevNum = MaterialSlots.Num();
	MaterialSlots.SetNum(NumMaterialSlots);

	if (PrevNum > NumMaterialSlots)
	{
		// Invalidate any remappings that may now be invalid
		for (int32 PartIndex = 0; PartIndex < PartMaterialSlotGroups.Num(); ++PartIndex)
		{
			if (PartMaterialSlotGroups[PartIndex] == MaterialSlotGroup)
			{
				FNaniteAssemblyPart& Part = AssemblyData.Parts[PartIndex];
				for (int32& MaterialIndex : Part.MaterialRemap)
				{
					if (MaterialIndex >= NumMaterialSlots)
					{
						MaterialIndex = INDEX_NONE;
					}
				}
			}
		}

		if (MaterialSlotGroup == 0)
		{
			for (int32& MaterialIndex : BaseMeshMaterialRemap)
			{
				if (MaterialIndex >= NumMaterialSlots)
				{
					MaterialIndex = INDEX_NONE;
				}
			}
		}
	}
}

void FNaniteAssemblyDataBuilder::RemapPartMaterial(int32 PartIndex, int32 LocalMaterialIndex, int32 MaterialIndex)
{
	check(AssemblyData.Parts.IsValidIndex(PartIndex));
	check(PartMaterialSlotGroups.IsValidIndex(PartIndex));
	check(LocalMaterialIndex >= 0);
	check(MaterialSlotGroups.IsValidIndex(PartMaterialSlotGroups[PartIndex]));
	check(MaterialSlotGroups[PartMaterialSlotGroups[PartIndex]].IsValidIndex(MaterialIndex));

	AddMaterialRemap(AssemblyData.Parts[PartIndex].MaterialRemap, LocalMaterialIndex, MaterialIndex);
}

void FNaniteAssemblyDataBuilder::RemapBaseMeshMaterial(int32 LocalMaterialIndex, int32 MaterialIndex)
{
	check(LocalMaterialIndex >= 0);
	check(MaterialSlotGroups[0].IsValidIndex(MaterialIndex));

	AddMaterialRemap(BaseMeshMaterialRemap, LocalMaterialIndex, MaterialIndex);
}

bool FNaniteAssemblyDataBuilder::ApplyToStaticMesh(
	UStaticMesh& TargetMesh,
	const UStaticMesh::FCommitMeshDescriptionParams& CommitParams
)
{
	if (!AssemblyData.IsValid())
	{
		// No assembly parts, don't change anything
		return false;
	}

	// Get or create the mesh description
	FMeshDescription* MeshDescription = nullptr;
	if (TargetMesh.IsMeshDescriptionValid(0))
	{
		// This was already a valid base mesh
		MeshDescription = TargetMesh.GetSourceModel(0).GetOrCacheMeshDescription();
	}
	else
	{
		if (TargetMesh.GetNumSourceModels() == 0)
		{
			TargetMesh.SetNumSourceModels(1);
		}

		MeshDescription = TargetMesh.GetSourceModel(0).CreateMeshDescription();
		
		FStaticMeshAttributes Attributes(*MeshDescription);
		Attributes.Register();
	}

	FNaniteAssemblyData& TargetAssemblyData = TargetMesh.GetNaniteSettings().NaniteAssemblyData;
	TargetAssemblyData = AssemblyData;

	{
		// Determine the final material slots
		TArray<FStaticMaterial>& StaticMaterials = TargetMesh.GetStaticMaterials();
		TArray<FMaterialSlot> MaterialSlots = FinalizeMaterialSlots(
			StaticMaterials,
			TargetAssemblyData,
			*MeshDescription
		);

		StaticMaterials.Empty(MaterialSlots.Num());
		for (const auto& Slot : MaterialSlots)
		{
			StaticMaterials.Emplace(Slot.Material.Get(), Slot.Name, Slot.Name);
		}
	}

	// Check to remap the base mesh's sections and validate their material index against the new material list
	const int32 NumMaterialSlots = TargetMesh.GetStaticMaterials().Num();
	FMeshSectionInfoMap& SectionInfoMap = TargetMesh.GetSectionInfoMap();
	for (auto& [Key, SectionInfo] : SectionInfoMap.Map)
	{
		SectionInfo.MaterialIndex = RemapBaseMaterialIndex(SectionInfo.MaterialIndex, NumMaterialSlots);
	}

	// Add mesh sections for unrepresented materials to LOD 0
	const int32 PrevNumSectionsLOD0 = SectionInfoMap.GetSectionNumber(0);
	const auto FindSectionWithMaterial = [&SectionInfoMap, PrevNumSectionsLOD0] (int32 MaterialIndex)
	{
		for (int32 SectionIndex = 0; SectionIndex < PrevNumSectionsLOD0; ++SectionIndex)
		{
			if (SectionInfoMap.Get(0, SectionIndex).MaterialIndex == MaterialIndex)
			{
				return true;
			}
		}

		return false;
	};
	int32 NextSectionIndex = PrevNumSectionsLOD0;
	for (int32 i = 0; i < NumMaterialSlots; ++i)
	{
		if (!FindSectionWithMaterial(i))
		{
			SectionInfoMap.Set(0, NextSectionIndex, FMeshSectionInfo(i));
			++NextSectionIndex;
		}
	}

	// Commit the mesh description
	TargetMesh.CommitMeshDescription(0, CommitParams);

	return true;
}

bool FNaniteAssemblyDataBuilder::ApplyToSkeletalMesh(
	USkeletalMesh& TargetMesh,
	const USkeletalMesh::FCommitMeshDescriptionParams& CommitParams
)
{
	if (!AssemblyData.IsValid())
	{
		// No assembly parts, don't change anything
		return false;
	}

	FMeshDescription* MeshDescription = (TargetMesh.GetNumSourceModels() == 0) ?
		nullptr : TargetMesh.GetSourceModel(0).GetMeshDescription();
	if (MeshDescription == nullptr)
	{
		// Skeletal mesh assemblies must start with a valid base mesh and skeleton
		return false;
	}

	FNaniteAssemblyData& TargetAssemblyData = TargetMesh.NaniteSettings.NaniteAssemblyData;
	TargetAssemblyData = AssemblyData;

	{
		TArray<FMaterialSlot> MaterialSlots = FinalizeMaterialSlots(
			TargetMesh.GetMaterials(),
			TargetAssemblyData,
			*MeshDescription
		);

		TArray<FSkeletalMaterial> SkeletalMaterials;
		SkeletalMaterials.Reserve(MaterialSlots.Num());
		for (const auto& Slot : MaterialSlots)
		{
			SkeletalMaterials.Emplace(Slot.Material.Get(), Slot.Name, Slot.Name);
		}
		TargetMesh.SetMaterials(SkeletalMaterials);
	}

	const int32 NumMaterialSlots = TargetMesh.GetMaterials().Num();
	for (int32 LODIndex = 0; LODIndex < TargetMesh.GetLODNum(); ++LODIndex)
	{
		FSkeletalMeshLODModel& LODModel = TargetMesh.GetImportedModel()->LODModels[LODIndex];
		for (FSkelMeshSection& Section : LODModel.Sections)
		{
			Section.MaterialIndex = RemapBaseMaterialIndex(Section.MaterialIndex, NumMaterialSlots);
		}

		if (FSkeletalMeshLODInfo* LOD = TargetMesh.GetLODInfo(LODIndex))
		{
			for (int32& RemapIndex : LOD->LODMaterialMap)
			{
				if (RemapIndex != INDEX_NONE)
				{
					RemapIndex = RemapBaseMaterialIndex(RemapIndex, NumMaterialSlots);
				}
			}
		}
	}
	
	if (TargetMesh.GetLODNum() > 0)
	{
		// Fix up LOD0's material map and add empty sections for material slots that are unrepresented by existing sections
		FSkeletalMeshLODModel& LOD0Model = TargetMesh.GetImportedModel()->LODModels[0];
		FSkeletalMeshLODInfo* LOD0Info = TargetMesh.GetLODInfo(0);
		for (int32 i = 0; i < NumMaterialSlots; ++i)
		{			
			// Add an empty skel mesh section for any unrepresented material slots
			if (!LOD0Model.Sections.FindByPredicate([i] (const auto& S) { return S.MaterialIndex == i; }))
			{
				LOD0Model.Sections.AddDefaulted_GetRef().MaterialIndex = i;
				if (!LOD0Info->LODMaterialMap.IsEmpty())
				{
					LOD0Info->LODMaterialMap.Add(i);
				}
			}
		}
	}

	// Commit the mesh description
	TargetMesh.CommitMeshDescription(0, CommitParams);

	return true;
}

int32 FNaniteAssemblyDataBuilder::RemapBaseMaterialIndex(int32 MaterialIndex, int32 NumMaterialSlots)
{
	if (!BaseMeshMaterialRemap.IsEmpty()) // Empty means don't remap
	{
		// remap the material index
		MaterialIndex = BaseMeshMaterialRemap.IsValidIndex(MaterialIndex) ?
			BaseMeshMaterialRemap[MaterialIndex] : 0;
	}

	if (MaterialIndex < 0 || MaterialIndex >= NumMaterialSlots)
	{
		// Ensure valid material index
		MaterialIndex = 0;
	}

	return MaterialIndex;
}

template <typename TMaterial>
TArray<FNaniteAssemblyDataBuilder::FMaterialSlot> FNaniteAssemblyDataBuilder::FinalizeMaterialSlots(
	const TArray<TMaterial>& PreviousMaterials,
	FNaniteAssemblyData& InOutData,
	FMeshDescription& InOutMeshDescription
)
{
	TArray<FMaterialSlot> MaterialSlots;
	FStaticMeshAttributes Attributes(InOutMeshDescription);
	TPolygonGroupAttributesRef<FName> MaterialSlotNamesAttr = Attributes.GetPolygonGroupMaterialSlotNames();

	{
		TArray<int32> MaterialSlotGroupOffsets;
		MaterialSlotGroupOffsets.Reserve(MaterialSlotGroups.Num());
		for (auto& MaterialSlotGroup : MaterialSlotGroups)
		{
			MaterialSlotGroupOffsets.Add(MaterialSlots.Num());
			MaterialSlots.Append(MaterialSlotGroup);
		}

		// Offset the remap tables of every part that was not using the default material slot group
		for (int32 PartIndex = 0; PartIndex < PartMaterialSlotGroups.Num(); ++PartIndex)
		{
			int32 PartSlotGroup = PartMaterialSlotGroups[PartIndex];
			if (PartSlotGroup != 0)
			{
				int32 Offset = MaterialSlotGroupOffsets[PartSlotGroup];
				for (int32& RemapIndex : InOutData.Parts[PartIndex].MaterialRemap)
				{
					RemapIndex += Offset;
				}
			}
		}

		// Ensure we have at least one material slot
		if (MaterialSlots.IsEmpty())
			MaterialSlots.AddDefaulted();
	}

	// Determine final slot names, guaranteeing uniqueness
	for (int32 SlotIndex = 1; SlotIndex < MaterialSlots.Num(); ++SlotIndex)
	{
		FMaterialSlot& Slot = MaterialSlots[SlotIndex];
		int32 MaxNumber = Slot.Name.GetNumber();
		bool bChangeNumber = false;
		for (int32 i = 0; i < SlotIndex; ++i)
		{
			const FName Existing = MaterialSlots[i].Name;
			if (Slot.Name.GetComparisonIndex() == Existing.GetComparisonIndex())
			{
				bChangeNumber |= Existing == Slot.Name;
				MaxNumber = FMath::Max(MaxNumber, Existing.GetNumber());
			}
		}

		if (bChangeNumber)
		{
			Slot.Name.SetNumber(MaxNumber + 1);
		}
	}

	// Rename all existing polygon group import names
	const int32 NumMaterialSlots = MaterialSlots.Num();
	TBitArray<> HandledSlots(false, MaterialSlots.Num());
	for (FPolygonGroupID PolyGroupID : InOutMeshDescription.PolygonGroups().GetElementIDs())
	{
		const FName PreviousName = MaterialSlotNamesAttr.Get(PolyGroupID);
		int32 SlotIndex = PreviousMaterials.IndexOfByPredicate(
			[PreviousName] (const auto& PreviousMaterial)
			{
				return PreviousMaterial.ImportedMaterialSlotName == PreviousName;
			}
		);
		if (SlotIndex != INDEX_NONE)
		{
			SlotIndex = RemapBaseMaterialIndex(SlotIndex, NumMaterialSlots);
			MaterialSlotNamesAttr.Set(PolyGroupID, MaterialSlots[SlotIndex].Name);
			HandledSlots[SlotIndex] = true;
		}
	}

	// create a polygon group with a degenerate triangle for those that are unrepresented by geometry in the base mesh description
	// as a placeholder, as it is expected that their geometry will come from part meshes
	for (int32 SlotIndex = 0; SlotIndex < NumMaterialSlots; ++SlotIndex)
	{
		if (!HandledSlots[SlotIndex])
		{
			InOutMeshDescription.ReserveNewVertices(3);
			InOutMeshDescription.ReserveNewVertexInstances(3);
			InOutMeshDescription.ReserveNewTriangles(1);
			InOutMeshDescription.ReserveNewPolygonGroups(1);

			const FPolygonGroupID PolyGroup = InOutMeshDescription.CreatePolygonGroup();
			MaterialSlotNamesAttr.Set(PolyGroup, MaterialSlots[SlotIndex].Name);

			const FVertexID Verts[] =
			{
				InOutMeshDescription.CreateVertex(),
				InOutMeshDescription.CreateVertex(),
				InOutMeshDescription.CreateVertex()
			};
			const FVertexInstanceID VertInstances[] =
			{
				InOutMeshDescription.CreateVertexInstance(Verts[0]),
				InOutMeshDescription.CreateVertexInstance(Verts[1]),
				InOutMeshDescription.CreateVertexInstance(Verts[2])
			};
			const FTriangleID Tri = InOutMeshDescription.CreateTriangle(PolyGroup, MakeArrayView(VertInstances, 3));

			TVertexAttributesRef<FVector3f> VertexPositions = Attributes.GetVertexPositions();
			VertexPositions.Set(Verts[0], FVector3f::Zero());
			VertexPositions.Set(Verts[1], FVector3f::Zero());
			VertexPositions.Set(Verts[2], FVector3f::Zero());
		}
	}

	return MaterialSlots;
}

#endif // WITH_EDITOR