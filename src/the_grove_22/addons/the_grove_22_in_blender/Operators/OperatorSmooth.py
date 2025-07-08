
""" Reduce the angle of sharp corners to create more smoothly bending branches.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from bpy.types import Operator

from ..Languages.Translation import t
from .OperatorBuild import build
from .OperatorReplant import replant
from ..File import load_grove, save_grove


class GROVE22_OT_Smooth(Operator):

    bl_idname = "the_grove_22.smooth"
    bl_label = t('smooth')
    bl_description = t('smooth_tt')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        properties = context.collection.GROVE22_Properties
        grove = load_grove(context.collection)
        if not grove:
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            context.window.cursor_modal_restore()
            return {'CANCELLED'}

        replant(context.collection, properties, grove)
        grove.smooth()
        save_grove(grove, context.collection)
        build(context, properties, grove, context.collection, rebuild=True)

        context.window.cursor_modal_restore()
        return {'FINISHED'}

    def invoke(self, context, _):
        context.window.cursor_modal_set('WAIT')
        return self.execute(context)
