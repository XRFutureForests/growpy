"""Addon preferences for GrowPy Nanite Export."""

import bpy


class GrowPyNanitePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    output_directory: bpy.props.StringProperty(
        name="Output Directory",
        description="Default directory for exported Nanite Assembly USD files",
        subtype="DIR_PATH",
        default="//nanite_export/",
    )

    mesh_type: bpy.props.EnumProperty(
        name="Mesh Type",
        description="Nanite Assembly mesh type for Unreal Engine",
        items=[
            ("SKELETAL", "Skeletal Mesh", "Export with skeleton for animation support"),
            ("STATIC", "Static Mesh", "Export as static mesh (no skeleton)"),
        ],
        default="SKELETAL",
    )

    strict_grove_requirements: bpy.props.BoolProperty(
        name="Strict Grove Requirements",
        description=(
            "Block export until Grove prerequisites are satisfied: valid Grove "
            "collection, built tree meshes, and skeletal build data for skeletal export"
        ),
        default=True,
    )

    junction_blend_distance: bpy.props.FloatProperty(
        name="Junction Blend",
        description="Distance over which to blend weights at branch junctions (meters)",
        default=0.5,
        min=0.0,
        max=2.0,
        step=10,
    )

    include_twigs: bpy.props.BoolProperty(
        name="Include Twigs",
        description="Convert and include twig instances in the Nanite Assembly",
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "output_directory")
        layout.separator()

        layout.label(text="Export Settings:")
        layout.prop(self, "mesh_type")
        layout.prop(self, "include_twigs")
        layout.prop(self, "strict_grove_requirements")

        layout.separator()
        layout.label(text="Skeleton (Grove-owned):")
        box = layout.box()
        box.label(text="Use The Grove > Build > Skeleton for topology controls.")
        box.label(text="Export uses Grove-compatible defaults for tagging.")
        box.prop(self, "junction_blend_distance")


_classes = [GrowPyNanitePreferences]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
