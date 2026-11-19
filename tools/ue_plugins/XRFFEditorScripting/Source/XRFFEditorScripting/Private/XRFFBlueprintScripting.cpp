#include "XRFFBlueprintScripting.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "Blueprint/WidgetTree.h"
#include "Components/PanelSlot.h"
#include "Components/PanelWidget.h"
#include "IAssetTools.h"
#include "WidgetBlueprint.h"
#include "WidgetBlueprintEditorUtils.h"
#include "WidgetBlueprintOperationUtils.h"
#include "UObject/ObjectRedirector.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphNode_Comment.h"
#include "EdGraphSchema_K2.h"
#include "EdGraphUtilities.h"
#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/UserDefinedEnum.h"
#include "K2Node_CallFunction.h"
#include "K2Node_CreateDelegate.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/EnumEditorUtils.h"
#include "Kismet2/Kismet2NameValidators.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/StructureEditorUtils.h"
#include "Editor.h"
#include "Animation/Skeleton.h"
#include "Engine/SkeletalMesh.h"
#include "EditorViewportClient.h"
#include "LevelEditorViewport.h"
#include "LandscapeComponent.h"
#include "LandscapeProxy.h"
#include "LandscapeInfo.h"
#include "LandscapeLayerInfoObject.h"
#include "Materials/MaterialExpressionComment.h"
#include "StructUtils/UserDefinedStruct.h"
#include "UObject/Package.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"

DEFINE_LOG_CATEGORY_STATIC(LogXRFFScripting, Log, All);

namespace
{
	bool Fail(const FString& Message)
	{
		UE_LOG(LogXRFFScripting, Error, TEXT("%s"), *Message);
		return false;
	}

	UEdGraph* FindFunctionGraph(UBlueprint* Blueprint, FName Name)
	{
		for (UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph && Graph->GetFName() == Name)
			{
				return Graph;
			}
		}
		return nullptr;
	}

	UK2Node_CustomEvent* FindCustomEvent(UBlueprint* Blueprint, FName Name)
	{
		TArray<UK2Node_CustomEvent*> Events;
		FBlueprintEditorUtils::GetAllNodesOfClass(Blueprint, Events);
		for (UK2Node_CustomEvent* Event : Events)
		{
			if (Event->CustomFunctionName == Name)
			{
				return Event;
			}
		}
		return nullptr;
	}

	TArray<UBlueprint*> WithCallers(UBlueprint* Blueprint, const TArray<UBlueprint*>& Callers)
	{
		TArray<UBlueprint*> Out{Blueprint};
		for (UBlueprint* Caller : Callers)
		{
			if (Caller)
			{
				Out.AddUnique(Caller);
			}
		}
		return Out;
	}

	// a call node whose target is the member Name of Owner (or of a class derived from it)
	bool CallsMember(UK2Node_CallFunction* Node, UBlueprint* Owner, FName Name)
	{
		if (Node->FunctionReference.GetMemberName() != Name)
		{
			return false;
		}
		for (UClass* Class = Node->FunctionReference.GetMemberParentClass(Node->GetBlueprintClassFromNode()); Class; Class = Class->GetSuperClass())
		{
			if (UBlueprint::GetBlueprintFromClass(Class) == Owner)
			{
				return true;
			}
		}
		return false;
	}

	TArray<UK2Node_CallFunction*> CallsOf(UBlueprint* Owner, FName Name, const TArray<UBlueprint*>& Blueprints)
	{
		TArray<UK2Node_CallFunction*> Out;
		for (UBlueprint* Blueprint : Blueprints)
		{
			TArray<UK2Node_CallFunction*> Calls;
			FBlueprintEditorUtils::GetAllNodesOfClass(Blueprint, Calls);
			for (UK2Node_CallFunction* Call : Calls)
			{
				if (CallsMember(Call, Owner, Name))
				{
					Out.Add(Call);
				}
			}
		}
		return Out;
	}

	FString NodePath(UEdGraphNode* Node)
	{
		UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForNode(Node);
		return FString::Printf(TEXT("%s.%s.%s"), Blueprint ? *Blueprint->GetName() : TEXT("?"), *Node->GetGraph()->GetName(), *Node->GetName());
	}

	FString FirstLine(const FString& Text)
	{
		FString First;
		return Text.Split(TEXT("\n"), &First, nullptr) ? First : Text;
	}

	UEdGraphNode_Comment* PlaceComment(UEdGraph* Graph, const FString& Text, int32 X, int32 Y, int32 Width, int32 Height, FLinearColor Color)
	{
		Graph->Modify();
		// replace only a box this function placed before: same first line, and never the editor's default text
		const FString Key = FirstLine(Text).TrimStartAndEnd();
		if (Key.Len() >= 12 && Key != TEXT("Comment"))
		{
			for (UEdGraphNode* Node : TArray<UEdGraphNode*>(Graph->Nodes))
			{
				UEdGraphNode_Comment* Old = Cast<UEdGraphNode_Comment>(Node);
				if (Old && FirstLine(Old->NodeComment).TrimStartAndEnd() == Key)
				{
					Graph->RemoveNode(Old);
				}
			}
		}
		UEdGraphNode_Comment* Comment = NewObject<UEdGraphNode_Comment>(Graph, NAME_None, RF_Transactional);
		Comment->CreateNewGuid();
		// PostPlacedNewNode resets text and colour to the editor defaults, so it runs before they are set
		Comment->PostPlacedNewNode();
		Comment->NodePosX = X;
		Comment->NodePosY = Y;
		Comment->NodeWidth = Width;
		Comment->NodeHeight = Height;
		Comment->NodeComment = Text;
		Comment->CommentColor = Color;
		Graph->AddNode(Comment, true, false);
		if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
		{
			FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
		}
		return Comment;
	}

	UEdGraphNode* FindNode(UEdGraph* Graph, const FString& Name)
	{
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node && Node->GetName() == Name)
			{
				return Node;
			}
		}
		return nullptr;
	}

	template <typename T>
	T* LoadOrNull(const FString& PackagePath)
	{
		const FString Object = PackagePath + TEXT(".") + FPackageName::GetLongPackageAssetName(PackagePath);
		return Cast<T>(StaticLoadObject(T::StaticClass(), nullptr, *Object, nullptr, LOAD_NoWarn | LOAD_Quiet));
	}
}

