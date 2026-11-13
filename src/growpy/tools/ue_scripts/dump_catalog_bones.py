"""Dump the Bones count of every catalog skeletal mesh to a JSON file.

Output: <project>/Saved/growpy_catalog_bones.json.

For ``growpy-tree-catalog build --bones`` and ``growpy-export-budget --bones``:
``{"SK_NorwaySpruce_r07_h20m": 2307, ...}``. Reads the asset registry tag only,
so no mesh is loaded (loading a catalog mesh can rebuild its Nanite data).
Run in the editor through remote Python (growpy.io.unreal.ue_remote.run_file).
"""

import json
import os

import unreal

ROOT = "/Game/Generated/Trees/Catalog"
registry = unreal.AssetRegistryHelpers.get_asset_registry()
flt = unreal.ARFilter(
    package_paths=[ROOT],
    class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "SkeletalMesh")],
    recursive_paths=True,
)
bones, untagged = {}, []
for data in registry.get_assets(flt):
    value = data.get_tag_value("Bones")
    if value:
        bones[str(data.asset_name)] = int(value)
    else:
        untagged.append(str(data.asset_name))
out = os.path.join(unreal.Paths.project_saved_dir(), "growpy_catalog_bones.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(dict(sorted(bones.items())), fh, indent=1)
print(f"BONES {len(bones)} meshes -> {out}; {len(untagged)} without a Bones tag")
