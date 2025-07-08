
""" Code for reading, writing and managing presets.
    Copyright (c) 2016 - 2025, Wybren van Keulen, The Grove. """


from os.path import join, exists, dirname, split, splitext
from os import listdir, remove
from shutil import copy2, SameFileError
from operator import itemgetter
from math import floor, log10

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

from .Languages.Translation import t

import json

def round_to_string(a):
    """ Round floating point numbers to 2 significant digits. """

    # TODO 2.3: remove this.

    if a == 0:
        return "0.0"
    else:
        return str(round(a, 2 - int(floor(log10(abs(a)))) - 1))


def presets_path():
    """ Find out where the presets are stored. """

    path = join(dirname(dirname(dirname(__file__))), "presets")
    path = bpy.context.preferences.addons[__package__].preferences.presets_path
    if exists(path):
        return path
    else:
        return None


def preset_names():

    # Convert old .seed files to json.
    # TODO 2.3: remove this.
    for file_name in sorted(listdir(presets_path())):
        if file_name[-5:] == '.seed':
            properties = properties = bpy.context.collection.GROVE22_Properties
            read_preset_seed(file_name[:-5], properties)
            write_preset(file_name[:-5], properties, select=False)
            path = join(presets_path(), file_name)
            remove(path)

    return [a[:-10] for a in sorted(listdir(presets_path())) if a[-10:] == '.seed.json' and a[0] != '.']


def list_presets():
    """ Search the presets folder for presets and add them to the presets menu. """

    presets = []
    for name in preset_names():
        presets.append((name, name, ""))
    presets.sort(key=itemgetter(1))
    return presets


def write_preset(name, properties, select=True):
        """ Write preset file. Only save a selection of parameters, others like build resolution are
            not related to a tree species. """

        seed_file = open(join(presets_path(), name + '.seed.json'), 'w')
        preset_dictionary = {}

        for parameter in dir(properties):
            if parameter in [
                    'twig_density',
                    'twig_longevity',
                    'simulation_scale',
                    'surround_enabled',
                    'surround_density',
                    'surround_distance',
                    'surround_height',
                    'surround_grow',
                    'auto_prune_enabled',
                    'auto_prune_low',
                    'auto_prune_keep_thick',
                    'auto_prune_dangling',
                    'favor_end',
                    'shade_avoidance',
                    'favor_end_reduce',
                    'favor_bright',
                    'favor_rising',
                    'drop_shaded',
                    'drop_weak',
                    'drop_obsolete',
                    'drop_decay',
                    'add_side_branches',
                    'add_chance',
                    'add_chance_reduce',
                    'add_bud_life',
                    'add_twist',
                    'add_angle',
                    'add_only_on_end',
                    'add_fork',
                    'add_regenerate',
                    'add_horizontal',
                    'add_up',
                    'grow_length',
                    'grow_nodes',
                    'turn_to_light',
                    'turn_up',
                    'turn_up_in_shade',
                    'turn_to_horizon',
                    'turn_random',
                    'turn_up',
                    'turn_up_in_shade',
                    'thicken_tips',
                    'thicken_tips_reduce',
                    'thicken_join',
                    'thicken_deadwood',
                    'thicken_base_scale',
                    'thicken_base_shape',
                    'thicken_base_buttress',
                    'bend_mass',
                    'bend_twig_mass',
                    'bend_twig_mass_solidify',
                    'bend_reaction',
                    'shade_area',
                    'shade_area_reduce',
                    'shade_area_depth',
                    'shade_leaf_sides',
                    'shade_branches',
                    'shade_alongside',
                    'shade_alongside_diameter']:

                value = getattr(properties, parameter)

                # Round floating point values.
                if isinstance(value, float):
                    if value == 0:
                        value = 0.0
                    else:
                        value = round(value, 2 - int(floor(log10(abs(value)))) - 1)

                preset_dictionary[parameter] = value

        json.dump(preset_dictionary, seed_file, indent=4)
        seed_file.close()

        if select:
            select_preset(name, properties)


