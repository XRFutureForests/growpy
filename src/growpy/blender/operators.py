"""Blender operators for GrowPy Nanite export addon."""

from __future__ import annotations

from pathlib import Path

import bpy

from . import grove_extract, twig_converter, usd_export


def _sanitize_identifier(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch.lower())
        elif ch in (" ", "-"):
            out.append("_")
    clean = "".join(out).strip("_")
    return clean or "tree"


def _twig_face_types(model) -> dict[int, str]:
    type_map: dict[int, str] = {}
    type_attrs = ["twig_long", "twig_short", "twig_upward", "twig_dead"]
    for twig_type in type_attrs:
        attr_name = f"face_attribute_{twig_type}"
        if not hasattr(model, attr_name):
            continue
        values = getattr(model, attr_name)
        for i, v in enumerate(values):
            if v > 0 and i not in type_map:
                type_map[i] = twig_type
    return type_map


def _extract_twig_placements(model) -> dict[str, list[dict]]:
    placements: dict[str, list[dict]] = {
        "twig_long": [],
        "twig_short": [],
        "twig_upward": [],
        "twig_dead": [],
    }

    if not (
        hasattr(model, "get_twig_locations")
        and hasattr(model, "get_twig_directions")
        and hasattr(model, "faces")
    ):
        return placements

    loc = model.get_twig_locations()
    dirs = model.get_twig_directions()
    orientations = (
        model.get_twig_orientations() if hasattr(model, "get_twig_orientations") else []
    )
    if not loc or not dirs:
        return placements

    num_twigs = len(loc) // 3
    twig_idx = 0
    face_to_type = _twig_face_types(model)
    bone_ids = getattr(model, "point_attribute_bone_id", [])

    for face_idx, face in enumerate(model.faces):
        twig_type = face_to_type.get(face_idx)
        if twig_type is None:
            continue
        if twig_idx >= num_twigs:
            break

        base = twig_idx * 3
        position = (loc[base], loc[base + 1], loc[base + 2])
        normal = (dirs[base], dirs[base + 1], dirs[base + 2])

        if orientations and base + 2 < len(orientations):
            orientation = (
                orientations[base],
                orientations[base + 1],
                orientations[base + 2],
            )
        else:
            orientation = (0.0, 0.0, 1.0)

        bone_id = None
        if bone_ids:
            counts: dict[int, int] = {}
            for vid in face:
                if vid < len(bone_ids):
                    b = int(bone_ids[vid])
                    counts[b] = counts.get(b, 0) + 1
            if counts:
                bone_id = max(counts.items(), key=lambda kv: kv[1])[0]

        placements[twig_type].append(
            {
                "position": position,
                "normal": normal,
                "orientation": orientation,
                "scale": 1.0,
                "bone_id": bone_id,
            }
        )
        twig_idx += 1

    return placements


def _find_layer_collection(layer_collection, name: str):
    if layer_collection.collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = _find_layer_collection(child, name)
        if found is not None:
            return found
    return None


class GROWPY_OT_SelectGroveCollection(bpy.types.Operator):
    bl_idname = "growpy.select_grove_collection"
    bl_label = "Select Grove Collection"
    bl_options = {"REGISTER", "UNDO"}

    collection_name: bpy.props.EnumProperty(
        name="Grove Collection",
        items=lambda self, context: [
            (c.name, c.name, "") for c in grove_extract.find_grove_collections()
        ],
    )

    @classmethod
    def poll(cls, context):
        return bool(grove_extract.find_grove_collections())

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        target = _find_layer_collection(
            context.view_layer.layer_collection, self.collection_name
        )
        if target is None:
            self.report({"ERROR"}, "Could not find layer collection")
            return {"CANCELLED"}
        context.view_layer.active_layer_collection = target
        self.report({"INFO"}, f"Active collection set to: {self.collection_name}")
        return {"FINISHED"}