bool UXRFFBlueprintScripting::SetFunctionPure(UBlueprint* Blueprint, FName FunctionName, bool bPure, const TArray<UBlueprint*>& CallerBlueprints, FString& OutReport)
{
	OutReport.Reset();
	UEdGraph* Graph = Blueprint ? FindFunctionGraph(Blueprint, FunctionName) : nullptr;
	UK2Node_FunctionEntry* Entry = Graph ? Cast<UK2Node_FunctionEntry>(FBlueprintEditorUtils::GetEntryNode(Graph)) : nullptr;
	if (!Entry)
	{
		return Fail(FString::Printf(TEXT("SetFunctionPure: no function %s in %s"), *FunctionName.ToString(), Blueprint ? *Blueprint->GetName() : TEXT("null")));
	}
	if (((Entry->GetFunctionFlags() & FUNC_BlueprintPure) != 0) == bPure)
	{
		OutReport = TEXT("unchanged");
		return true;
	}

	// remember what ran into and out of every call, then cut the exec links before the pins go away
	struct FBypass
	{
		UK2Node_CallFunction* Node;
		TArray<UEdGraphPin*> Sources;
		TArray<UEdGraphPin*> Targets;
	};
	TArray<FBypass> Bypasses;
	const TArray<UBlueprint*> Blueprints = WithCallers(Blueprint, CallerBlueprints);
	for (UK2Node_CallFunction* Call : CallsOf(Blueprint, FunctionName, Blueprints))
	{
		FBypass& Bypass = Bypasses.Add_GetRef({Call, {}, {}});
		Call->Modify();
		if (UEdGraphPin* Exec = Call->GetExecPin())
		{
			Bypass.Sources = Exec->LinkedTo;
			Exec->BreakAllPinLinks();
		}
		if (UEdGraphPin* Then = Call->GetThenPin())
		{
			Bypass.Targets = Then->LinkedTo;
			Then->BreakAllPinLinks();
		}
	}

	Entry->Modify();
	if (bPure)
	{
		Entry->AddExtraFlags(FUNC_BlueprintPure);
	}
	else
	{
		Entry->ClearExtraFlags(FUNC_BlueprintPure);
	}
	if (UFunction* Function = Blueprint->SkeletonGeneratedClass ? FindUField<UFunction>(Blueprint->SkeletonGeneratedClass, FunctionName) : nullptr)
	{
		Function->Modify();
		Function->FunctionFlags = bPure ? (Function->FunctionFlags | FUNC_BlueprintPure) : (Function->FunctionFlags & ~FUNC_BlueprintPure);
	}
	Entry->ReconstructNode();
	GetDefault<UEdGraphSchema_K2>()->HandleParameterDefaultValueChanged(Entry);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);

	const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
	TSet<UBlueprint*> Touched;
	for (FBypass& Bypass : Bypasses)
	{
		Bypass.Node->ReconstructNode();
		int32 Links = 0;
		if (bPure)
		{
			for (UEdGraphPin* Source : Bypass.Sources)
			{
				for (UEdGraphPin* Target : Bypass.Targets)
				{
					Links += Schema->TryCreateConnection(Source, Target) ? 1 : 0;
				}
			}
		}
		OutReport += FString::Printf(TEXT("%s: %d in, %d out, %d bypass links%s\n"), *NodePath(Bypass.Node), Bypass.Sources.Num(), Bypass.Targets.Num(), Links,
			bPure ? TEXT("") : TEXT(" (now impure: wire its exec pins by hand)"));
		Touched.Add(FBlueprintEditorUtils::FindBlueprintForNode(Bypass.Node));
	}
	for (UBlueprint* Caller : Touched)
	{
		if (Caller && Caller != Blueprint)
		{
			FBlueprintEditorUtils::MarkBlueprintAsModified(Caller);
			FKismetEditorUtilities::CompileBlueprint(Caller);
		}
	}
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	return true;
}

bool UXRFFBlueprintScripting::RenameMember(UBlueprint* Blueprint, FName OldName, FName NewName)
{
	if (!Blueprint)
	{
		return Fail(TEXT("RenameMember: no blueprint"));
	}
	if (FKismetNameValidator(Blueprint).IsValid(NewName) != EValidatorResult::Ok)
	{
		return Fail(FString::Printf(TEXT("RenameMember: %s is taken or invalid in %s"), *NewName.ToString(), *Blueprint->GetName()));
	}
	if (FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, OldName) != INDEX_NONE)
	{
		FBlueprintEditorUtils::RenameMemberVariable(Blueprint, OldName, NewName);
		return FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, NewName) != INDEX_NONE
			|| Fail(FString::Printf(TEXT("RenameMember: %s.%s did not rename"), *Blueprint->GetName(), *OldName.ToString()));
	}
	if (Blueprint->SimpleConstructionScript)
	{
		for (USCS_Node* Node : Blueprint->SimpleConstructionScript->GetAllNodes())
		{
			if (Node && Node->GetVariableName() == OldName)
			{
				FBlueprintEditorUtils::RenameComponentMemberVariable(Blueprint, Node, NewName);
				return Node->GetVariableName() == NewName
					|| Fail(FString::Printf(TEXT("RenameMember: component %s.%s did not rename"), *Blueprint->GetName(), *OldName.ToString()));
			}
		}
	}
	return Fail(FString::Printf(TEXT("RenameMember: %s has no variable, dispatcher or component %s"), *Blueprint->GetName(), *OldName.ToString()));
}

bool UXRFFBlueprintScripting::RenameFunctionOrEvent(UBlueprint* Blueprint, FName OldName, FName NewName, const TArray<UBlueprint*>& CallerBlueprints, FString& OutReport)
{
	OutReport.Reset();
	if (!Blueprint)
	{
		return Fail(TEXT("RenameFunctionOrEvent: no blueprint"));
	}
	if (FKismetNameValidator(Blueprint).IsValid(NewName) != EValidatorResult::Ok)
	{
		return Fail(FString::Printf(TEXT("RenameFunctionOrEvent: %s is taken or invalid in %s"), *NewName.ToString(), *Blueprint->GetName()));
	}
	const TArray<UBlueprint*> Blueprints = WithCallers(Blueprint, CallerBlueprints);
	// collect the call nodes first: after the rename the old name no longer resolves
	const TArray<UK2Node_CallFunction*> Calls = CallsOf(Blueprint, OldName, Blueprints);
	if (UEdGraph* Graph = FindFunctionGraph(Blueprint, OldName))
	{
		FBlueprintEditorUtils::RenameGraph(Graph, NewName.ToString());
	}
	else if (UK2Node_CustomEvent* Event = FindCustomEvent(Blueprint, OldName))
	{
		Event->Modify();
		Event->OnRenameNode(NewName.ToString());
	}
	else
	{
		return Fail(FString::Printf(TEXT("RenameFunctionOrEvent: %s has no function or custom event %s"), *Blueprint->GetName(), *OldName.ToString()));
	}

	for (UK2Node_CallFunction* Call : Calls)
	{
		if (Call->FunctionReference.GetMemberName() == NewName)
		{
			continue;
		}
		Call->Modify();
		const FGuid Guid = Call->FunctionReference.GetMemberGuid();
		if (Call->FunctionReference.IsSelfContext())
		{
			Call->FunctionReference.SetSelfMember(NewName, Guid);
		}
		else
		{
			Call->FunctionReference.SetExternalMember(NewName, Call->FunctionReference.GetMemberParentClass(Call->GetBlueprintClassFromNode()), Guid);
		}
		Call->ReconstructNode();
		OutReport += FString::Printf(TEXT("call %s\n"), *NodePath(Call));
	}
	for (UBlueprint* Each : Blueprints)
	{
		TArray<UK2Node_CreateDelegate*> Delegates;
		FBlueprintEditorUtils::GetAllNodesOfClass(Each, Delegates);
		for (UK2Node_CreateDelegate* Delegate : Delegates)
		{
			if (Delegate->GetFunctionName() == OldName)
			{
				Delegate->Modify();
				Delegate->SetFunction(NewName);
				OutReport += FString::Printf(TEXT("create event %s\n"), *NodePath(Delegate));
			}
		}
		TArray<UEdGraphNode*> Nodes;
		FBlueprintEditorUtils::GetAllNodesOfClass(Each, Nodes);
		for (UEdGraphNode* Node : Nodes)
		{
			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (Pin && Pin->Direction == EGPD_Input && Pin->DefaultValue == OldName.ToString())
				{
					OutReport += FString::Printf(TEXT("STRING still names it: %s pin %s\n"), *NodePath(Node), *Pin->PinName.ToString());
				}
			}
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Each);
	}
	return true;
}