def select_preset(name, properties):
    """ Make sure a newly added preset is selected in the drop down. """

    presets = list_presets()
    for preset in presets:
        if preset[1] == name:
            properties.presets_menu = preset[0]
            properties.preset_name = preset[1]
            break


def remove_imported_file_preset(properties, selected_preset_name):
    """ When importing a file, it creates a temporary preset called Imported File.
        As soon as another preset is picked, it can be removed. """

    name = 'Imported File'

    if properties.presets_menu == name:
        return

    path = join(presets_path(), name + ".seed.json")
    if exists(path):
        try:
            remove(path)
        except OSError:
            print("OS Error: Could not delete preset file. It may be in use.")

        list_presets()
        select_preset(selected_preset_name, properties)


def read_preset_seed(name, properties):
    """ Read preset file and return a dictionary with all properties inside the preset. """

    # TODO 2.3: remove this.
    name = join(presets_path(), name + ".seed")
    preset = {}

    try:
        with open(name, 'r') as preset_file:
            for line in preset_file:
                if len(line.split('=')) != 2:
                    continue
                parameter, value = line.split('=')
                parameter = parameter.strip()
                value = value.strip()

                if parameter in dir(properties):
                    if value == "True":
                        value = True
                    elif value == "False":
                        value = False
                    elif value[0] == value[-1] and value[0] == '"':
                        value = str(value[1:-1])
                    else:
                        try:
                            value = int(value)
                        except ValueError:
                            try:
                                value = float(value)
                            except ValueError:
                                pass

                    preset[parameter] = value

                # Backward compatibility
                # elif parameter == 'old_parameter_name':
                #     properties.new_parameter_name = float(value)

    except IOError:
        print("Failed loading preset " + name)
        return

    # side_branches is now a simple int, not an enum string anymore.
    if "add_side_branches" in preset:
        preset["add_side_branches"] = int(preset["add_side_branches"])

    for parameter, value in preset.items():
        try:
            setattr(properties, parameter, value)
        except TypeError:
            print("Load Preset - Skipping parameter " + parameter + ", it has the wrong type.111")

    # Backward compatibility for old presets, set new parameters to a default value.
    # if 'new_parameter_name' not in preset:
    #     properties.new_parameter = 0.0


def read_preset(name, properties):
    """ Read preset file and return a dictionary with all properties inside the preset. """

    path = join(presets_path(), name + ".seed.json")
    preset = {}

    try:
        with open(path, 'r') as preset_file:
            preset = json.load(preset_file)

    except IOError:
        print("Failed loading preset " + name)
        return

    for parameter, value in preset.items():
        try:
            setattr(properties, parameter, value)
        except TypeError:
            print("Read preset - skipping parameter " + parameter + ", it has the wrong type.")

        # Backward compatibility
        # if parameter == 'old_parameter_name':
        #     properties.new_parameter_name = float(value)

    # Backward compatibility for old presets, set new parameters to a default value.
    # if 'new_parameter_name' not in preset:
    #     properties.new_parameter = 0.0


