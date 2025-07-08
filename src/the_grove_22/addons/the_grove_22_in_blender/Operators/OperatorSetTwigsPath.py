
""" Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from os.path import isdir, dirname

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator

from ..Languages.Translation import t


class GROVE22_OT_SetTwigsPath(Operator, ImportHelper):

    bl_idname = "the_grove_22.set_twigs_path"
    bl_label = "Set Twigs Folder..."
    bl_description = t('twigs_path_tt')
    bl_options = {'INTERNAL'}

    filename_ext = ""

    filter_glob: StringProperty(
        default="", options={'HIDDEN'}, subtype='DIR_PATH', maxlen=255)

    save_preferences: BoolProperty(
        name=t('save_preferences'), description=t('save_preferences_tt'), default=True)

    def draw(self, _):
        self.layout.label(text='Where do you store twigs?', icon='QUESTION')
        self.layout.separator()
        self.layout.prop(self, 'save_preferences')

    def execute(self, context):
        path = self.filepath
        if not isdir(path):
            path = dirname(path)

        context.preferences.addons[__package__.split('.')[0]].preferences.twigs_path = path
        context.preferences.addons[__package__.split('.')[0]].preferences.tag_refresh_twigs(context)

        if self.save_preferences:
            bpy.ops.wm.save_userpref()

        return {'FINISHED'}
