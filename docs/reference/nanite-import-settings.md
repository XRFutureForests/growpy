# Nanite Import Settings for GrowPy Forests

How `[unreal]` settings in `unreal.toml` map to UE
[`MeshNaniteSettings`](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MeshNaniteSettings),
why each one matters for forest imports, and where the rationale comes from.

These settings are applied post-import in
[unreal_nanite_script.py:_configure_nanite_assembly](../src/growpy/io/unreal/unreal_nanite_script.py)
(injected as a preamble into batch scripts by
[`unreal_scripts.py`](../src/growpy/io/unreal/unreal_scripts.py))
on every assembly mesh produced by the pipeline.

## Why these settings matter

A growpy forest export typically produces hundreds to thousands of Nanite
assembly USDA files, each with one assembly mesh per tree plus shared twig
prototypes. Out-of-the-box UE Nanite defaults are tuned for hand-authored
hero meshes, not procedural batches — so the difference between defaults and
forest-tuned values can be 10–100x in build time, VRAM, and disk.

The two single biggest wins are:

1. **`fallback_target = "percent_triangles"`** — without this, UE may evaluate
   `fallback_percent_triangles` under the wrong heuristic (relative-error or
   "auto") and silently keep far more triangles than `0.01` implies. This is
   the most common reason "1% fallback" assemblies still cost a lot.
2. **Voxelize shape preservation** — switches the distance representation
   from triangles to voxels, eliminating the canopy-thinning failure mode of
   `PreserveArea` and removing LOD popping entirely. Required for the new
   skeletal-mesh wind path in UE 5.7+.

## Settings reference

| TOML key | UE property | Default | Why for forests |
|---|---|---|---|
| `nanite_fallback_percent` | `fallback_percent_triangles` | `0.01` | Fallback only renders when Nanite is unavailable (raytracing without Nanite RT, complex collision, mobile, editor "Nanite off"). 1% is plenty for those edge cases on a tree. |
| `nanite_fallback_target` | `fallback_target` | `"percent_triangles"` | **CRITICAL**. Forces the percent value above to actually apply. Alternatives: `"relative_error"` (use the relative-error knob below) or `"auto"`. |
| `nanite_fallback_relative_error` | `fallback_relative_error` | `1.0` | Only used when `fallback_target = "relative_error"`. Higher = coarser fallback. Try 2.0–4.0 if you switch heuristics. |
| `nanite_trim_relative_error` | `trim_relative_error` | `0.0` (auto) | Controls internal Nanite LOD hierarchy simplification. Epic recommends staying above `0.02`; `0.04` is a good default. Higher values reduce build + streaming size on organic meshes. |
| `nanite_target_residency_kb` | `target_minimum_residency_in_kb` | `0` | Minimum always-resident Nanite data per mesh. `0` = single page. Ideal for forests where most trees are far from camera at any moment. |
| `nanite_lerp_uvs` | `lerp_u_vs` | `true` | Required for textured meshes — prevents UV seam artifacts when Nanite simplifies. |
| `nanite_max_edge_length_factor` | `max_edge_length_factor` | `0.0` | Set > 0 (e.g. `1.0`) for skeletal-mesh wind animation to prevent oversimplification along bone-driven edges. Default `0` is fine for static trees. |
| `nanite_explicit_tangents` | `explicit_tangents` | `false` | Implicit tangents are smaller and faster to build. Only set `true` if a material specifically depends on baked tangents (rare for vegetation). |
| `nanite_position_precision` | `position_precision` | `-1` (auto) | Vertex position quantization. Lower = smaller. Trees tolerate aggressive precision well; `-1` lets UE choose per-mesh. |
| `nanite_normal_precision` | `normal_precision` | `-1` (auto) | Normal quantization. Vegetation usually tolerates coarse normals well. |
| `voxelization` | `shape_preservation = Voxelize` | `true` | The "right" shape preservation mode for foliage in UE 5.7+. Required for skeletal mesh wind. Adds import time but eliminates canopy thinning at distance. |

## Order of operations matters

In [`_configure_nanite_assembly`](../src/growpy/io/unreal/unreal_nanite_script.py),
properties are applied in this order:

1. `shape_preservation` → Voxelize
2. `fallback_target` → must be set **before** the percent value below
3. `fallback_percent_triangles` → applies under the heuristic chosen in step 2
4. `fallback_relative_error` → fallback in case heuristic is relative-error
5. `trim_relative_error` (only if > 0)
6. `target_minimum_residency_in_kb`
7. `lerp_u_vs`
8. `max_edge_length_factor` (only if > 0)
9. `explicit_tangents`
10. `position_precision` / `normal_precision` (only if ≥ 0)

## Quick recipes

**Fastest builds, smallest assets** (preview / iteration):

```toml
[unreal]
voxelization = false  # skip voxelization during testing
nanite_fallback_target = "percent_triangles"
nanite_fallback_percent = 0.01
nanite_trim_relative_error = 2.0
nanite_explicit_tangents = false
```

**Production quality** (default):

```toml
[unreal]
voxelization = true
nanite_fallback_target = "percent_triangles"
nanite_fallback_percent = 0.01
nanite_trim_relative_error = 0.04
nanite_target_residency_kb = 0
nanite_lerp_uvs = true
nanite_explicit_tangents = false
```

**With skeletal-mesh wind** (UE 5.7+ Dynamic Wind plugin):

```toml
[unreal]
voxelization = true
nanite_max_edge_length_factor = 1.0  # protect bone-driven edges
# everything else = production quality
```

## What we still rely on Voxelize for

From the Nanite Foliage docs and the Witcher 4 demo:

- **Canopy preservation** — `PreserveArea` "won't help much" for tree canopies
  built from many tiny leaf meshes; voxels are the working approach.
- **Wind animation path** — voxelize is required to enable the new
  skeletal-mesh wind / Dynamic Wind plugin pipeline.
- **Performance** — voxel rasterization avoids the alpha-mask overdraw that
  killed traditional foliage; the demo measured ~50 fps voxel vs ~34 fps
  preserve-area on identical scenes.

## Limitations to know

- **Ray-traced shadows** with voxelized Nanite foliage currently fall back to
  the fallback mesh, not the assembly. Yet another reason to keep the fallback
  *small but not zero*.
- **WPO wind animation** does not survive voxelization — that's why the wind
  pipeline moved to skeletal-mesh + Dynamic Wind in UE 5.7.
- **Alpha masking** in materials adds overdraw and "potentially expensive
  mask function" cost; prefer opaque-with-geometric-leaves where possible.

## USD authoring side (for reference)

The export side already produces files compatible with UE 5.7+ Nanite
Assemblies, using three USD schemas:

- `NaniteAssemblyRootAPI` — marks the assembly root and `meshType`
  (`staticMesh` / `skeletalMesh`)
- `NaniteAssemblyExternalRefAPI` — references pre-imported UE mesh assets
- `NaniteAssemblySkelBindingAPI` — binds parts to skeleton joints (skeletal
  assemblies only)

PointInstancer prims are the preferred way to scatter prototypes — Epic notes
this is "more efficient because it reduces the complexity of the stage"
versus native USD instancing. See
[nanite-assembly-readme.md](../internals/nanite-assembly-readme.md) for the export side.

## Sources

- [Nanite Technical Details](https://dev.epicgames.com/documentation/unreal-engine/nanite-technical-details#fallbackmesh)
- [Working with Nanite-Enabled Content](https://dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content)
- [Nanite in Unreal Engine](https://dev.epicgames.com/documentation/unreal-engine/nanite-in-unreal-engine)
- [Nanite Foliage](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-foliage)
- [Procedural Vegetation Editor (PVE)](https://dev.epicgames.com/documentation/unreal-engine/procedural-vegetation-editor-pve-in-unreal-engine)
- [MeshNaniteSettings Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MeshNaniteSettings)
- [Nanite Assemblies in USD: Scene Structure](https://dev.epicgames.com/community/learning/tutorials/7O3z/unreal-engine-nanite-assemblies-in-usd-scene-structure-part-1-of-2)
- [Nanite Assemblies in USD: Houdini Tutorials](https://dev.epicgames.com/community/learning/tutorials/1mxR/unreal-engine-nanite-assemblies-in-usd-houdini-tutorials-part-2)