bool UXRFFBlueprintScripting::RenameParameter(UBlueprint* Blueprint, FName FunctionName, FName OldName, FName NewName, const TArray<UBlueprint*>& CallerBlueprints)
{
	if (!Blueprint)
	{
		return Fail(TEXT("RenameParameter: no blueprint"));
	}
	TArray<UK2Node_EditablePinBase*> Terminals;
	if (UEdGraph* Graph = FindFunctionGraph(Blueprint, FunctionName))
	{
		Terminals.Add(FBlueprintEditorUtils::GetEntryNode(Graph));
		TArray<UK2Node_FunctionResult*> Results;
		Graph->GetNodesOfClass(Results);
		Terminals.Append(Results);
	}
	else if (UK2Node_CustomEvent* Event = FindCustomEvent(Blueprint, FunctionName))
	{
		Terminals.Add(Event);
	}
	Terminals.Remove(nullptr);
	if (Terminals.IsEmpty())
	{
		return Fail(FString::Printf(TEXT("RenameParameter: %s has no function or custom event %s"), *Blueprint->GetName(), *FunctionName.ToString()));
	}
	TArray<UK2Node*> Nodes(Terminals);
	Nodes.Append(CallsOf(Blueprint, FunctionName, WithCallers(Blueprint, CallerBlueprints)));
	bool bFound = false;
	for (UK2Node* Node : Nodes)
	{
		const ERenamePinResult Test = Node->RenameUserDefinedPin(OldName, NewName, true);
		if (Test == ERenamePinResult_NameCollision)
		{
			return Fail(FString::Printf(TEXT("RenameParameter: %s collides on %s"), *NewName.ToString(), *NodePath(Node)));
		}
		bFound |= Test == ERenamePinResult_Success;
	}
	if (!bFound)
	{
		return Fail(FString::Printf(TEXT("RenameParameter: %s.%s has no parameter %s"), *Blueprint->GetName(), *FunctionName.ToString(), *OldName.ToString()));
	}
	for (UK2Node* Node : Nodes)
	{
		Node->Modify();
		Node->RenameUserDefinedPin(OldName, NewName, false);
	}
	for (UK2Node_EditablePinBase* Terminal : Terminals)
	{
		for (TSharedPtr<FUserPinInfo>& Info : Terminal->UserDefinedPins)
		{
			if (Info.IsValid() && Info->PinName == OldName)
			{
				Info->PinName = NewName;
			}
		}
		Terminal->ReconstructNode();
	}
	for (UBlueprint* Each : WithCallers(Blueprint, CallerBlueprints))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Each);
	}
	return true;
}

TArray<FString> UXRFFBlueprintScripting::DescribeVariables(UBlueprint* Blueprint)
{
	TArray<FString> Out;
	if (!Blueprint)
	{
		return Out;
	}
	for (const FBPVariableDescription& Var : Blueprint->NewVariables)
	{
		TArray<FString> Flags;
		if (!(Var.PropertyFlags & CPF_DisableEditOnInstance))
		{
			Flags.Add(TEXT("InstanceEditable"));
		}
		if (Var.PropertyFlags & CPF_ExposeOnSpawn)
		{
			Flags.Add(TEXT("ExposeOnSpawn"));
		}
		if (Var.PropertyFlags & CPF_BlueprintReadOnly)
		{
			Flags.Add(TEXT("ReadOnly"));
		}
		if (Var.HasMetaData(FBlueprintMetadata::MD_Private) && Var.GetMetaData(FBlueprintMetadata::MD_Private) == TEXT("true"))
		{
			Flags.Add(TEXT("Private"));
		}
		if (Var.VarType.IsContainer())
		{
			Flags.Add(Var.VarType.IsArray() ? TEXT("Array") : Var.VarType.IsSet() ? TEXT("Set") : TEXT("Map"));
		}
		if (Var.VarType.PinCategory == UEdGraphSchema_K2::PC_MCDelegate)
		{
			Flags.Add(TEXT("Delegate"));
		}
		const UObject* Sub = Var.VarType.PinSubCategoryObject.Get();
		const FString Type = Var.VarType.PinCategory.ToString() + (Sub ? TEXT("/") + Sub->GetName() : FString());
		const FString Tooltip = Var.HasMetaData(FBlueprintMetadata::MD_Tooltip) ? Var.GetMetaData(FBlueprintMetadata::MD_Tooltip).Replace(TEXT("\n"), TEXT(" ")) : FString();
		Out.Add(FString::Printf(TEXT("%s|%s|%s|%s|%s"), *Var.VarName.ToString(), *Var.Category.ToString(), *Type, *FString::Join(Flags, TEXT(",")), *Tooltip));
	}
	return Out;
}

FEdGraphPinType UXRFFBlueprintScripting::GetVariablePinType(UBlueprint* Blueprint, FName VariableName)
{
	const int32 Index = Blueprint ? FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName) : INDEX_NONE;
	return Index == INDEX_NONE ? FEdGraphPinType() : Blueprint->NewVariables[Index].VarType;
}

bool UXRFFBlueprintScripting::SetVariableTooltip(UBlueprint* Blueprint, FName VariableName, const FString& Tooltip)
{
	if (!Blueprint || FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName) == INDEX_NONE)
	{
		return Fail(FString::Printf(TEXT("SetVariableTooltip: no variable %s"), *VariableName.ToString()));
	}
	if (Tooltip.IsEmpty())
	{
		FBlueprintEditorUtils::RemoveBlueprintVariableMetaData(Blueprint, VariableName, nullptr, FBlueprintMetadata::MD_Tooltip);
	}
	else
	{
		FBlueprintEditorUtils::SetBlueprintVariableMetaData(Blueprint, VariableName, nullptr, FBlueprintMetadata::MD_Tooltip, Tooltip);
	}
	return true;
}

