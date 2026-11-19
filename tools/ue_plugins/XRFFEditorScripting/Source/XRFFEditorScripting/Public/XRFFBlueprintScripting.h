// Editor-only blueprint edits that UE 5.8's BlueprintEditorLibrary and the MCP BlueprintTools do not offer.
// Python: unreal.XRFFBlueprintScripting.<snake_case name>(...). Every function returns false (and logs why) instead
// of asserting, compiles nothing unless it says so, and leaves saving to the caller.
#pragma once

#include "CoreMinimal.h"
#include "EdGraph/EdGraphPin.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "XRFFBlueprintScripting.generated.h"

class ALandscapeProxy;
class USkeletalMesh;
class ULandscapeLayerInfoObject;
class UBlueprint;
class UEdGraph;
class UMaterialExpressionComment;
class UEdGraphNode;
class UUserDefinedEnum;
class UUserDefinedStruct;

USTRUCT(BlueprintType)
struct FXRFFStructField
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XRFF")
	FString Name;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XRFF")
	FEdGraphPinType Type;

	/** Default as export text ("" keeps the type's default). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XRFF")
	FString DefaultValue;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XRFF")
	FString Tooltip;
};

UCLASS()
class UXRFFBlueprintScripting : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Set or clear Pure on a blueprint function (as the details panel's checkbox does). Making a function pure
	 * removes the exec pins of its call nodes; in every caller blueprint the call is bypassed (what ran into it now
	 * runs into what followed it). Callers are searched in Blueprint itself and in CallerBlueprints. Going back to
	 * impure leaves the callers unwired (reported). Compiles the changed blueprints.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool SetFunctionPure(UBlueprint* Blueprint, FName FunctionName, bool bPure, const TArray<UBlueprint*>& CallerBlueprints, FString& OutReport);

	/** Rename a member variable, event dispatcher or component variable with all its references in Blueprint. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool RenameMember(UBlueprint* Blueprint, FName OldName, FName NewName);

	/**
	 * Rename a function graph or a custom event. Call nodes and Create Event nodes in Blueprint and in
	 * CallerBlueprints are re-pointed; string pins that still hold the old name (Set Timer by Function Name and
	 * the like) are listed in OutReport, not changed.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool RenameFunctionOrEvent(UBlueprint* Blueprint, FName OldName, FName NewName, const TArray<UBlueprint*>& CallerBlueprints, FString& OutReport);

	/** Rename a parameter of a function or custom event, on its entry/result node and on every call node in Blueprint and CallerBlueprints. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool RenameParameter(UBlueprint* Blueprint, FName FunctionName, FName OldName, FName NewName, const TArray<UBlueprint*>& CallerBlueprints);

	/**
	 * One line per member variable declared in Blueprint:
	 * name|category|type|flags|tooltip, type as category/subcategory object, flags from InstanceEditable, ExposeOnSpawn,
	 * ReadOnly, Private, Container (Array/Set/Map), Delegate.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static TArray<FString> DescribeVariables(UBlueprint* Blueprint);

	/** Pin type of a member variable (empty type if missing), to recreate it in another blueprint. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static FEdGraphPinType GetVariablePinType(UBlueprint* Blueprint, FName VariableName);

	/** Tooltip of a member variable ("" clears it). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool SetVariableTooltip(UBlueprint* Blueprint, FName VariableName, const FString& Tooltip);

	/** Tooltip and, if not empty, category of a function graph. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool SetFunctionDescription(UBlueprint* Blueprint, FName FunctionName, const FString& Tooltip, const FString& Category);

	/**
	 * Comment box around the named nodes (object names as in the graph, e.g. K2Node_CallFunction_12), padded.
	 * An existing comment whose text starts with the same first line is replaced, so the call can be repeated.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static UEdGraphNode* AddCommentAroundNodes(UEdGraph* Graph, const TArray<FString>& NodeNames, const FString& Text, FLinearColor Color, float Padding = 40.f);

	/** Comment box at a fixed position and size; same replace rule as AddCommentAroundNodes. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static UEdGraphNode* AddCommentBox(UEdGraph* Graph, const FString& Text, int32 X, int32 Y, int32 Width, int32 Height, FLinearColor Color);

	/** One line per node: name|title|x|y|width|height|class. Width and height are 0 until the graph was drawn once. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static TArray<FString> DescribeGraph(UEdGraph* Graph);

	/** Copy-paste text of the named nodes (all nodes if NodeNames is empty). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static FString ExportNodes(UEdGraph* Graph, const TArray<FString>& NodeNames);

	/** Paste nodes from ExportNodes text, moved by (OffsetX, OffsetY); returns the new node names. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static TArray<FString> ImportNodes(UEdGraph* Graph, const FString& Text, int32 OffsetX, int32 OffsetY);

	/** Delete the named nodes (entry and result nodes are refused). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static int32 DeleteNodes(UEdGraph* Graph, const TArray<FString>& NodeNames);

	/**
	 * Create the user-defined enum at PackagePath (e.g. /Game/00_XRFF/10_Levels/E_SiteLoadState) or bring an existing
	 * one to exactly these entries, in this order. Existing entries are renamed in place, so values keep their index.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Assets")
	static UUserDefinedEnum* CreateOrUpdateEnum(const FString& PackagePath, const TArray<FString>& DisplayNames, const FString& Description);

	/**
	 * Create the user-defined struct at PackagePath or add the missing fields to an existing one (matched by name;
	 * a field whose type differs is reported, not changed). Fields not in the list are kept.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Assets")
	static UUserDefinedStruct* CreateOrUpdateStruct(const FString& PackagePath, const TArray<FXRFFStructField>& Fields, const FString& Description);

	/** Pin type of an enum (for BlueprintEditorLibrary.add_member_variable, struct fields and parameters). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static FEdGraphPinType GetEnumPinType(UEnum* Enum);

	/** Add an input (or output) parameter of any pin type to a function graph or custom event. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool AddParameter(UBlueprint* Blueprint, FName FunctionName, FName ParamName, const FEdGraphPinType& Type, bool bOutput);

	/** Create a blueprint interface (Kind "Interface"), function library ("FunctionLibrary") or normal blueprint of ParentClass ("Normal"). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Assets")
	static UBlueprint* CreateBlueprintAsset(const FString& PackagePath, UClass* ParentClass, const FString& Kind);

	/**
	 * Fix Up Redirectors under the given content paths (as the Content Browser command): re-save every referencer
	 * with the new path, then delete the redirectors that no longer have a referencer. Returns the redirectors found.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Assets")
	static int32 FixUpRedirectors(const TArray<FString>& ContentPaths);

	/**
	 * In a function-library function graph: connect the entry's hidden __WorldContext pin to every unconnected
	 * world-context input (WorldContextObject, __WorldContext) of the graph's nodes. Returns the links made.
	 */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static int32 WireWorldContext(UEdGraph* Graph);

	/** Set an input pin's default object or class (a class literal on Get Actor Of Class, an asset on a pin). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool SetPinDefaultObject(UEdGraph* Graph, const FString& NodeName, FName PinName, UObject* Value);

	/** Set an input pin's default value from its string form ("Hidden", "2.0", "(R=1,G=0,B=0,A=1)"). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool SetPinDefaultValue(UEdGraph* Graph, const FString& NodeName, FName PinName, const FString& Value);

	/** Connect NodeA.PinA to NodeB.PinB through the graph schema (type-checked; an exec output or a data input keeps one link). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool LinkPins(UEdGraph* Graph, const FString& NodeA, FName PinA, const FString& NodeB, FName PinB);

	/** Remove every link of Node.Pin. Returns the number of links removed (-1 if the pin is missing). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static int32 BreakPinLinks(UEdGraph* Graph, const FString& NodeName, FName PinName);

	/** Let Blueprint implement the interface (adds the interface's function stubs). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool ImplementInterface(UBlueprint* Blueprint, UClass* InterfaceClass);

	/** The editor's Refresh All Nodes: every node is rebuilt against the current types (after a variable type change). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool RefreshAllNodes(UBlueprint* Blueprint);

	/** One line per widget in a widget blueprint's designer tree: name|class|variable (1/0)|parent. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static TArray<FString> ListWidgets(UBlueprint* WidgetBlueprint);

	/** A property of a widget in the designer tree as export text ("" if the widget or property is missing). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static FString GetWidgetProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName);

	/** Set a property of a widget in the designer tree from export text (e.g. bIsVariable True, a Text, a Visibility). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static bool SetWidgetProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName, const FString& Value);

	/** One line per property binding of a widget blueprint: widget|property|function or source property|Function/Property. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static TArray<FString> ListWidgetBindings(UBlueprint* WidgetBlueprint);

	/** Remove the property binding of PropertyName on the widget WidgetName. The bound function itself stays. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static bool RemoveWidgetBinding(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName);

	/** Add a widget of WidgetClass named NewName as the last child of the panel ParentName in the designer tree (true if it exists already). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static bool AddWidgetToPanel(UBlueprint* WidgetBlueprint, const FString& ParentName, UClass* WidgetClass, const FString& NewName, bool bIsVariable);

	/** Remove the designer widget WidgetName and its children (and their bindings), even when graphs reference it. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static bool RemoveWidget(UBlueprint* WidgetBlueprint, const FString& WidgetName);

	/** Rename the designer widget OldName to NewName as the designer does (variable references, bindings, animations). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static bool RenameWidget(UBlueprint* WidgetBlueprint, const FString& OldName, const FString& NewName);

	/** A property of the designer widget's panel slot (Row, Column, Padding, ...) as export text; empty if none. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static FString GetSlotProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName);

	/** Set a property of the designer widget's panel slot from export text. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Widget")
	static bool SetSlotProperty(UBlueprint* WidgetBlueprint, const FString& WidgetName, const FString& PropertyName, const FString& Value);

	/** Remove the input PinName of the custom event EventName (its user-defined pin), then refresh the blueprint's nodes. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Blueprint")
	static bool RemoveEventInput(UBlueprint* Blueprint, FName EventName, FName PinName);

	/** Per landscape component: name|section base|registered|can render grass map|grass elements (-1 = none)|grass data up to date. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Landscape")
	static TArray<FString> DescribeLandscapeGrass(ALandscapeProxy* Proxy);

	/** Build the proxy's outdated grass maps now (as an editor save does) and return how many are still outdated. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Landscape")
	static int32 BuildLandscapeGrassMaps(ALandscapeProxy* Proxy);

	/** Add a paint target layer Name with LayerInfo to the landscape (the TargetLayers map is read-only to scripts). True if it exists afterwards. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Landscape")
	static bool AddLandscapeTargetLayer(ALandscapeProxy* Proxy, FName Name, ULandscapeLayerInfoObject* LayerInfo);

	/** Copy the mesh's reference pose into its Skeleton asset (the skeleton editor's Update Reference Pose). Dynamic Wind
	 *  reads bone orientation from the skeleton, so call this after re-orienting bones with SkeletonModifier. Marks the skeleton dirty. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Skeleton")
	static bool SyncSkeletonRefPoseFromMesh(USkeletalMesh* Mesh);

	/** Every editor viewport: index|world|perspective|visible|realtime|size|realtime override message. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Viewport")
	static TArray<FString> DescribeViewports();

	/** Realtime on (or off) for every level viewport of the editor world, removing the overrides that block it. Returns how many. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Viewport")
	static int32 SetLevelViewportsRealtime(bool bRealtime);

	/** Size of a material comment box (SizeX/SizeY are not exposed to Python). */
	UFUNCTION(BlueprintCallable, Category = "XRFF|Material")
	static bool SetMaterialCommentSize(UMaterialExpressionComment* Comment, int32 Width, int32 Height);
};
