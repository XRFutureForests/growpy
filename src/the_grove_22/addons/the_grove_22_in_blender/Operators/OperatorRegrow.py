
""" Restart and regrow the trees for the same number of years.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


import bpy
from ..Languages.Translation import t


class GROVE22_OT_Regrow(bpy.types.Operator):

    bl_idname = "the_grove_22.regrow"
    bl_label = t('regrow')
    bl_description = t('regrow_tt')
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, _):
        bpy.ops.the_grove_22.grow('INVOKE_DEFAULT', do_regrow=True)
        return {'FINISHED'}
