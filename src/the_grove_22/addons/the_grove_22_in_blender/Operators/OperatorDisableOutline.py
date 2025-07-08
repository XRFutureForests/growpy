
""" Blender by default draws outlines around objects, but that makes thin branches
    appear much thicker. This operator warns the user and provides a one-click solution.

    Copyright 2019 - 2025, Wybren van Keulen, The Grove """

from bpy.types import Operator

from ..Languages.Translation import t


class GROVE22_OT_DisableOutline(Operator):

    bl_idname = "the_grove_22.disable_outline"
    bl_label = t('disable_outline')
    bl_description = t('disable_outline_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        context.area.spaces[0].shading.show_object_outline = False
        return {"FINISHED"}
