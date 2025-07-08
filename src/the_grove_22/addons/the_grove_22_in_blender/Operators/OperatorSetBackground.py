
""" Set the background color to a brighter grey.
    Blender's default background is too close to the bark color,
    which makes trees hard to see.

    Copyright 2018 - 2025, Wybren van Keulen, The Grove """

from bpy.types import Operator

from ..Languages.Translation import t


class GROVE22_OT_SetBackground(Operator):

    bl_idname = "the_grove_22.set_background"
    bl_label = t('set_background')
    bl_description = t('set_background_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        context.area.spaces[0].shading.background_type = 'VIEWPORT'
        context.area.spaces[0].shading.background_color = (0.214, 0.214, 0.214)

        return {"FINISHED"}
