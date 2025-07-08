
""" Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from os.path import isdir, dirname

import bpy
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from ..Languages.Translation import t


class GROVE22_OT_SetTexturesPath(Operator, ImportHelper):
    bl_idname = "the_grove_22.set_textures_path"
    bl_label = "Set Textures Folder..."
    bl_description = t('textures_path_tt')
    bl_options = {'INTERNAL'}

    filename_ext = ""

    filter_glob: StringProperty(
        default="",
        options={'HIDDEN'},
        subtype='DIR_PATH',
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    save_preferences: BoolProperty(
        name=t('save_preferences'), description=t('save_preferences_tt'), default=True)

    def draw(self, _):
        """ Draw the user interface inside the file browser. """

        self.layout.label(text='Where do you store bark textures?', icon='QUESTION')
        self.layout.separator()
        self.layout.prop(self, 'save_preferences')

    def execute(self, context):
        """ When the user has picked a folder, save this in the user preferences and fill the textures menu. """

        path = self.filepath
        if not isdir(path):
            path = dirname(path)

        context.preferences.addons[__package__.split('.')[0]].preferences.textures_path = path
        context.preferences.addons[__package__.split('.')[0]].preferences.tag_refresh_textures(context)

        if self.save_preferences:
            bpy.ops.wm.save_userpref()

        return {'FINISHED'}
