"""UI panels for GrowPy Nanite export addon."""

from __future__ import annotations

import bpy

from . import grove_extract


class GROWPY_PT_NaniteExport(bpy.types.Panel):
    bl_label = "GrowPy Nanite Export"
    bl_idname = "GROWPY_PT_nanite_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GrowPy"

    @classmethod
    def poll(cls, context):
        return bool(grove_extract.find_grove_collections())

    def draw(self, context):
        layout = self.layout

        addon = context.preferences.addons.get(__package__)
        if addon is None:
            layout.label(text="Addon preferences unavailable", icon="ERROR")
            return
        prefs = addon.preferences

        collection = grove_extract.get_active_grove_collection()
        box = layout.box()
        box.label(text="Grove Source", icon="OUTLINER_COLLECTION")

        if collection is None:
            box.label(text="No active Grove collection", icon="ERROR")
        else:
            species = grove_extract.get_species_name_from_collection(collection)
            box.label(text=f"Collection: {collection.name}")
            box.label(text=f"Species: {species}")
            box.label(text=f"Objects: {len(collection.objects)}")

            preflight = grove_extract.preflight_export(
                collection=collection,
                require_skeletal=(prefs.mesh_type == "SKELETAL"),
                strict_requirements=prefs.strict_grove_requirements,
            )
            req_box = layout.box()
            req_box.label(
                text="Preflight", icon="CHECKMARK" if preflight.ok else "ERROR"
            )
            for msg in preflight.errors[:3]:
                req_box.label(text=msg, icon="ERROR")
            for msg in preflight.warnings[:2]:
                req_box.label(text=msg, icon="INFO")
            for msg in preflight.infos[:1]:
                req_box.label(text=msg, icon="INFO")
            if preflight.ok:
                req_box.label(text="Grove requirements satisfied", icon="CHECKMARK")

        layout.operator("growpy.select_grove_collection", icon="RESTRICT_SELECT_OFF")

        layout.separator()
        layout.label(text="Export Settings")
        layout.prop(prefs, "output_directory")
        layout.prop(prefs, "mesh_type")
        layout.prop(prefs, "include_twigs")
        layout.prop(prefs, "strict_grove_requirements")

        layout.separator()
        layout.label(text="Skeleton")
        col = layout.column(align=True)
        col.label(text="Skeleton data comes from Grove core during export.")
        col.label(text="No Blender armature is created by this addon.")
        col.label(text="Run Grove Build first. Build Skeleton is optional.")
        col.prop(prefs, "junction_blend_distance")

        layout.separator()
        layout.operator("growpy.export_nanite_assembly", icon="EXPORT")


_classes = [GROWPY_PT_NaniteExport]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