bool UXRFFBlueprintScripting::SetFunctionDescription(UBlueprint* Blueprint, FName FunctionName, const FString& Tooltip, const FString& Category)
{
	UEdGraph* Graph = Blueprint ? FindFunctionGraph(Blueprint, FunctionName) : nullptr;
	UK2Node_FunctionEntry* Entry = Graph ? Cast<UK2Node_FunctionEntry>(FBlueprintEditorUtils::GetEntryNode(Graph)) : nullptr;
	if (!Entry)
	{
		return Fail(FString::Printf(TEXT("SetFunctionDescription: no function %s"), *FunctionName.ToString()));
	}
	Entry->Modify();
	Entry->MetaData.ToolTip = FText::FromString(Tooltip);
	FBlueprintEditorUtils::ModifyFunctionMetaData(Graph);
	if (!Category.IsEmpty())
	{
		FBlueprintEditorUtils::SetBlueprintFunctionOrMacroCategory(Graph, FText::FromString(Category), true);
	}
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

UEdGraphNode* UXRFFBlueprintScripting::AddCommentAroundNodes(UEdGraph* Graph, const TArray<FString>& NodeNames, const FString& Text, FLinearColor Color, float Padding)
{
	if (!Graph)
	{
		Fail(TEXT("AddCommentAroundNodes: no graph"));
		return nullptr;
	}
	TArray<UEdGraphNode*> Nodes;
	for (const FString& Name : NodeNames)
	{
		if (UEdGraphNode* Node = FindNode(Graph, Name))
		{
			Nodes.Add(Node);
		}
		else
		{
			UE_LOG(LogXRFFScripting, Warning, TEXT("AddCommentAroundNodes: %s has no node %s"), *Graph->GetName(), *Name);
		}
	}
	if (Nodes.IsEmpty())
	{
		Fail(FString::Printf(TEXT("AddCommentAroundNodes: none of the nodes found in %s"), *Graph->GetName()));
		return nullptr;
	}
	int32 MinX = MAX_int32, MinY = MAX_int32, MaxX = MIN_int32, MaxY = MIN_int32;
	for (UEdGraphNode* Node : Nodes)
	{
		// node sizes exist only once the graph has been drawn; estimate them from the title and the pin count
		int32 Inputs = 0, Outputs = 0;
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && !Pin->bHidden)
			{
				(Pin->Direction == EGPD_Input ? Inputs : Outputs) += 1;
			}
		}
		const int32 Width = Node->NodeWidth > 0 ? Node->NodeWidth : FMath::Clamp(80 + 8 * Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString().Len(), 160, 420);
		const int32 Height = Node->NodeHeight > 0 ? Node->NodeHeight : 48 + 24 * FMath::Max(Inputs, Outputs);
		MinX = FMath::Min(MinX, Node->NodePosX);
		MinY = FMath::Min(MinY, Node->NodePosY);
		MaxX = FMath::Max(MaxX, Node->NodePosX + Width);
		MaxY = FMath::Max(MaxY, Node->NodePosY + Height);
	}
	int32 Lines = 1;
	for (TCHAR C : Text)
	{
		Lines += C == TEXT('\n') ? 1 : 0;
	}
	const int32 Pad = FMath::RoundToInt(Padding);
	const int32 Top = Pad + 28 * Lines;
	UEdGraphNode_Comment* Comment = PlaceComment(Graph, Text, MinX - Pad, MinY - Top, MaxX - MinX + 2 * Pad, MaxY - MinY + Top + Pad, Color);
	for (UEdGraphNode* Node : Nodes)
	{
		Comment->AddNodeUnderComment(Node);
	}
	return Comment;
}

UEdGraphNode* UXRFFBlueprintScripting::AddCommentBox(UEdGraph* Graph, const FString& Text, int32 X, int32 Y, int32 Width, int32 Height, FLinearColor Color)
{
	if (!Graph)
	{
		Fail(TEXT("AddCommentBox: no graph"));
		return nullptr;
	}
	return PlaceComment(Graph, Text, X, Y, Width, Height, Color);
}

TArray<FString> UXRFFBlueprintScripting::DescribeGraph(UEdGraph* Graph)
{
	TArray<FString> Out;
	if (Graph)
	{
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node)
			{
				Out.Add(FString::Printf(TEXT("%s|%s|%d|%d|%d|%d|%s"), *Node->GetName(), *Node->GetNodeTitle(ENodeTitleType::ListView).ToString().Replace(TEXT("\n"), TEXT(" ")),
					Node->NodePosX, Node->NodePosY, Node->NodeWidth, Node->NodeHeight, *Node->GetClass()->GetName()));
			}
		}
	}
	return Out;
}

FString UXRFFBlueprintScripting::ExportNodes(UEdGraph* Graph, const TArray<FString>& NodeNames)
{
	FString Text;
	if (!Graph)
	{
		Fail(TEXT("ExportNodes: no graph"));
		return Text;
	}
	TSet<UObject*> Nodes;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (Node && Node->CanDuplicateNode() && (NodeNames.IsEmpty() || NodeNames.Contains(Node->GetName())))
		{
			Node->PrepareForCopying();
			Nodes.Add(Node);
		}
	}
	FEdGraphUtilities::ExportNodesToText(Nodes, Text);
	return Text;
}

TArray<FString> UXRFFBlueprintScripting::ImportNodes(UEdGraph* Graph, const FString& Text, int32 OffsetX, int32 OffsetY)
{
	TArray<FString> Out;
	if (!Graph || !FEdGraphUtilities::CanImportNodesFromText(Graph, Text))
	{
		Fail(TEXT("ImportNodes: no graph, or the text holds nothing this graph accepts"));
		return Out;
	}
	Graph->Modify();
	TSet<UEdGraphNode*> Imported;
	FEdGraphUtilities::ImportNodesFromText(Graph, Text, Imported);
	for (UEdGraphNode* Node : Imported)
	{
		Node->CreateNewGuid();
		Node->NodePosX += OffsetX;
		Node->NodePosY += OffsetY;
		Out.Add(Node->GetName());
	}
	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	}
	return Out;
}

int32 UXRFFBlueprintScripting::DeleteNodes(UEdGraph* Graph, const TArray<FString>& NodeNames)
{
	UBlueprint* Blueprint = Graph ? FBlueprintEditorUtils::FindBlueprintForGraph(Graph) : nullptr;
	int32 Deleted = 0;
	for (const FString& Name : NodeNames)
	{
		UEdGraphNode* Node = Graph ? FindNode(Graph, Name) : nullptr;
		if (!Node || Node->IsA<UK2Node_FunctionEntry>() || Node->IsA<UK2Node_FunctionResult>() || !Node->CanUserDeleteNode())
		{
			UE_LOG(LogXRFFScripting, Warning, TEXT("DeleteNodes: %s not deleted (missing, entry/result or not deletable)"), *Name);
			continue;
		}
		if (Blueprint)
		{
			FBlueprintEditorUtils::RemoveNode(Blueprint, Node, true);
		}
		else
		{
			Graph->RemoveNode(Node);
		}
		++Deleted;
	}
	return Deleted;
}

