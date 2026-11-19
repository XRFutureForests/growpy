# XRFFEditorScripting (Unreal Editor plugin)

Editor-only C++ plugin that gives Python access to what the engine's script API leaves out. Two function libraries:

- `UXRFFBlueprintScripting` (`unreal.XRFFBlueprintScripting`): blueprint edits (pure flags, member, event and pin
  renames, comment boxes, user-defined enums and structs, node copy between graphs, pin links), widget and landscape
  helpers.
- `UXRFFPVESkeletonDump` (`unreal.XRFFPVESkeletonDump`, XRFF-655): runs a Procedural Vegetation (PVE) graph on its own
  PCG execution source with inspection on, and writes one node's growth collection as a growpy growth JSON
  (positions in metres y-up, `budLateralMeristem` radius per point, polylines parents first with PVE's point indices,
  `branchNumber` / `branchParentNumber`, a `metadata` object). Python: `start_pve_run` -> poll
  `is_pve_run_generating` from a ticker callback -> `dump_pve_skeleton` -> `release_pve_run`; `list_pve_run_data`
  lists every node pin that holds PVE data.

## Engine and dependencies

- Unreal Engine 5.8 (built and tested on 5.8.4). Editor module only; not packaged into games.
- Plugin dependencies: PCG, ProceduralVegetationEditor (module `ProceduralVegetation`); module `Chaos` for the managed
  array collection.

## Build

The host project is Blueprint-only, so the plugin is built on its own and the binaries are copied in:

1. Close the editor of the project that uses the plugin.
2. `RunUAT BuildPlugin -Plugin=<path>\XRFFEditorScripting.uplugin -Package=<staging folder> -TargetPlatforms=Win64`
   (a short staging path avoids Windows path-length limits).
3. Copy `<staging folder>\Binaries` into the project's `Plugins\XRFFEditorScripting\Binaries` (keep the old ones
   until the editor has started once with the new build).

## Which copy is canonical

This folder is the canonical source (owner decision 2026-11-19). The plugin folder inside a project is a deployed
copy: change the source here first, then copy it into the project and rebuild. Binaries and `Intermediate/` are never
committed.
