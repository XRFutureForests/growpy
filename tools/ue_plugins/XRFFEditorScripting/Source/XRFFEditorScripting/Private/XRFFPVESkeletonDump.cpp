#include "XRFFPVESkeletonDump.h"

#include "DataTypes/PVData.h"
#include "GeometryCollection/ManagedArrayCollection.h"
#include "Graph/PCGStackContext.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "PCGData.h"
#include "PCGDefaultExecutionSource.h"
#include "PCGEdge.h"
#include "PCGGraph.h"
#include "PCGGraphExecutionInspection.h"
#include "PCGNode.h"
#include "PCGPin.h"
#include "PCGSettings.h"
#include "ProceduralVegetation.h"
#include "Subsystems/IPCGBaseSubsystem.h"
#include "UObject/StrongObjectPtr.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogXRFFPVEDump, Log, All);

namespace XRFFPVEDump
{
	// PVE collection names (ProceduralVegetation Public/Facades/PVAttributesNames.h, UE 5.8)
	static const FName PointGroup(TEXT("Points"));
	static const FName BranchGroup(TEXT("Primitives"));
	static const FName PositionAttr(TEXT("Position"));
	static const FName ScaleAttr(TEXT("Scale"));
	static const FName BranchPointsAttr(TEXT("Points"));
	static const FName BranchNumberAttr(TEXT("branchNumber"));
	static const FName BranchParentNumberAttr(TEXT("branchParentNumber"));

	// runs stay alive until released; Python holds only the raw object
	static TArray<TStrongObjectPtr<UPCGDefaultExecutionSource>> Runs;

	static UPCGDefaultExecutionSource* AsRun(UObject* Run)
	{
		UPCGDefaultExecutionSource* Source = Cast<UPCGDefaultExecutionSource>(Run);
		return Source && Runs.ContainsByPredicate([Source](const TStrongObjectPtr<UPCGDefaultExecutionSource>& P) { return P.Get() == Source; }) ? Source : nullptr;
	}

	static const UPVData* PinData(UPCGDefaultExecutionSource& Source, const UPCGPin& Pin)
	{
		FPCGStack Stack;
		Stack.PushFrame(&Source);
		Stack.PushFrame(Source.GetGraph());
		Stack.PushFrame(Pin.Node);
		Stack.PushFrame(&Pin);
		const UPVData* Out = nullptr;
		Source.GetExecutionState().GetInspection().InspectData(Stack, [&Out](const FPCGDataCollection& Collection)
		{
			const FPCGTaggedData* Tagged = Collection.TaggedData.GetData();
			if (Tagged != nullptr)
			{
				Out = Cast<UPVData>(Tagged->Data);
			}
		});
		return Out;
	}

	static FString SettingsClass(const UPCGNode* Node)
	{
		const UPCGSettings* Settings = Node ? Node->GetSettings() : nullptr;
		return Settings ? Settings->GetClass()->GetName() : FString(TEXT("?"));
	}

	static bool Matches(const UPCGNode* Node, const FString& Wanted)
	{
		return Node->GetName() == Wanted || SettingsClass(Node) == Wanted
			|| (Node->HasAuthoredTitle() && Node->GetAuthoredTitleName().ToString() == Wanted);
	}

	static FString Num(double V)
	{
		return FString::Printf(TEXT("%.9g"), V);  // float32 values round-trip exactly; same data -> same bytes
	}
}

UObject* UXRFFPVESkeletonDump::StartPVERun(UObject* ProceduralVegetationOrGraph)
{
	UPCGGraphInterface* Graph = Cast<UPCGGraphInterface>(ProceduralVegetationOrGraph);
	if (UProceduralVegetation* PV = Cast<UProceduralVegetation>(ProceduralVegetationOrGraph))  // non-const: GetGraph() const returns a const graph
	{
		Graph = PV->GetGraph();
	}
	if (!Graph)
	{
		UE_LOG(LogXRFFPVEDump, Error, TEXT("StartPVERun: %s is neither a ProceduralVegetation asset nor a PCG graph"),
			*GetNameSafe(ProceduralVegetationOrGraph));
		return nullptr;
	}
	FPCGDefaultExecutionSourceParams Params;
	Params.GraphInterface = Graph;
	UPCGDefaultExecutionSource* Source = IPCGBaseSubsystem::CreateExecutionSource<UPCGDefaultExecutionSource>(Params);
	if (!Source)
	{
		UE_LOG(LogXRFFPVEDump, Error, TEXT("StartPVERun: no execution source for %s"), *GetNameSafe(Graph));
		return nullptr;
	}
	Source->GetExecutionState().GetInspection().EnableInspection();
	XRFFPVEDump::Runs.Emplace(Source);
	Source->Generate();
	return Source;
}