UUserDefinedEnum* UXRFFBlueprintScripting::CreateOrUpdateEnum(const FString& PackagePath, const TArray<FString>& DisplayNames, const FString& Description)
{
	if (DisplayNames.IsEmpty())
	{
		Fail(TEXT("CreateOrUpdateEnum: no entries"));
		return nullptr;
	}
	UUserDefinedEnum* Enum = LoadOrNull<UUserDefinedEnum>(PackagePath);
	if (!Enum)
	{
		UPackage* Package = CreatePackage(*PackagePath);
		Enum = Cast<UUserDefinedEnum>(FEnumEditorUtils::CreateUserDefinedEnum(Package, FName(*FPackageName::GetLongPackageAssetName(PackagePath)), RF_Public | RF_Standalone | RF_Transactional));
		if (!Enum)
		{
			Fail(FString::Printf(TEXT("CreateOrUpdateEnum: could not create %s"), *PackagePath));
			return nullptr;
		}
		FAssetRegistryModule::AssetCreated(Enum);
	}
	Enum->Modify();
	// NumEnums counts the hidden _MAX entry
	while (Enum->NumEnums() - 1 < DisplayNames.Num())
	{
		FEnumEditorUtils::AddNewEnumeratorForUserDefinedEnum(Enum);
	}
	while (Enum->NumEnums() - 1 > DisplayNames.Num())
	{
		FEnumEditorUtils::RemoveEnumeratorFromUserDefinedEnum(Enum, Enum->NumEnums() - 2);
	}
	// two passes, so a reordering never collides with a name still in use
	for (int32 i = 0; i < DisplayNames.Num(); ++i)
	{
		FEnumEditorUtils::SetEnumeratorDisplayName(Enum, i, FText::FromString(FString::Printf(TEXT("XRFFTmp%d"), i)));
	}
	for (int32 i = 0; i < DisplayNames.Num(); ++i)
	{
		if (!FEnumEditorUtils::SetEnumeratorDisplayName(Enum, i, FText::FromString(DisplayNames[i])))
		{
			Fail(FString::Printf(TEXT("CreateOrUpdateEnum: display name %s rejected"), *DisplayNames[i]));
		}
	}
	Enum->EnumDescription = FText::FromString(Description);
	Enum->MarkPackageDirty();
	return Enum;
}

UUserDefinedStruct* UXRFFBlueprintScripting::CreateOrUpdateStruct(const FString& PackagePath, const TArray<FXRFFStructField>& Fields, const FString& Description)
{
	UUserDefinedStruct* Struct = LoadOrNull<UUserDefinedStruct>(PackagePath);
	TArray<FGuid> Placeholders;
	if (!Struct)
	{
		UPackage* Package = CreatePackage(*PackagePath);
		Struct = FStructureEditorUtils::CreateUserDefinedStruct(Package, FName(*FPackageName::GetLongPackageAssetName(PackagePath)), RF_Public | RF_Standalone | RF_Transactional);
		if (!Struct)
		{
			Fail(FString::Printf(TEXT("CreateOrUpdateStruct: could not create %s"), *PackagePath));
			return nullptr;
		}
		FAssetRegistryModule::AssetCreated(Struct);
		// a new struct starts with one placeholder member
		for (const FStructVariableDescription& Var : FStructureEditorUtils::GetVarDesc(Struct))
		{
			Placeholders.Add(Var.VarGuid);
		}
	}
	Struct->Modify();
	for (const FXRFFStructField& Field : Fields)
	{
		const FStructVariableDescription* Existing = FStructureEditorUtils::GetVarDesc(Struct).FindByPredicate(
			[&](const FStructVariableDescription& Var) { return Var.FriendlyName == Field.Name; });
		if (Existing)
		{
			if (Existing->ToPinType() != Field.Type)
			{
				UE_LOG(LogXRFFScripting, Warning, TEXT("CreateOrUpdateStruct: %s.%s has another type; left as it is"), *Struct->GetName(), *Field.Name);
			}
			continue;
		}
		if (!FStructureEditorUtils::AddVariable(Struct, Field.Type))
		{
			Fail(FString::Printf(TEXT("CreateOrUpdateStruct: could not add %s"), *Field.Name));
			continue;
		}
		const FGuid Guid = FStructureEditorUtils::GetVarDesc(Struct).Last().VarGuid;
		FStructureEditorUtils::RenameVariable(Struct, Guid, Field.Name);
		if (!Field.DefaultValue.IsEmpty())
		{
			FStructureEditorUtils::ChangeVariableDefaultValue(Struct, Guid, Field.DefaultValue);
		}
		if (!Field.Tooltip.IsEmpty())
		{
			FStructureEditorUtils::ChangeVariableTooltip(Struct, Guid, Field.Tooltip);
		}
	}
	if (!Fields.IsEmpty())
	{
		for (const FGuid& Guid : Placeholders)
		{
			FStructureEditorUtils::RemoveVariable(Struct, Guid);
		}
	}
	if (UUserDefinedStructEditorData* Data = Cast<UUserDefinedStructEditorData>(Struct->EditorData))
	{
		Data->ToolTip = Description;
	}
	Struct->MarkPackageDirty();
	return Struct;
}

FEdGraphPinType UXRFFBlueprintScripting::GetEnumPinType(UEnum* Enum)
{
	FEdGraphPinType Type;
	Type.PinCategory = UEdGraphSchema_K2::PC_Byte;
	Type.PinSubCategoryObject = Enum;
	return Type;
}

bool UXRFFBlueprintScripting::AddParameter(UBlueprint* Blueprint, FName FunctionName, FName ParamName, const FEdGraphPinType& Type, bool bOutput)
{
	if (!Blueprint)
	{
		return Fail(TEXT("AddParameter: no blueprint"));
	}
	UK2Node_EditablePinBase* Node = nullptr;
	if (UEdGraph* Graph = FindFunctionGraph(Blueprint, FunctionName))
	{
		UK2Node_EditablePinBase* Entry = FBlueprintEditorUtils::GetEntryNode(Graph);
		Node = bOutput && Entry ? FBlueprintEditorUtils::FindOrCreateFunctionResultNode(Entry) : Entry;
	}
	else if (!bOutput)
	{
		Node = FindCustomEvent(Blueprint, FunctionName);
	}
	if (!Node)
	{
		return Fail(FString::Printf(TEXT("AddParameter: %s has no function%s %s"), *Blueprint->GetName(), bOutput ? TEXT("") : TEXT(" or custom event"), *FunctionName.ToString()));
	}
	for (const TSharedPtr<FUserPinInfo>& Info : Node->UserDefinedPins)
	{
		if (Info.IsValid() && Info->PinName == ParamName)
		{
			return true;
		}
	}
	Node->Modify();
	// entry and event nodes carry the inputs as output pins; the result node carries the outputs as input pins
	if (!Node->CreateUserDefinedPin(ParamName, Type, bOutput ? EGPD_Input : EGPD_Output, false))
	{
		return Fail(FString::Printf(TEXT("AddParameter: could not add %s to %s"), *ParamName.ToString(), *FunctionName.ToString()));
	}
	Node->ReconstructNode();
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return true;
}

UBlueprint* UXRFFBlueprintScripting::CreateBlueprintAsset(const FString& PackagePath, UClass* ParentClass, const FString& Kind)
{
	if (UBlueprint* Existing = LoadOrNull<UBlueprint>(PackagePath))
	{
		return Existing;
	}
	EBlueprintType Type = BPTYPE_Normal;
	UClass* Parent = ParentClass;
	if (Kind == TEXT("Interface"))
	{
		Type = BPTYPE_Interface;
		Parent = UInterface::StaticClass();
	}
	else if (Kind == TEXT("FunctionLibrary"))
	{
		Type = BPTYPE_FunctionLibrary;
		Parent = UBlueprintFunctionLibrary::StaticClass();
	}
	if (!Parent)
	{
		Fail(TEXT("CreateBlueprintAsset: no parent class"));
		return nullptr;
	}
	UPackage* Package = CreatePackage(*PackagePath);
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(Parent, Package, FName(*FPackageName::GetLongPackageAssetName(PackagePath)), Type);
	if (Blueprint)
	{
		FAssetRegistryModule::AssetCreated(Blueprint);
		Blueprint->MarkPackageDirty();
	}
	return Blueprint;
}