class GROWPY_OT_ExportNaniteAssembly(bpy.types.Operator):
    bl_idname = "growpy.export_nanite_assembly"
    bl_label = "Export Nanite Assembly"
    bl_description = (
        "Export selected Grove collection to USD Nanite Assembly. "
        "Requires a valid Grove collection with Build run; for skeletal export "
        "uses Grove core skeleton data for USD skinning and does not create a Blender armature."
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        collection = grove_extract.get_active_grove_collection()
        if collection is None:
            return False

        addon = context.preferences.addons.get(__package__)
        if addon is None:
            return False

        prefs = addon.preferences
        if not getattr(prefs, "strict_grove_requirements", True):
            return True

        preflight = grove_extract.preflight_export(
            collection=collection,
            require_skeletal=(prefs.mesh_type == "SKELETAL"),
            strict_requirements=True,
        )
        return preflight.ok

    def execute(self, context):
        addon = context.preferences.addons.get(__package__)
        if addon is None:
            self.report({"ERROR"}, "Addon preferences not found")
            return {"CANCELLED"}

        prefs = addon.preferences
        use_skeletal = prefs.mesh_type == "SKELETAL"
        output_dir = Path(bpy.path.abspath(prefs.output_directory))
        output_dir.mkdir(parents=True, exist_ok=True)

        collection = grove_extract.get_active_grove_collection()
        if collection is None:
            self.report({"ERROR"}, "No Grove collection selected")
            return {"CANCELLED"}

        preflight = grove_extract.preflight_export(
            collection=collection,
            require_skeletal=use_skeletal,
            strict_requirements=prefs.strict_grove_requirements,
        )
        for msg in preflight.warnings:
            self.report({"WARNING"}, msg)
        for msg in preflight.infos:
            self.report({"INFO"}, msg)
        if not preflight.ok:
            for msg in preflight.errors:
                self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        skeleton_defaults = grove_extract.GROVE_SKELETON_DEFAULTS

        try:
            extraction = grove_extract.extract_grove(
                collection=collection,
                skeleton_length=float(skeleton_defaults["length"]),
                skeleton_reduce=float(skeleton_defaults["reduce"]),
                skeleton_bias=float(skeleton_defaults["bias"]),
                skeleton_connected=bool(skeleton_defaults["connected"]),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to extract Grove data: {exc}")
            return {"CANCELLED"}

        twig_paths: dict[str, list[Path]] = {}
        if prefs.include_twigs and extraction.twig_blend_paths:
            try:
                twig_paths = twig_converter.convert_twig_sources(
                    twig_blend_paths=extraction.twig_blend_paths,
                    output_dir=output_dir / "twigs",
                    use_skeletal_mesh=use_skeletal,
                )
            except Exception as exc:
                self.report({"WARNING"}, f"Twig conversion failed: {exc}")
                twig_paths = {}

        species = _sanitize_identifier(extraction.species_name)
        trees_exported = 0

        for idx, tree_model in enumerate(extraction.trees):
            tree_num = idx + 1
            tree_key = f"{tree_num:04d}"
            bones_info = (
                extraction.bones_info_per_tree[idx]
                if idx < len(extraction.bones_info_per_tree)
                else None
            )

            tree_usd = output_dir / f"{species}_{tree_key}_stems.usda"
            ok_tree = usd_export.build_tree_mesh_usd(
                model=tree_model,
                output_path=tree_usd,
                species_name=extraction.species_name,
                tree_id=tree_key,
                bones_info=bones_info,
                include_skeleton=use_skeletal,
                junction_blend_distance=prefs.junction_blend_distance,
                bark_texture_path=extraction.bark_texture_path,
            )
            if not ok_tree:
                self.report({"WARNING"}, f"Tree export failed: {tree_usd.name}")
                continue

            twig_placements = (
                _extract_twig_placements(tree_model) if prefs.include_twigs else {}
            )

            assembly_usd = output_dir / f"{species}_{tree_key}_nanite_assembly.usda"
            ok_assembly = usd_export.create_nanite_assembly(
                tree_usd_path=tree_usd,
                output_path=assembly_usd,
                species_name=extraction.species_name,
                tree_id=tree_key,
                twig_usd_paths=twig_paths,
                twig_placements=twig_placements,
                use_skeletal_mesh=use_skeletal,
            )
            if not ok_assembly:
                self.report({"WARNING"}, f"Assembly export failed: {assembly_usd.name}")
                continue

            trees_exported += 1

        self.report(
            {"INFO"},
            f"Export complete: {trees_exported}/{len(extraction.trees)} trees written to {output_dir}",
        )
        return {"FINISHED"}


_classes = [
    GROWPY_OT_SelectGroveCollection,
    GROWPY_OT_ExportNaniteAssembly,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