bool UXRFFPVESkeletonDump::IsPVERunGenerating(UObject* Run)
{
	UPCGDefaultExecutionSource* Source = XRFFPVEDump::AsRun(Run);
	return Source && Source->GetExecutionState().IsGenerating();
}

TArray<FString> UXRFFPVESkeletonDump::ListPVERunData(UObject* Run)
{
	TArray<FString> Lines;
	UPCGDefaultExecutionSource* Source = XRFFPVEDump::AsRun(Run);
	if (!Source || Source->GetExecutionState().IsGenerating() || !Source->GetGraph())
	{
		return Lines;
	}
	for (const UPCGNode* Node : Source->GetGraph()->GetNodes())
	{
		for (const TObjectPtr<UPCGPin>& Pin : Node->GetOutputPins())
		{
			if (const UPVData* Data = XRFFPVEDump::PinData(*Source, *Pin))
			{
				const FManagedArrayCollection& C = Data->GetCollection();
				Lines.Add(FString::Printf(TEXT("%s | %s | %s | points %d | branches %d"), *Node->GetName(),
					*XRFFPVEDump::SettingsClass(Node), *Pin->Properties.Label.ToString(),
					C.HasGroup(XRFFPVEDump::PointGroup) ? C.NumElements(XRFFPVEDump::PointGroup) : -1,
					C.HasGroup(XRFFPVEDump::BranchGroup) ? C.NumElements(XRFFPVEDump::BranchGroup) : -1));
			}
		}
	}
	return Lines;
}

