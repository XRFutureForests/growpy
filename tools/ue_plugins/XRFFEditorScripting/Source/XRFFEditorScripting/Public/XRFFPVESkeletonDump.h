// PVE skeleton read-out (XRFF-655, register E118, 2026-11-19): run a Procedural Vegetation graph through our own PCG
// execution source with inspection on (the route of PVE's own scenario tests), then write one node's growth collection
// as a growpy growth JSON that tree-structure's read_growth_json reads unchanged (fields agreed with the tree-structure lane):
//   points.positions [x, y, z] m, y-up ([X, Z, Y] / 100 of PVE's Z-up cm; a plain swap, as PVE's importer does)
//   points.attributes.budLateralMeristem [[r]] m (PVE point Scale / 100 = the radius before the mesh builder's
//     profile, DaVinci and min-radius passes; for an imported growpy tree this is the file's own value)
//   primitives.points: polylines parents first, trunk first; PVE point indices kept (a branch shares its parent's
//     attachment vertex, as in Grove files); branchNumber / branchParentNumber (trunk parent -1), branchOrder
//   metadata {source, asset, node, units, up, engine, points, branches, + the caller's fields}
// Python (unreal.XRFFPVESkeletonDump.<snake_case>): start_pve_run -> poll is_pve_run_generating from a ticker
// (never block the game thread) -> dump_pve_skeleton -> release_pve_run. Errors come back as text, nothing asserts.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "XRFFPVESkeletonDump.generated.h"

UCLASS()
class UXRFFPVESkeletonDump : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Start executing a PVE graph (a ProceduralVegetation asset or its graph) with inspection on. Returns the run
	 *  (kept alive until release_pve_run), or None with the reason in the log. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|PVE")
	static UObject* StartPVERun(UObject* ProceduralVegetationOrGraph);

	/** True while the run is still generating; poll from a ticker callback. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|PVE")
	static bool IsPVERunGenerating(UObject* Run);

	/** One line per node output pin that holds PVE data: "<node name> | <settings class> | <pin> | points N | branches M". */
	UFUNCTION(BlueprintCallable, Category = "XRFF|PVE")
	static TArray<FString> ListPVERunData(UObject* Run);

	/** Write the growth JSON of one node's output. Node: node name, node title or settings class name; empty = the node
	 *  that feeds the first mesh builder (the finished skeleton). ExtraMetadata: JSON members without braces, e.g.
	 *  "\"seed\": 7023, \"cycles\": 45, \"radius_convention\": \"growpy_profile_mean\"". Returns "" on success, else the error. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|PVE")
	static FString DumpPVESkeleton(UObject* Run, const FString& Node, const FString& OutPath, const FString& ExtraMetadata);

	/** Pine low-limb removal (register E124): on a finished run, read the input skeleton of the Manual Edit node `Node`
	 *  (node name or title; empty = the first PVManualEditSettings node), pick the first-order limbs attached below
	 *  CrownBaseM metres above the tree base (lowest first, at most MaxShare of all first-order limbs), and write their
	 *  points and those of their subtrees, by bud number, into the node's RemovedPoints, so PVE's own Manual Edit
	 *  removes them. A limb attached above the line keeps its whole subtree; each branch's first point (the attachment
	 *  vertex on its parent) is never marked, so the trunk stays whole. The graph is marked dirty; the caller saves it.
	 *  Returns "removed <k> of <n> first-order limbs below <h> m[, CAPPED at <share>]" or "ERROR: ...". */
	UFUNCTION(BlueprintCallable, Category = "XRFF|PVE")
	static FString MarkCrownBaseRemoval(UObject* Run, const FString& Node, float CrownBaseM, float MaxShare);

	/** Stop and forget a run. */
	UFUNCTION(BlueprintCallable, Category = "XRFF|PVE")
	static void ReleasePVERun(UObject* Run);
};