class GROVE22_OT_Preset_Remove(bpy.types.Operator):

    bl_idname = "the_grove_22.preset_remove"
    bl_label = t('remove_preset')
    bl_description = t('remove_preset_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        """ Remove the active preset. """

        properties = context.collection.GROVE22_Properties
        name = properties.preset_name
        print(t('Remove Preset - ') + name)

        path = join(presets_path(), name + ".seed.json")
        if exists(path):
            try:
                remove(path)
            except OSError:
                print("OS Error: Could not delete preset file. It may be in use.")

        # After removing the preset, select the first preset in the list.
        properties.presets_menu = list_presets()[0][0]
        properties.preset_name = list_presets()[0][1]

        return {'FINISHED'}


class GROVE22_OT_Preset_Cancel(bpy.types.Operator):

    bl_idname = "the_grove_22.preset_cancel"
    bl_label = t('cancel_action')
    bl_description = t('cancel_action')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        """ Cancel add, remove or overwrite presets and close the UI box. """
        properties = context.collection.GROVE22_Properties
        properties.show_add_preset_box = False
        properties.show_remove_preset_box = False
        properties.show_overwrite_preset_box = False
        return {'FINISHED'}


class GROVE22_OT_Preset_Rename(bpy.types.Operator):

    bl_idname = "the_grove_22.preset_rename"
    bl_label = t('rename_preset')
    bl_description = t('rename_preset_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        """ Remove the named preset and write a new preset. """

        properties = context.collection.GROVE22_Properties
        old_name = properties.presets_menu
        new_name = properties.preset_name

        write_preset(new_name, properties)

        # Remove the old preset.
        path = join(presets_path(), old_name + ".seed.json")
        if exists(path):
            try:
                remove(path)
            except OSError:
                print("OS Error: Could not delete preset file. It may be in use.")

        # Make sure the newly added preset is selected in the drop down.
        select_preset(new_name, properties)

        properties.show_add_preset_box = False
        properties.show_remove_preset_box = False

        return {'FINISHED'}


class GROVE22_OT_Preset_Save(bpy.types.Operator):

    bl_idname = "the_grove_22.preset_save"
    bl_label = t('add_preset')
    bl_description = t('add_preset_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        """ Save the current properties to a new preset. """

        properties = context.collection.GROVE22_Properties
        name = properties.preset_name

        if exists(join(presets_path(), name + ".seed.json")):
            properties.show_overwrite_preset_box = True
            return {'FINISHED'}

        # Write and select new preset.
        write_preset(name, properties)

        properties.show_add_preset_box = False
        properties.show_remove_preset_box = False

        return {'FINISHED'}


class GROVE22_OT_Preset_Overwrite(bpy.types.Operator):

    bl_idname = "the_grove_22.preset_overwrite"
    bl_label = t('overwrite_preset')
    bl_description = t('overwrite_preset_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        """ Overwrite the existing preset."""

        properties = context.collection.GROVE22_Properties
        name = properties.preset_name

        # Write and select new preset.
        write_preset(name, properties)

        properties.show_add_preset_box = False
        properties.show_remove_preset_box = False

        return {'FINISHED'}


class GROVE22_OT_Preset_Import(bpy.types.Operator, ImportHelper):

    bl_idname = "the_grove_22.preset_import"
    bl_label = t('import_preset')
    bl_description = t('import_preset_tt')
    bl_options = {'INTERNAL'}

    filename_ext = ".seed.json"

    filter_glob: StringProperty(
        default="*.seed.json",
        options={'HIDDEN'},
        subtype='DIR_PATH',
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def draw(self, context):
        self.layout.label(text='Select a .seed.json file.', icon='INFO')

    def execute(self, context):
        properties = context.collection.GROVE22_Properties

        print('The Grove in Blender - Copying preset: ' + self.filepath)

        if splitext(self.filepath)[-1] == '.json':
            try:
                copy2(self.filepath, presets_path())
            except SameFileError:
                self.report({'WARNING'}, 'The Grove in Blender - This preset is already in your presets folder.')
                return {'CANCELLED'}
            except PermissionError:
                self.report({'ERROR'}, 'The Grove in Blender - Failed to copy the preset to your presets folder, you have no permission to write to the folder.')
                return {'CANCELLED'}

        # Make sure the newly added preset is selected in the drop down.
        new_name = splitext(split(self.filepath)[-1])[0]
        # print('The Grove in Blender - Trying to set twigs menu to: ' + new_name)
        presets = list_presets()
        for preset in presets:
            if preset[1] == new_name:
                properties.presets_menu = preset[0]
                properties.preset_name = preset[1]
                break

        properties.show_add_preset_box = False
        properties.show_remove_preset_box = False

        return {'FINISHED'}