FString UXRFFPVESkeletonDump::DumpPVESkeleton(UObject* Run, const FString& Node, const FString& OutPath, const FString& ExtraMetadata)
{
	using namespace XRFFPVEDump;
	UPCGDefaultExecutionSource* Source = AsRun(Run);
	if (!Source)
	{
		return TEXT("not a run from start_pve_run (or already released)");
	}
	if (Source->GetExecutionState().IsGenerating())
	{
		return TEXT("still generating");
	}
	const UPCGGraph* Graph = Source->GetGraph();
	if (!Graph)
	{
		return TEXT("run has no graph");
	}

	// pick the output pin: the named node's first PVE output, or the pin feeding the first mesh builder
	const UPCGPin* Pin = nullptr;
	for (const UPCGNode* N : Graph->GetNodes())
	{
		if (Node.IsEmpty())
		{
			if (SettingsClass(N).Contains(TEXT("MeshBuilder")) && N->GetInputPins().Num() > 0 && N->GetInputPins()[0]->Edges.Num() > 0)
			{
				const UPCGPin* In = N->GetInputPins()[0];
				Pin = In->Edges[0]->GetOtherPin(In);
				break;
			}
		}
		else if (Matches(N, Node))
		{
			for (const TObjectPtr<UPCGPin>& P : N->GetOutputPins())
			{
				if (PinData(*Source, *P))
				{
					Pin = P;
					break;
				}
			}
			break;
		}
	}
	if (!Pin)
	{
		return Node.IsEmpty() ? TEXT("no mesh builder with a connected input") : FString::Printf(TEXT("node %s not found or has no PVE output"), *Node);
	}
	const UPVData* Data = PinData(*Source, *Pin);
	if (!Data)
	{
		return FString::Printf(TEXT("no inspected PVE data on %s (inspection off or node not executed)"), *Pin->Node->GetName());
	}

	const FManagedArrayCollection& C = Data->GetCollection();
	const TManagedArray<FVector3f>* Pos = C.FindAttributeTyped<FVector3f>(PositionAttr, PointGroup);
	const TManagedArray<float>* Scale = C.FindAttributeTyped<float>(ScaleAttr, PointGroup);
	const TManagedArray<TArray<int32>>* BPoints = C.FindAttributeTyped<TArray<int32>>(BranchPointsAttr, BranchGroup);
	const TManagedArray<int32>* BNum = C.FindAttributeTyped<int32>(BranchNumberAttr, BranchGroup);
	const TManagedArray<int32>* BPar = C.FindAttributeTyped<int32>(BranchParentNumberAttr, BranchGroup);
	if (!Pos || !Scale || !BPoints || !BNum || !BPar)
	{
		return FString::Printf(TEXT("collection lacks %s%s%s%s%s"), Pos ? TEXT("") : TEXT("Points.Position "),
			Scale ? TEXT("") : TEXT("Points.Scale "), BPoints ? TEXT("") : TEXT("Primitives.Points "),
			BNum ? TEXT("") : TEXT("Primitives.branchNumber "), BPar ? TEXT("") : TEXT("Primitives.branchParentNumber"));
	}
	const int32 NP = Pos->Num();
	const int32 NB = BPoints->Num();

	// parents first: breadth-first from the single root, children in collection order
	TMap<int32, int32> IndexOfNumber;
	for (int32 B = 0; B < NB; ++B)
	{
		if (IndexOfNumber.Contains((*BNum)[B]))
		{
			return FString::Printf(TEXT("duplicate branchNumber %d"), (*BNum)[B]);
		}
		IndexOfNumber.Add((*BNum)[B], B);
	}
	TArray<TArray<int32>> Children;
	Children.SetNum(NB);
	TArray<int32> Roots;
	for (int32 B = 0; B < NB; ++B)
	{
		const int32* Parent = IndexOfNumber.Find((*BPar)[B]);
		if (Parent && *Parent != B)
		{
			Children[*Parent].Add(B);
		}
		else
		{
			Roots.Add(B);
		}
	}
	if (Roots.Num() != 1)
	{
		return FString::Printf(TEXT("%d root branches (one plant per dump)"), Roots.Num());
	}
	TArray<int32> Order = {Roots[0]};
	TArray<int32> Depth;
	Depth.Init(-1, NB);
	Depth[Roots[0]] = 0;
	for (int32 I = 0; I < Order.Num(); ++I)
	{
		for (const int32 Child : Children[Order[I]])
		{
			Depth[Child] = Depth[Order[I]] + 1;
			Order.Add(Child);
		}
	}
	if (Order.Num() != NB)
	{
		return FString::Printf(TEXT("%d of %d branches not reachable from the root"), NB - Order.Num(), NB);
	}
	for (const int32 B : Order)
	{
		for (const int32 P : (*BPoints)[B])
		{
			if (P < 0 || P >= NP)
			{
				return FString::Printf(TEXT("branch %d points at %d, outside %d points"), (*BNum)[B], P, NP);
			}
		}
	}

	TArray<FString> Parts;
	Parts.Reserve(NP);
	for (int32 I = 0; I < NP; ++I)
	{
		const FVector3f& P = (*Pos)[I];  // PVE Z-up cm -> growpy y-up m
		Parts.Add(FString::Printf(TEXT("[%s,%s,%s]"), *Num(P.X / 100.0), *Num(P.Z / 100.0), *Num(P.Y / 100.0)));
	}
	FString Out = TEXT("{\"points\":{\"positions\":[") + FString::Join(Parts, TEXT(",")) + TEXT("],\"attributes\":{");
	Parts.Reset();
	for (int32 I = 0; I < NP; ++I)
	{
		Parts.Add(TEXT("[") + Num((*Scale)[I] / 100.0) + TEXT("]"));
	}
	Out += TEXT("\"budLateralMeristem\":{\"isArray\":true,\"size\":1,\"type\":\"float\",\"values\":[") + FString::Join(Parts, TEXT(",")) + TEXT("]}}},");

	TArray<FString> Lines, Numbers, ParentNumbers, Orders;
	for (const int32 B : Order)
	{
		TArray<FString> Idx;
		for (const int32 P : (*BPoints)[B])
		{
			Idx.Add(FString::FromInt(P));
		}
		Lines.Add(TEXT("[") + FString::Join(Idx, TEXT(",")) + TEXT("]"));
		Numbers.Add(FString::FromInt((*BNum)[B]));
		ParentNumbers.Add(FString::FromInt(B == Roots[0] ? -1 : (*BPar)[B]));
		Orders.Add(FString::FromInt(Depth[B]));
	}
	auto IntAttr = [](const TCHAR* Name, const TArray<FString>& V)
	{
		return FString::Printf(TEXT("\"%s\":{\"isArray\":false,\"size\":1,\"type\":\"int\",\"values\":["), Name) + FString::Join(V, TEXT(",")) + TEXT("]}");
	};
	Out += TEXT("\"primitives\":{\"points\":[") + FString::Join(Lines, TEXT(",")) + TEXT("],\"attributes\":{")
		+ IntAttr(TEXT("branchNumber"), Numbers) + TEXT(",") + IntAttr(TEXT("branchParentNumber"), ParentNumbers) + TEXT(",")
		+ IntAttr(TEXT("branchOrder"), Orders) + TEXT("}},");

	const FString Asset = Graph->GetOuter() ? Graph->GetOuter()->GetPathName() : Graph->GetPathName();
	Out += FString::Printf(TEXT("\"metadata\":{\"source\":\"pve_grower_dump\",\"asset\":\"%s\",\"node\":\"%s\",\"node_class\":\"%s\",")
		TEXT("\"units\":\"m\",\"up\":\"y\",\"radius\":\"PVE point Scale / 100, before the mesh builder\",\"engine\":\"%s\",")
		TEXT("\"points\":%d,\"branches\":%d%s%s}}\n"),
		*Asset.ReplaceCharWithEscapedChar(), *Pin->Node->GetName(), *SettingsClass(Pin->Node),
		*FEngineVersion::Current().ToString(), NP, NB, ExtraMetadata.IsEmpty() ? TEXT("") : TEXT(","), *ExtraMetadata);

	if (!FFileHelper::SaveStringToFile(Out, *OutPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
	{
		return FString::Printf(TEXT("cannot write %s"), *OutPath);
	}
	UE_LOG(LogXRFFPVEDump, Display, TEXT("PVE_DUMP %s <- %s: %d points, %d branches"), *OutPath, *Pin->Node->GetName(), NP, NB);
	return FString();
}

FString UXRFFPVESkeletonDump::MarkCrownBaseRemoval(UObject* Run, const FString& Node, float CrownBaseM, float MaxShare)
{
	return MarkCrownTrim(Run, Node, CrownBaseM, MaxShare, 0.0f);
}

FString UXRFFPVESkeletonDump::MarkCrownTrim(UObject* Run, const FString& Node, float CrownBaseM, float MaxShare, float ReachM)
{
	using namespace XRFFPVEDump;
	UPCGDefaultExecutionSource* Source = AsRun(Run);
	if (!Source || Source->GetExecutionState().IsGenerating() || !Source->GetGraph())
	{
		return TEXT("ERROR: not a finished run from start_pve_run");
	}
	// the Manual Edit node; its settings class is not exported, so it is found by class name and written by reflection
	UPCGNode* Target = nullptr;
	for (UPCGNode* N : Source->GetGraph()->GetNodes())
	{
		if (SettingsClass(N) == TEXT("PVManualEditSettings") && (Node.IsEmpty() || Matches(N, Node)))
		{
			Target = N;
			break;
		}
	}
	if (!Target || Target->GetInputPins().Num() == 0 || Target->GetInputPins()[0]->Edges.Num() == 0)
	{
		return FString::Printf(TEXT("ERROR: no connected Manual Edit node %s"), *Node);
	}
	const UPCGPin* In = Target->GetInputPins()[0];
	const UPVData* Data = PinData(*Source, *In->Edges[0]->GetOtherPin(In));
	if (!Data)
	{
		return TEXT("ERROR: no inspected data on the Manual Edit node's input");
	}
	const FManagedArrayCollection& C = Data->GetCollection();
	const TManagedArray<FVector3f>* Pos = C.FindAttributeTyped<FVector3f>(PositionAttr, PointGroup);
	const TManagedArray<int32>* Bud = C.FindAttributeTyped<int32>(FName(TEXT("budNumber")), PointGroup);
	const TManagedArray<TArray<int32>>* BPoints = C.FindAttributeTyped<TArray<int32>>(BranchPointsAttr, BranchGroup);
	const TManagedArray<int32>* BNum = C.FindAttributeTyped<int32>(BranchNumberAttr, BranchGroup);
	const TManagedArray<int32>* BPar = C.FindAttributeTyped<int32>(BranchParentNumberAttr, BranchGroup);
	if (!Pos || !Bud || !BPoints || !BNum || !BPar)
	{
		return TEXT("ERROR: input collection lacks Position / budNumber / branch attributes");
	}
	const int32 NB = BPoints->Num();
	TMap<int32, int32> IndexOfNumber;
	for (int32 B = 0; B < NB; ++B)
	{
		IndexOfNumber.Add((*BNum)[B], B);
	}
	int32 Root = INDEX_NONE;
	TArray<TArray<int32>> Children;
	Children.SetNum(NB);
	for (int32 B = 0; B < NB; ++B)
	{
		const int32* P = IndexOfNumber.Find((*BPar)[B]);
		if (P && *P != B)
		{
			Children[*P].Add(B);
		}
		else if (Root == INDEX_NONE)
		{
			Root = B;
		}
		else
		{
			return TEXT("ERROR: more than one root branch");
		}
	}
	if (Root == INDEX_NONE || (*BPoints)[Root].Num() == 0)
	{
		return TEXT("ERROR: no trunk");
	}
	float BaseZ = TNumericLimits<float>::Max();
	for (const int32 P : (*BPoints)[Root])
	{
		BaseZ = FMath::Min(BaseZ, (*Pos)[P].Z);
	}
	// first-order limbs by attachment height (their first point, shared with the trunk), lowest first
	TArray<TPair<float, int32>> FirstOrder;
	for (const int32 B : Children[Root])
	{
		if ((*BPoints)[B].Num() > 0)
		{
			FirstOrder.Add(TPair<float, int32>(((*Pos)[(*BPoints)[B][0]].Z - BaseZ) / 100.0f, B));
		}
	}
	FirstOrder.Sort([](const TPair<float, int32>& A, const TPair<float, int32>& B2) { return A.Key < B2.Key; });
	const int32 Cap = FMath::FloorToInt(FMath::Clamp(MaxShare, 0.0f, 1.0f) * FirstOrder.Num());
	TArray<int32> Remove;
	int32 Below = 0;
	for (const TPair<float, int32>& L : FirstOrder)
	{
		if (L.Key < CrownBaseM)
		{
			++Below;
			if (Remove.Num() < Cap)
			{
				Remove.Add(L.Value);
			}
		}
	}
	// mark every point but each branch's attachment vertex, over the removed limbs and their whole subtrees
	int32 MaxBud = 0;
	for (int32 I = 0; I < Bud->Num(); ++I)
	{
		MaxBud = FMath::Max(MaxBud, (*Bud)[I]);
	}
	TArray<bool> Removed;
	Removed.Init(false, MaxBud + 1);
	TArray<int32> Stack = Remove;
	int32 Marked = 0;
	while (Stack.Num() > 0)
	{
		const int32 B = Stack.Pop();
		const TArray<int32>& Pts = (*BPoints)[B];
		for (int32 K = 1; K < Pts.Num(); ++K)
		{
			const int32 BudNo = (*Bud)[Pts[K]];
			if (BudNo >= 0 && BudNo <= MaxBud && !Removed[BudNo])
			{
				Removed[BudNo] = true;
				++Marked;
			}
		}
		Stack.Append(Children[B]);
	}
	// limb-reach trim (E131): parents are walked before their children, so a child sees its attachment vertex's mark
	int32 Trimmed = 0, Whole = 0;
	if (ReachM > 0.0f)
	{
		const float Reach2 = FMath::Square(ReachM * 100.0f);
		for (const TPair<float, int32>& L : FirstOrder)
		{
			if (Remove.Contains(L.Value))
			{
				continue;
			}
			const FVector3f Axis = (*Pos)[(*BPoints)[L.Value][0]];
			Stack.Reset();
			Stack.Add(L.Value);
			while (Stack.Num() > 0)
			{
				const int32 B = Stack.Pop();
				const TArray<int32>& Pts = (*BPoints)[B];
				if (Pts.Num() == 0)
				{
					continue;
				}
				const int32 Bud0 = (*Bud)[Pts[0]];
				int32 K = 1;  // first point to go
				if (!(Bud0 >= 0 && Bud0 <= MaxBud && Removed[Bud0]))
				{
					while (K < Pts.Num() && FMath::Square((*Pos)[Pts[K]].X - Axis.X) + FMath::Square((*Pos)[Pts[K]].Y - Axis.Y) <= Reach2)
					{
						++K;
					}
				}
				if (K < Pts.Num())
				{
					++(K > 1 ? Trimmed : Whole);
				}
				for (int32 I = K; I < Pts.Num(); ++I)
				{
					const int32 BudNo = (*Bud)[Pts[I]];
					if (BudNo >= 0 && BudNo <= MaxBud && !Removed[BudNo])
					{
						Removed[BudNo] = true;
						++Marked;
					}
				}
				Stack.Append(Children[B]);
			}
		}
	}
	// write ManualEditSettings.RemovedPoints (and size RelativeOffsets to match) through reflection
	UPCGSettings* Settings = Target->GetSettings();
	FStructProperty* ParamsProp = Settings ? CastField<FStructProperty>(Settings->GetClass()->FindPropertyByName(TEXT("ManualEditSettings"))) : nullptr;
	if (!ParamsProp)
	{
		return TEXT("ERROR: Manual Edit settings have no ManualEditSettings property");
	}
	void* Params = ParamsProp->ContainerPtrToValuePtr<void>(Settings);
	FArrayProperty* RemovedProp = CastField<FArrayProperty>(ParamsProp->Struct->FindPropertyByName(TEXT("RemovedPoints")));
	FArrayProperty* OffsetsProp = CastField<FArrayProperty>(ParamsProp->Struct->FindPropertyByName(TEXT("RelativeOffsets")));
	if (!RemovedProp || !CastField<FBoolProperty>(RemovedProp->Inner))
	{
		return TEXT("ERROR: ManualEditSettings has no bool array RemovedPoints");
	}
	Settings->Modify();
	FScriptArrayHelper RemovedArr(RemovedProp, RemovedProp->ContainerPtrToValuePtr<void>(Params));
	RemovedArr.Resize(Removed.Num());
	FBoolProperty* BoolInner = CastField<FBoolProperty>(RemovedProp->Inner);
	for (int32 I = 0; I < Removed.Num(); ++I)
	{
		BoolInner->SetPropertyValue(RemovedArr.GetRawPtr(I), Removed[I]);
	}
	if (OffsetsProp)
	{
		FScriptArrayHelper OffArr(OffsetsProp, OffsetsProp->ContainerPtrToValuePtr<void>(Params));
		if (OffArr.Num() != Removed.Num())
		{
			OffArr.Resize(Removed.Num());  // new elements are zero-initialised: no offsets
		}
	}
	Settings->PostEditChange();
	Settings->MarkPackageDirty();
	const FString Out = FString::Printf(TEXT("removed %d of %d first-order limbs below %.2f m (%d below the line, %d points marked)%s%s"),
		Remove.Num(), FirstOrder.Num(), CrownBaseM, Below, Marked,
		Below > Remove.Num() ? *FString::Printf(TEXT(", CAPPED at %.2f"), MaxShare) : TEXT(""),
		ReachM > 0.0f ? *FString::Printf(TEXT("; reach %.2f m: %d branches trimmed, %d removed whole"), ReachM, Trimmed, Whole) : TEXT(""));
	UE_LOG(LogXRFFPVEDump, Display, TEXT("PVE_CROWNBASE %s: %s"), *Target->GetName(), *Out);
	return Out;
}

void UXRFFPVESkeletonDump::ReleasePVERun(UObject* Run)
{
	UPCGDefaultExecutionSource* Source = XRFFPVEDump::AsRun(Run);
	if (!Source)
	{
		return;
	}
	Source->Sunset();
	XRFFPVEDump::Runs.RemoveAll([Source](const TStrongObjectPtr<UPCGDefaultExecutionSource>& P) { return P.Get() == Source; });
}
