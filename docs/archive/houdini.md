from pxr import Sdf
import hou
# 1) Get your stage
# If you're running inside a LOP node, this works:
stage = hou.pwd().editableStage()
# If you're in a generic Python Shell, use the LOP node path instead:
# stage = hou.node("/stage/your_lop_node").editableStage()
primPath = "/Tree_assembly" # <-- change if needed
prim = stage.GetPrimAtPath(primPath)
if not prim:
raise RuntimeError(f"Prim not found: {primPath}")
# 2) Work at the Sdf layer level so apiSchemas goes in the PRIM HEADER
layer = stage.GetEditTarget().GetLayer()
# Make sure there is a prim spec in this layer
ps = layer.GetPrimAtPath(primPath)
if ps is None:
Sdf.CreatePrimInLayer(layer, primPath)
ps = layer.GetPrimAtPath(primPath)
# If someone accidentally authored an *attribute* called apiSchemas, remove it
if prim.HasAttribute("apiSchemas"):
prim.RemoveProperty("apiSchemas")
# 3) Add NaniteAssemblyRootAPI to apiSchemas (header metadata)
existing = ps.GetInfo("apiSchemas")
tokens = []
if isinstance(existing, Sdf.TokenListOp):
tokens = list(existing.ApplyOperations([]))
elif isinstance(existing, (list, tuple)):
tokens = [str(t) for t in existing]
if "NaniteAssemblyRootAPI" not in tokens:
tokens.append("NaniteAssemblyRootAPI")
ps.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(tokens))
ps.SetInfo("kind", "assembly") # header too
# 4) Unreal needs this token attribute as well
attr = prim.GetAttribute("unreal:naniteAssembly:meshType")
if not attr:
attr = prim.CreateAttribute("unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token,
custom=True)
attr.Set("staticMesh") # or "skeletalMesh"
# (Optional) sanity check in-memory text
print(stage.GetRootLayer().ExportToString())






from pxr import Sdf
import hou
# Use the current LOP node's edit target
stage = hou.pwd().editableStage()
layer = stage.GetEditTarget().GetLayer()
paths = [
"/Tree_assembly/LargeBranchA",
"/Tree_assembly/LargeBranchB",
"/Tree_assembly/MediumBranchA",
"/Tree_assembly/MediumBranchB",
"/Tree_assembly/SmallBranchA",
"/Tree_assembly/SmallBranchB",
"/Tree_assembly/Trunk",
]
def _get_api_tokens(ps):
existing = ps.GetInfo("apiSchemas")
if isinstance(existing, Sdf.TokenListOp):
return list(existing.ApplyOperations([]))
elif isinstance(existing, (list, tuple)):
return [str(t) for t in existing]
return []
def add_external_ref(layer, primPath, set_mesh_type=True):
ps = layer.GetPrimAtPath(primPath)
if ps is None:
Sdf.CreatePrimInLayer(layer, primPath)
ps = layer.GetPrimAtPath(primPath)
# Add NaniteAssemblyExternalRefAPI to the prim header
tokens = _get_api_tokens(ps)
if "NaniteAssemblyExternalRefAPI" not in tokens:
tokens.append("NaniteAssemblyExternalRefAPI")
ps.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(tokens))
# Optional: set meshType token attribute = "staticMesh"
if set_mesh_type:
attr = ps.attributes.get("unreal:naniteAssembly:meshType")
if attr is None:
attr = Sdf.AttributeSpec(ps, "unreal:naniteAssembly:meshType",
Sdf.ValueTypeNames.Token)
attr.default = "staticMesh"
for p in paths:
add_external_ref(layer, p)
print("Applied NaniteAssemblyExternalRefAPI to", len(paths), "prims.")