int32 UXRFFBlueprintScripting::FixUpRedirectors(const TArray<FString>& ContentPaths)
{
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry").Get();
	FARFilter Filter;
	Filter.bRecursivePaths = true;
	Filter.ClassPaths.Add(UObjectRedirector::StaticClass()->GetClassPathName());
	for (const FString& Path : ContentPaths)
	{
		Filter.PackagePaths.Add(FName(*Path));
	}
	TArray<FAssetData> Found;
	Registry.GetAssets(Filter, Found);
	TArray<UObjectRedirector*> Redirectors;
	for (const FAssetData& Asset : Found)
	{
		if (UObjectRedirector* Redirector = Cast<UObjectRedirector>(Asset.GetAsset()))
		{
			Redirectors.Add(Redirector);
		}
	}
	if (!Redirectors.IsEmpty())
	{
		FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get().FixupReferencers(Redirectors, false, ERedirectFixupMode::DeleteFixedUpRedirectors);
	}
	return Redirectors.Num();
}

int32 UXRFFBlueprintScripting::WireWorldContext(UEdGraph* Graph)
{
	UK2Node_FunctionEntry* Entry = Graph ? Cast<UK2Node_FunctionEntry>(FBlueprintEditorUtils::GetEntryNode(Graph)) : nullptr;
	UEdGraphPin* Context = Entry ? Entry->GetAutoWorldContextPin() : nullptr;
	if (!Context)
	{
		Fail(FString::Printf(TEXT("WireWorldContext: %s has no __WorldContext (not a function-library function?)"), Graph ? *Graph->GetName() : TEXT("null")));
		return 0;
	}
	const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
	int32 Links = 0;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node || Node == Entry)
		{
			continue;
		}
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->Direction == EGPD_Input && Pin->LinkedTo.IsEmpty()
				&& (Pin->PinName == TEXT("WorldContextObject") || Pin->PinName == TEXT("__WorldContext")))
			{
				Links += Schema->TryCreateConnection(Context, Pin) ? 1 : 0;
			}
		}
	}
	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
	{
		FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	}
	return Links;
}

bool UXRFFBlueprintScripting::SetPinDefaultObject(UEdGraph* Graph, const FString& NodeName, FName PinName, UObject* Value)
{
	UEdGraphNode* Node = Graph ? FindNode(Graph, NodeName) : nullptr;
	UEdGraphPin* Pin = Node ? Node->FindPin(PinName, EGPD_Input) : nullptr;
	if (!Pin)
	{
		return Fail(FString::Printf(TEXT("SetPinDefaultObject: no input %s on %s"), *PinName.ToString(), *NodeName));
	}
	Node->Modify();
	GetDefault<UEdGraphSchema_K2>()->TrySetDefaultObject(*Pin, Value);
	Node->PinDefaultValueChanged(Pin);
	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
	{
		FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	}
	return Pin->DefaultObject == Value;
}

bool UXRFFBlueprintScripting::SetPinDefaultValue(UEdGraph* Graph, const FString& NodeName, FName PinName, const FString& Value)
{
	UEdGraphNode* Node = Graph ? FindNode(Graph, NodeName) : nullptr;
	UEdGraphPin* Pin = Node ? Node->FindPin(PinName, EGPD_Input) : nullptr;
	if (!Pin)
	{
		return Fail(FString::Printf(TEXT("SetPinDefaultValue: no input %s on %s"), *PinName.ToString(), *NodeName));
	}
	Node->Modify();
	GetDefault<UEdGraphSchema_K2>()->TrySetDefaultValue(*Pin, Value);
	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
	{
		FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	}
	return Pin->DefaultValue == Value || Fail(FString::Printf(TEXT("SetPinDefaultValue: %s.%s kept '%s'"), *NodeName, *PinName.ToString(), *Pin->DefaultValue));
}

static UEdGraphPin* FindPinAnyDirection(UEdGraphNode* Node, FName PinName)
{
	if (!Node)
	{
		return nullptr;
	}
	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && Pin->PinName == PinName)
		{
			return Pin;
		}
	}
	return nullptr;
}

bool UXRFFBlueprintScripting::LinkPins(UEdGraph* Graph, const FString& NodeA, FName PinA, const FString& NodeB, FName PinB)
{
	UEdGraphPin* A = Graph ? FindPinAnyDirection(FindNode(Graph, NodeA), PinA) : nullptr;
	UEdGraphPin* B = Graph ? FindPinAnyDirection(FindNode(Graph, NodeB), PinB) : nullptr;
	if (!A || !B)
	{
		return Fail(FString::Printf(TEXT("LinkPins: missing %s.%s or %s.%s"), *NodeA, *PinA.ToString(), *NodeB, *PinB.ToString()));
	}
	A->GetOwningNode()->Modify();
	B->GetOwningNode()->Modify();
	if (!Graph->GetSchema()->TryCreateConnection(A, B))
	{
		return Fail(FString::Printf(TEXT("LinkPins: schema refused %s.%s -> %s.%s"), *NodeA, *PinA.ToString(), *NodeB, *PinB.ToString()));
	}
	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
	{
		FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	}
	return true;
}

int32 UXRFFBlueprintScripting::BreakPinLinks(UEdGraph* Graph, const FString& NodeName, FName PinName)
{
	UEdGraphPin* Pin = Graph ? FindPinAnyDirection(FindNode(Graph, NodeName), PinName) : nullptr;
	if (!Pin)
	{
		Fail(FString::Printf(TEXT("BreakPinLinks: no pin %s on %s"), *PinName.ToString(), *NodeName));
		return -1;
	}
	const int32 Count = Pin->LinkedTo.Num();
	Pin->GetOwningNode()->Modify();
	Graph->GetSchema()->BreakPinLinks(*Pin, true);
	if (UBlueprint* Blueprint = FBlueprintEditorUtils::FindBlueprintForGraph(Graph))
	{
		FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	}
	return Count;
}

bool UXRFFBlueprintScripting::ImplementInterface(UBlueprint* Blueprint, UClass* InterfaceClass)
{
	if (!Blueprint || !InterfaceClass)
	{
		return Fail(TEXT("ImplementInterface: no blueprint or interface"));
	}
	return FBlueprintEditorUtils::ImplementNewInterface(Blueprint, InterfaceClass->GetClassPathName())
		|| Fail(FString::Printf(TEXT("ImplementInterface: %s did not take %s"), *Blueprint->GetName(), *InterfaceClass->GetName()));
}

bool UXRFFBlueprintScripting::RefreshAllNodes(UBlueprint* Blueprint)
{
	if (!Blueprint)
	{
		return Fail(TEXT("RefreshAllNodes: no blueprint"));
	}
	FBlueprintEditorUtils::RefreshAllNodes(Blueprint);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return true;
}

