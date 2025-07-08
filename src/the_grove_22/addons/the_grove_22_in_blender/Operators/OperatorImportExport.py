
""" Export the current grove to a .grove file.
    As a back-up, to share, or to import into another application.
    Copyright (c) 2024 - 2025, Wybren van Keulen, The Grove. """

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty
from os.path import exists

import gzip
import base64

from ..Core import import_core
the_grove_core = import_core()

from ..Presets import write_preset
from ..File import save_grove, load_grove
from .OperatorBuild import clean_grove, clean_record
from .OperatorPlant import recreate_empties
from ..Languages.Translation import t


class GROVE22_OT_Export_Grove(bpy.types.Operator, ExportHelper):

    bl_idname = "the_grove_22.export_grove"
    bl_label = t('file_export')
    bl_description = t('file_export_tt')
    bl_options = {'INTERNAL'}

    filename_ext = ".grove"

    filter_glob: StringProperty(
        default="*.grove",
        options={'HIDDEN'},
        subtype='DIR_PATH',
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def draw(self, context):
        self.layout.label(text='Save a .grove file.', icon='INFO')

    def invoke(self, context, event):
        self.filepath = most_recent_file()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):

        # Update the grove's properties with the latest changes made in the UI.
        # These changes are automatically set in the grove each time when using tools like grow and prune,
        # but changes may have been made after that.
        grove = load_grove(context.collection)
        grove.set_properties(
            context.collection.GROVE22_Properties.convert_to_core_properties())
        save_grove(grove, context.collection)

        with open(self.filepath, 'wb') as out_file:
            data_string = the_grove_core.io.grove_to_json_string(grove)
            compressed_data = gzip.compress(bytes(data_string.encode('utf-8')), compresslevel=3)
            out_file.write(compressed_data)

        add_to_recent_files(self.filepath)

        return {'FINISHED'}


class GROVE22_OT_Import_Grove(bpy.types.Operator, ImportHelper):

    bl_idname = "the_grove_22.import_grove"
    bl_label = t('file_import')
    bl_description = t('file_import_tt')
    bl_options = {'INTERNAL'}

    filename_ext = ".grove"

    filter_glob: StringProperty(
        default="*.grove",
        options={'HIDDEN'},
        subtype='DIR_PATH',
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def draw(self, context):
        self.layout.label(text='Import a .grove file.', icon='INFO')

    def invoke(self, context, event):
        self.filepath = most_recent_file()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.window.cursor_modal_set('WAIT')
        import_path(self.filepath)
        context.window.cursor_modal_restore()

        return {'FINISHED'}


def import_path(filepath):
    grove_collection = bpy.context.collection

    clean_record(grove_collection)
    clean_grove(grove_collection)

    with open(filepath, 'rb') as in_file:
        compressed_data = in_file.read()
        grove_collection['grove'] = base64.b64encode(compressed_data).decode('utf-8')

    # Read properties from the imported grove.
    grove = load_grove(grove_collection)
    properties = grove_collection.GROVE22_Properties
    properties.read_from_core_properties(grove.get_properties())

    bpy.ops.the_grove_22.build()
    recreate_empties()

    # Copy the properties of the imported file to a new preset called Imported File.
    write_preset('Imported File', properties, select=True)

    add_to_recent_files(filepath)


def add_to_recent_files(filepath):
    prefs = bpy.context.preferences.addons[__package__.split('.')[0]].preferences
    if prefs.recent_files != "":
        prefs.recent_files = prefs.recent_files + "\n"
    prefs.recent_files = prefs.recent_files + filepath


def most_recent_file():
    prefs = bpy.context.preferences.addons[__package__.split('.')[0]].preferences
    files = prefs.recent_files.split("\n")
    if len(files) and exists(files[-1]):
        return files[-1]
    else:
        return ""


def recent_files():
    prefs = bpy.context.preferences.addons[__package__.split('.')[0]].preferences
    files = prefs.recent_files.split("\n")
    existing_files = []
    for file in files:
        if exists(file):
            # Filter out duplicates.
            if file not in existing_files:
                existing_files.append(file)

    # Maximum of 5 recent files.
    existing_files = existing_files[-5:]

    # Update recent files to only existing ones.
    prefs.recent_files = ""
    for file in existing_files:
        if prefs.recent_files != "":
            prefs.recent_files += "\n"
        prefs.recent_files += file

    return existing_files
