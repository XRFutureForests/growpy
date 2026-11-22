"""E144 editor-side: read the SHIPPED Greenleaf maple tree that the A/B export reproduces (Vol_4_Tree_E_v1_low): bounds, bones, T3D.
One mesh load (a Nanite build on a cold 5.9 cache). growpy-ue-session --run; output env PVE59_OUT / gvref/probe.json."""
import json
import os
import traceback

import unreal

OUT = os.path.join(os.environ.get("PVE59_OUT", "data/output/pve59_extract/raw"), "gvref")
os.makedirs(OUT, exist_ok=True)
P = "/Game/GVBroadleafPresets/Meshes/Trees/Maple/SK_GV_Maple_Vol_4_Tree_E_v1_low"
res = {}
try:
    a = unreal.load_asset(P)
    b = a.get_bounds()
    f = os.path.join(OUT, "shipped.t3d")
    task = unreal.AssetExportTask()
    task.object, task.filename, task.exporter = a, f, unreal.ObjectExporterT3D()
    task.automated, task.prompt, task.replace_identical = True, False, True
    unreal.Exporter.run_asset_export_task(task)
    pose = unreal.AnimPoseExtensions.get_reference_pose(a.skeleton)
    names = unreal.AnimPoseExtensions.get_bone_names(pose)
    res[P] = {"origin": [b.origin.x, b.origin.y, b.origin.z], "extent": [b.box_extent.x, b.box_extent.y, b.box_extent.z], "t3d": f,
              "bones": [[str(n)] + [getattr(unreal.AnimPoseExtensions.get_bone_pose(pose, n, unreal.AnimPoseSpaces.WORLD).translation, k) for k in "xyz"] for n in names]}
except Exception:
    res["error"] = traceback.format_exc()[-500:]
with open(os.path.join(OUT, "probe.json"), "w", encoding="utf-8") as fh:
    json.dump(res, fh)
print("PVE59_GVREF_DONE", list(res))