namespace
{
	UWidget* FindDesignerWidget(UBlueprint* Blueprint, const FString& Name, const TCHAR* Caller)
	{
		UWidgetBlueprint* Widgets = Cast<UWidgetBlueprint>(Blueprint);
		UWidget* Widget = Widgets && Widgets->WidgetTree ? Widgets->WidgetTree->FindWidget(FName(*Name)) : nullptr;
		if (!Widget)
		{
			Fail(FString::Printf(TEXT("%s: %s has no widget %s"), Caller, Blueprint ? *Blueprint->GetName() : TEXT("null"), *Name));
		}
		return Widget;
	}
}

TArray<FString> UXRFFBlueprintScripting::ListWidgets(UBlueprint* WidgetBlueprint)
{
	TArray<FString> Out;
	UWidgetBlueprint* Widgets = Cast<UWidgetBlueprint>(WidgetBlueprint);
	if (!Widgets || !Widgets->WidgetTree)
	{
		Fail(TEXT("ListWidgets: not a widget blueprint"));
		return Out;
	}
	Widgets->WidgetTree->ForEachWidget([&Out](UWidget* Widget)
	{
		const UPanelWidget* Parent = Widget->GetParent();
		Out.Add(FString::Printf(TEXT("%s|%s|%d|%s"), *Widget->GetName(), *Widget->GetClass()->GetName(), Widget->bIsVariable ? 1 : 0, Parent ? *Parent->GetName() : TEXT("")));
	});
	return Out;
}

FString UXRFFBlueprintScripting::GetWidgetProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName)
{
	FString Value;
	UWidget* Widget = FindDesignerWidget(WidgetBlueprint, WidgetName, TEXT("GetWidgetProperty"));
	const FProperty* Property = Widget ? Widget->GetClass()->FindPropertyByName(FName(*PropertyName)) : nullptr;
	if (Property)
	{
		Property->ExportTextItem_InContainer(Value, Widget, nullptr, Widget, PPF_None);
	}
	return Value;
}

bool UXRFFBlueprintScripting::SetWidgetProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName, const FString& Value)
{
	UWidget* Widget = FindDesignerWidget(WidgetBlueprint, WidgetName, TEXT("SetWidgetProperty"));
	if (!Widget)
	{
		return false;
	}
	FProperty* Property = Widget->GetClass()->FindPropertyByName(FName(*PropertyName));
	if (!Property)
	{
		return Fail(FString::Printf(TEXT("SetWidgetProperty: %s has no property %s"), *WidgetName, *PropertyName));
	}
	Widget->Modify();
	if (!Property->ImportText_InContainer(*Value, Widget, Widget, PPF_None))
	{
		return Fail(FString::Printf(TEXT("SetWidgetProperty: %s.%s rejected %s"), *WidgetName, *PropertyName, *Value));
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
	return true;
}

TArray<FString> UXRFFBlueprintScripting::ListWidgetBindings(UBlueprint* WidgetBlueprint)
{
	TArray<FString> Out;
	UWidgetBlueprint* Widgets = Cast<UWidgetBlueprint>(WidgetBlueprint);
	if (!Widgets)
	{
		Fail(TEXT("ListWidgetBindings: not a widget blueprint"));
		return Out;
	}
	for (const FDelegateEditorBinding& Binding : Widgets->Bindings)
	{
		const bool bFunction = Binding.Kind == EBindingKind::Function;
		Out.Add(FString::Printf(TEXT("%s|%s|%s|%s"), *Binding.ObjectName, *Binding.PropertyName.ToString(),
			bFunction ? *Binding.FunctionName.ToString() : *Binding.SourceProperty.ToString(), bFunction ? TEXT("Function") : TEXT("Property")));
	}
	return Out;
}

bool UXRFFBlueprintScripting::RemoveWidgetBinding(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName)
{
	UWidgetBlueprint* Widgets = Cast<UWidgetBlueprint>(WidgetBlueprint);
	if (!Widgets)
	{
		return Fail(TEXT("RemoveWidgetBinding: not a widget blueprint"));
	}
	Widgets->Modify();
	const int32 Removed = Widgets->Bindings.RemoveAll([&](const FDelegateEditorBinding& Binding)
	{
		return Binding.ObjectName == WidgetName && Binding.PropertyName == FName(*PropertyName);
	});
	if (Removed == 0)
	{
		return Fail(FString::Printf(TEXT("RemoveWidgetBinding: %s has no binding %s.%s"), *Widgets->GetName(), *WidgetName, *PropertyName));
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Widgets);
	return true;
}

bool UXRFFBlueprintScripting::AddWidgetToPanel(UBlueprint* WidgetBlueprint, const FString& ParentName, UClass* WidgetClass, const FString& NewName, bool bIsVariable)
{
	UWidgetBlueprint* Widgets = Cast<UWidgetBlueprint>(WidgetBlueprint);
	if (!Widgets || !Widgets->WidgetTree || !WidgetClass || !WidgetClass->IsChildOf(UWidget::StaticClass()))
	{
		return Fail(TEXT("AddWidgetToPanel: not a widget blueprint, or the class is no widget"));
	}
	if (Widgets->WidgetTree->FindWidget(FName(*NewName)))
	{
		return true;
	}
	UPanelWidget* Parent = Cast<UPanelWidget>(FindDesignerWidget(WidgetBlueprint, ParentName, TEXT("AddWidgetToPanel")));
	if (!Parent)
	{
		return Fail(FString::Printf(TEXT("AddWidgetToPanel: %s is no panel in %s"), *ParentName, *Widgets->GetName()));
	}
	Widgets->Modify();
	Widgets->WidgetTree->Modify();
	Parent->Modify();
	UWidget* Widget = Widgets->WidgetTree->ConstructWidget<UWidget>(WidgetClass, FName(*NewName));
	Widget->bIsVariable = bIsVariable;
	Parent->AddChild(Widget);
	Widgets->OnVariableAdded(Widget->GetFName());
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Widgets);
	return true;
}

bool UXRFFBlueprintScripting::RemoveWidget(UBlueprint* WidgetBlueprint, const FString& WidgetName)
{
	UWidget* Widget = FindDesignerWidget(WidgetBlueprint, WidgetName, TEXT("RemoveWidget"));
	if (!Widget)
	{
		return false;
	}
	UWidgetBlueprint* Widgets = Cast<UWidgetBlueprint>(WidgetBlueprint);
	TSet<UWidget*> ToDelete;
	ToDelete.Add(Widget);
	FWidgetBlueprintEditorUtils::DeleteWidgets(Widgets, ToDelete, FWidgetBlueprintEditorUtils::EDeleteWidgetWarningType::DeleteSilently);
	return Widgets->WidgetTree->FindWidget(FName(*WidgetName)) == nullptr;
}

bool UXRFFBlueprintScripting::RenameWidget(UBlueprint* WidgetBlueprint, const FString& OldName, const FString& NewName)
{
	UWidget* Widget = FindDesignerWidget(WidgetBlueprint, OldName, TEXT("RenameWidget"));
	if (!Widget)
	{
		return false;
	}
	if (!FWidgetBlueprintOperationUtils::RenameWidget(Cast<UWidgetBlueprint>(WidgetBlueprint), Widget, NewName) || Widget->GetName() != NewName)
	{
		return Fail(FString::Printf(TEXT("RenameWidget: %s could not become %s (now %s)"), *OldName, *NewName, *Widget->GetName()));
	}
	return true;
}

