"""Build the cached render data of every catalog tree, headless.

A catalog mesh re-saved after a content move (all 216 were, 2026-09-25, when the
tree content went to /Game/Generated/Trees) no longer matches its cached Nanite
and skeletal render data, so the first thing that loads it rebuilds it -- about
a minute per large tree. With ECOSENSE as the startup map that is PCG_Trees,
during editor start: the window stays on frame 0 for an hour or more. Loading
every mesh once here does the same builds without a frozen editor, writes them
to the derived-data cache, and the next editor start reads them back. Stopping
keeps every mesh finished so far; a rerun carries on with the rest.

Run with NO editor open on the project (both would build the same meshes):

    "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
        "D:/Unreal/XRFFL_Dev/XRFFL_Dev.uproject" -run=pythonscript
        -script="D:/Git/work/growpy/src/growpy/tools/ue_scripts/warm_catalog_cache.py"
        -unattended -nosplash -stdout -AllowStdOutLogVerbosity

Optional arguments go inside the -script string after the path:
``--limit N`` (first N meshes only) and ``--root /Game/...`` (repeatable).
Progress lines start with WARMCACHE. The commandlet exits 1 even on success:
the engine counts its own start-up errors (e.g. the r.Mobile.VirtualTextures
deprecation ensure) -- judge the run by the "WARMCACHE done" line.

A load returns before its mesh is built (the build is async), so after each
load the script finishes all pending mesh compilations: without that the loop
ends in a second and every tree builds at once during shutdown, all in memory
together (2026-09-25 test).
"""

import sys
import time

import unreal

DEFAULT_ROOTS = ("/Game/Assets/Trees/Catalog", "/Game/Generated/Trees/Catalog")
GC_EVERY = 4  # meshes between garbage collections; a large tree holds GBs
# Console commands the engine derives per asset type (Editor.Async%sCompilation...).
FINISH_ALL = (
    "Editor.AsyncSkinnedAssetCompilationFinishAll",
    "Editor.AsyncStaticMeshCompilationFinishAll",
)


def _args(argv):
    roots, limit = [], None
    it = iter(argv)
    for arg in it:
        if arg == "--root":
            roots.append(next(it))
        elif arg == "--limit":
            limit = int(next(it))
    return roots or list(DEFAULT_ROOTS), limit


def catalog_meshes(roots):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    found = []
    for root in roots:
        for data in registry.get_assets_by_path(root, recursive=True):
            if str(data.asset_class_path.asset_name) == "SkeletalMesh":
                found.append(str(data.package_name))
    return sorted(set(found))


def main():
    roots, limit = _args(sys.argv[1:])
    meshes = catalog_meshes(roots)
    if limit is not None:
        meshes = meshes[:limit]
    unreal.log(f"WARMCACHE {len(meshes)} catalog meshes under {roots}")
    start = time.time()
    for index, path in enumerate(meshes, 1):
        t0 = time.time()
        mesh = unreal.load_asset(path)
        for command in FINISH_ALL:
            unreal.SystemLibrary.execute_console_command(None, command)
        state = "missing" if mesh is None else "ok"
        del mesh
        seconds = time.time() - t0
        unreal.log(f"WARMCACHE {index}/{len(meshes)} {state} {path} {seconds:.0f}s")
        if index % GC_EVERY == 0:
            unreal.SystemLibrary.collect_garbage()
    minutes = (time.time() - start) / 60.0
    unreal.log(f"WARMCACHE done: {len(meshes)} meshes in {minutes:.0f} min")


main()
