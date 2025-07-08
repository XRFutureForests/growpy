
""" Add a new Grove collection and make it active.
    Generate a unique ID used to couple the grove with its own geometry nodes.

    Copyright 2018 - 2025, Wybren van Keulen, The Grove """


from time import time

import bpy
from ..Languages.Translation import t
from .OperatorRestart import restart
from ..Presets import preset_names


class GROVE22_OT_Add(bpy.types.Operator):

    bl_idname = "the_grove_22.add"
    bl_label = t('add_new_grove')
    bl_description = t('add_new_grove_tt')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out. """
        return context.mode == 'OBJECT'

    def execute(self, context):
        """ Add a new grove collection. """
        
        if not len(preset_names()):
            self.report({"ERROR"}, "No presets found, please first configure the presets path!")
            return {'FINISHED'}
        
        new_grove_collection = bpy.data.collections.new('Grove')
        context.scene.collection.children.link(new_grove_collection)
        context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[-1]

        properties = new_grove_collection.GROVE22_Properties

        # Try loading a default preset, which the user may have deleted.
        existing_preset_names = preset_names()
        
        if 'Oleaceae - Ash' in existing_preset_names:
            properties.presets_menu = 'Oleaceae - Ash'
        elif 'Canabaceae - Hackberry' in existing_preset_names:
            properties.presets_menu = 'Canabaceae - Hackberry'
        else:
            if len(existing_preset_names):
                properties.presets_menu = existing_preset_names[0]

        # Add unique ID to the collection.
        properties.unique_id = str(round(time() * 100.0))[4:]

        restart()

        # Try loading default texture.
        for texture in properties.textures_list:
            if texture[0].endswith('BlackAlder35.jpg'):
                properties.texture_bark = texture[0]
                break

        # Set scene units that make sense.
        if context.preferences.addons[__package__.split('.')[0]].preferences.use_adaptive_units:
            try:
                context.scene.unit_settings.length_unit = 'ADAPTIVE'
            except AttributeError:
                print('The Grove in Blender - Setting scene units failed, something changed in the Blender Python API.')

        return {'FINISHED'}

    def invoke(self, context, _):
        return self.execute(context)