FString UXRFFBlueprintScripting::GetSlotProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName)
{
	FString Value;
	UWidget* Widget = FindDesignerWidget(WidgetBlueprint, WidgetName, TEXT("GetSlotProperty"));
	UPanelSlot* Slot = Widget ? Widget->Slot : nullptr;
	const FProperty* Property = Slot ? Slot->GetClass()->FindPropertyByName(FName(*PropertyName)) : nullptr;
	if (Property)
	{
		Property->ExportTextItem_InContainer(Value, Slot, nullptr, Slot, PPF_None);
	}
	return Value;
}

bool UXRFFBlueprintScripting::SetSlotProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName, const FString& Value)
{
	UWidget* Widget = FindDesignerWidget(WidgetBlueprint, WidgetName, TEXT("SetSlotProperty"));
	UPanelSlot* Slot = Widget ? Widget->Slot : nullptr;
	if (!Slot)
	{
		return Fail(FString::Printf(TEXT("SetSlotProperty: %s has no slot"), *WidgetName));
	}
	FProperty* Property = Slot->GetClass()->FindPropertyByName(FName(*PropertyName));
	if (!Property)
	{
		return Fail(FString::Printf(TEXT("SetSlotProperty: %s has no slot property %s"), *Slot->GetClass()->GetName(), *PropertyName));
	}
	Slot->Modify();
	if (!Property->ImportText_InContainer(*Value, Slot, Slot, PPF_None))
	{
		return Fail(FString::Printf(TEXT("SetSlotProperty: %s.%s rejected %s"), *WidgetName, *PropertyName, *Value));
	}
	Slot->SynchronizeProperties();
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
	return true;
}

bool UXRFFBlueprintScripting::RemoveEventInput(UBlueprint* Blueprint, FName EventName, FName PinName)
{
	UK2Node_CustomEvent* Event = Blueprint ? FindCustomEvent(Blueprint, EventName) : nullptr;
	if (!Event)
	{
		return Fail(FString::Printf(TEXT("RemoveEventInput: %s has no custom event %s"), Blueprint ? *Blueprint->GetName() : TEXT("null"), *EventName.ToString()));
	}
	if (!Event->UserDefinedPinExists(PinName))
	{
		return Fail(FString::Printf(TEXT("RemoveEventInput: %s has no input %s"), *EventName.ToString(), *PinName.ToString()));
	}
	Event->Modify();
	Event->RemoveUserDefinedPinByName(PinName);
	Event->ReconstructNode();
	FBlueprintEditorUtils::RefreshAllNodes(Blueprint);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return !Event->UserDefinedPinExists(PinName);
}

TArray<FString> UXRFFBlueprintScripting::DescribeLandscapeGrass(ALandscapeProxy* Proxy)
{
	TArray<FString> Out;
	if (!Proxy)
	{
		Fail(TEXT("DescribeLandscapeGrass: no landscape"));
		return Out;
	}
	for (ULandscapeComponent* Component : Proxy->LandscapeComponents)
	{
		if (!Component)
		{
			continue;
		}
		const FLandscapeComponentGrassData& Grass = Component->GrassData.Get();
		Out.Add(FString::Printf(TEXT("%s|%d,%d|%d|%d|%d|%d"), *Component->GetName(), Component->GetSectionBase().X, Component->GetSectionBase().Y,
			Component->IsRegistered() ? 1 : 0, Component->CanRenderGrassMap() ? 1 : 0, Grass.NumElements,
			Grass.GenerationHash == Component->ComputeGrassMapGenerationHash() ? 1 : 0));
	}
	return Out;
}

int32 UXRFFBlueprintScripting::BuildLandscapeGrassMaps(ALandscapeProxy* Proxy)
{
	if (!Proxy)
	{
		Fail(TEXT("BuildLandscapeGrassMaps: no landscape"));
		return -1;
	}
	Proxy->BuildGrassMaps();
	return Proxy->GetOutdatedGrassMapCount();
}

bool UXRFFBlueprintScripting::AddLandscapeTargetLayer(ALandscapeProxy* Proxy, FName Name, ULandscapeLayerInfoObject* LayerInfo)
{
	if (!Proxy || !LayerInfo || Name.IsNone())
	{
		return Fail(TEXT("AddLandscapeTargetLayer: landscape, name and layer info are required"));
	}
	if (Proxy->HasTargetLayer(Name))
	{
		return true;
	}
	Proxy->Modify();
	FLandscapeTargetLayerSettings Settings;
	Settings.LayerInfoObj = LayerInfo;
	Proxy->AddTargetLayer(Name, Settings, true);
	if (ULandscapeInfo* Info = Proxy->GetLandscapeInfo())
	{
		Info->UpdateLayerInfoMap(Proxy);
	}
	return Proxy->HasTargetLayer(Name);
}

bool UXRFFBlueprintScripting::SyncSkeletonRefPoseFromMesh(USkeletalMesh* Mesh)
{
	USkeleton* Skeleton = Mesh ? Mesh->GetSkeleton() : nullptr;
	if (!Skeleton)
	{
		return Fail(TEXT("SyncSkeletonRefPoseFromMesh: mesh with a skeleton is required"));
	}
	Skeleton->Modify();
	Skeleton->UpdateReferencePoseFromMesh(Mesh);
	Skeleton->MarkPackageDirty();
	return true;
}

TArray<FString> UXRFFBlueprintScripting::DescribeViewports()
{
	TArray<FString> Out;
	if (!GEditor)
	{
		return Out;
	}
	int32 Index = 0;
	for (FEditorViewportClient* Client : GEditor->GetAllViewportClients())
	{
		if (!Client)
		{
			continue;
		}
		FIntPoint Offset, Size;
		Client->GetViewportDimensions(Offset, Size);
		UWorld* World = Client->GetWorld();
		Out.Add(FString::Printf(TEXT("%d|%s|%d|%d|%d|%dx%d|%s|%d"), Index++, World ? *World->GetName() : TEXT("none"),
			Client->IsPerspective() ? 1 : 0, Client->IsVisible() ? 1 : 0, Client->IsRealtime() ? 1 : 0, Size.X, Size.Y,
			*Client->GetRealtimeOverrideMessage().ToString(), Client->IsLevelEditorClient() ? 1 : 0));
	}
	return Out;
}

int32 UXRFFBlueprintScripting::SetLevelViewportsRealtime(bool bRealtime)
{
	int32 Count = 0;
	if (!GEditor)
	{
		return Count;
	}
	for (FLevelEditorViewportClient* Client : GEditor->GetLevelViewportClients())
	{
		if (!Client)
		{
			continue;
		}
		while (Client->IsRealtimeOverrideSet() && Client->PopRealtimeOverride())
		{
		}
		Client->SetRealtime(bRealtime);
		Client->Invalidate();
		++Count;
	}
	return Count;
}

bool UXRFFBlueprintScripting::SetMaterialCommentSize(UMaterialExpressionComment* Comment, int32 Width, int32 Height)
{
	if (!Comment)
	{
		return Fail(TEXT("SetMaterialCommentSize: no comment"));
	}
	Comment->Modify();
	Comment->SizeX = Width;
	Comment->SizeY = Height;
	return true;
}
