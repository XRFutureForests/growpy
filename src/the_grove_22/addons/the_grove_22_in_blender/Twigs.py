
""" The twig picker lists your library of twigs in a convenient menu.
    Picking a twig automatically appends the twig objects and links them
    to the twigs collection.

    Copyright (c) 2017 - 2025, Wybren van Keulen, The Grove. """


from os import walk
from os.path import join, split
from re import sub, search
from operator import itemgetter

import bpy

from .Languages.Translation import t


def list_twigs(context):
    """ Fill the twig library menu with twigs found in the twigs folder.
        Display a tip to configure a twigs path if no twigs are found.
        Also add options to pick scene objects, or no twigs at all. """

    twigs_path = context.preferences.addons[__package__].preferences.twigs_path
    items = [(t('twig_no_twigs'), t('twig_no_twigs'), t('twig_no_twigs_tt'), 'X', 0),
             (t('twig_pick_objects'), t('twig_pick_objects'), t('twig_pick_objects_tt'), 'OBJECT_DATA', 1),  # SCENE_DATA
             (t('twig_pick_collections'), t('twig_pick_collections'), t('twig_pick_collections_tt'), 'GROUP', 2)]

    library_items = []
    i = 3
    for root, _, files in walk(twigs_path):
        for file_name in files:
            if file_name[-6:] == '.blend' and not file_name.startswith("."):
                english_name = split(root)[-1].split('Twig')[0] # Strip the Twig at the end of the name.
                english_name = sub('(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z0-9])', ' ', english_name) # Convert CamelCase to spaces.
                english_name = sub('[ ]+[ ]', ' ', english_name) # Remove any duplicate spaces.

                scientific_name = file_name[:-6].split('Twig')[0] # Strip the Twig at the end of the name.
                scientific_name = sub('(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z0-9])', ' ', scientific_name) # Convert CamelCase to spaces.
                scientific_name = sub('[ ]+[ ]', ' ', scientific_name) # Remove any duplicate spaces.

                if bool(search(r'[A-Z]$', scientific_name)):
                    english_name += ' ' + scientific_name[-1]

                # english_name = sub('(?!^)([A-Z0-9]+)', r' \1', display_name)

                if len(scientific_name.split(' ')) < 2:
                    scientific_name = english_name

                # Quote varieties.
                scientific_name_split = scientific_name.split(' ')
                if len(scientific_name_split) > 2 and scientific_name_split[1].lower() == 'x':
                    if len(scientific_name_split) == 3:
                        scientific_name = scientific_name_split[0] + ' × ' + scientific_name_split[2].lower()
                    elif len(scientific_name_split) == 4:
                        scientific_name = scientific_name_split[0] + ' × ' + scientific_name_split[2].lower() + " '" + scientific_name_split[3] + "'"
                elif len(scientific_name_split) == 4:
                    scientific_name = scientific_name_split[0] + ' ' + scientific_name_split[1].lower() + " " + scientific_name_split[2] + " '" + scientific_name_split[3] + "'"
                elif len(scientific_name_split) == 3:
                    scientific_name = scientific_name_split[0] + ' ' + scientific_name_split[1].lower() + " '" + scientific_name_split[2] + "'"
                elif len(scientific_name_split) == 2:
                    scientific_name = scientific_name_split[0] + ' ' + scientific_name_split[1].lower()

                if context.preferences.addons[__package__.split('.')[0]].preferences.use_scientific_names:
                    library_items.append((join(root, file_name), scientific_name, english_name, 'APPEND_BLEND', i))
                else:
                    library_items.append((join(root, file_name), english_name, scientific_name, 'APPEND_BLEND', i))
                i += 1
    library_items.sort(key=itemgetter(1))

    items = items + library_items

    return items


def add_hashed_alpha(obj):
    """ To make materials of existing twigs work with alpha in Eevee.
        Should be temporary, twigs should be updated. """

    for slot in obj.material_slots:
        material = slot.material
        if material.name.endswith('Leaves'):
            material.blend_method = 'HASHED'


def find_existing_data(data_block):
    """ Blender uses a system of adding a dot followed by an increasing number to denote
        duplicated objects. For instance Cube becomes Cube.001, Cube.002...

        When importing twig objects from an external file, I want to prevent duplicates if the
        twig is already in the file.

        This function returns the duplicated twig or collection, or None if it can't find any. """

    name = data_block.name

    if data_block.rna_type.name == 'Object':
        data = bpy.data.objects
    if data_block.rna_type.name == 'Collection':
        data = bpy.data.collections

    # First find out if the name ends with a dot and three digits.
    # If not, then there is no duplicate.
    if len(name) > 4 and name[-4] == ".":
        try:
            number = int(name[-3:])
        except ValueError:
            return name
    else:
        return name

    # If so, try to find the original, by reducing the number.
    # .003 becomes .002, .001 and eventually remove the dot and number.
    base_name = name[:-4]
    for i in reversed(range(number)):
        if i == 0:
            original_name = base_name
        else:
            original_name = base_name + '.' + "{:03d}".format(i)

        if original_name in data:
            if data[original_name].users != 0:
                # print('The Grove in Blender - Using existing twig found in scene.')
                return data[original_name].name

    return name

def append_twigs(properties, context):
    """ Append twigs from a twigs file.

        The naming convention for object inside twig files is simple. A lateral twig should contain "lateral", an
        apical twig "apical", and if both twigs are the same, the object should be named something with twig. It is
        case insensitive. """

    if properties.twig_menu == t('twig_no_twigs'):
        return

    twig_collection_long = ""
    twig_collection_short = ""
    twig_collection_upward = ""
    twig_collection_dead = ""
    twig_object_end = ""
    twig_object_side = ""
    twig_object_upward = ""
    twig_object_dead = ""

    # Find an already existing twigs collection, create one if necessary.
    twigs_collection = None
    for collection in context.collection.children:
        if collection.name.startswith('Twigs'):
            twigs_collection = collection
            break
    if twigs_collection is None:
        twigs_collection = bpy.data.collections.new('Twigs')
        context.collection.children.link(twigs_collection)
        context.view_layer.active_layer_collection.children[twigs_collection.name].hide_viewport = True
        twigs_collection.hide_render = True

    display_name = split(properties.twig_menu[:-6])[1]
    display_name = display_name.split('Twig')[0]
    display_name = sub('(?!^)([A-Z0-9]+)', r' \1', display_name)
    display_name = sub('[ ]+[ ]', ' ', display_name)
    sub_twigs_collection = None
    for collection in twigs_collection.children:
        if collection.name.startswith(display_name):
            if collection.name == display_name:
                sub_twigs_collection = collection
                break
            elif len(collection.name) > 4 and collection.name[-4] == "." and collection.name[-3:].isdigit():
                sub_twigs_collection = collection
    if sub_twigs_collection is None:
        sub_twigs_collection = bpy.data.collections.new(display_name)
        twigs_collection.children.link(sub_twigs_collection)
    twigs_collection = sub_twigs_collection

    with bpy.data.libraries.load(properties.twig_menu) as (data_from, data_to):
        # data_to.collections = [name for name in data_from.collections if name.lower().find("twigs") != -1]
        # data_to.collections = [col for col in data_from.collections if col.name.lower().find("twigs") != -1]
        # Above 2 lines do not work! So manually check every name for 'twig' below.
        data_to.collections = data_from.collections
        data_to.objects = data_from.objects

    properties.do_twig_collections = False
    # First check if there are twig collections in the file.
    for col in data_to.collections:
        if col is not None:
            # If the collection name ends with a dot and three digits,
            # there was already a collection with that name.
            name = find_existing_data(col)
            name_lower = name.lower()

            if name_lower.find('lateral') != -1 or name_lower.find('side') != -1 or name_lower.find('short') != -1:
                if name_lower.find('twig') != -1:
                    if name not in twigs_collection.children:
                        twigs_collection.children.link(bpy.data.collections[name])
                    twig_collection_short = name
                    properties.do_twig_collections = True

            elif name_lower.find('apical') != -1 or name_lower.find('end') != -1 or name_lower.find('long') != -1:
                if name_lower.find('twig') != -1:
                    if name not in twigs_collection.children:
                        twigs_collection.children.link(bpy.data.collections[name])
                    twig_collection_long = name
                    properties.do_twig_collections = True

            elif name_lower.find('upward') != -1 or name_lower.find('vertical') != -1:
                if name_lower.find('twig') != -1:
                    if name not in twigs_collection.children:
                        twigs_collection.children.link(bpy.data.collections[name])
                    twig_collection_upward = name
                    properties.do_twig_collections = True

            elif name_lower.find('dead') != -1:
                if name_lower.find('twig') != -1:
                    if name not in twigs_collection.children:
                        twigs_collection.children.link(bpy.data.collections[name])
                    twig_collection_dead = name
                    properties.do_twig_collections = True

            elif name_lower.find('twig') != -1:
                if name not in twigs_collection.children:
                    twigs_collection.children.link(bpy.data.collections[name])
                if twig_collection_long == "":
                    twig_collection_long = name
                if twig_collection_short == "":
                    twig_collection_short = name
                properties.do_twig_collections = True

    if not properties.do_twig_collections:
        # Second, if no twig collections are found, try finding twig objects.
        for obj in data_to.objects:
            if obj is not None:
                name = find_existing_data(obj)
                name_lower = name.lower()

                if (name_lower.find('lateral') != -1 or
                        name_lower.find('sidetwig') != -1 or
                        name_lower.find('shorttwig') != -1):
                    if name not in context.scene.objects:
                        twigs_collection.objects.link(bpy.data.objects[name])
                    twig_object_side = name
                    add_hashed_alpha(bpy.data.objects[name])

                elif (name_lower.find('apical') != -1 or
                      name_lower.find('endtwig') != -1 or
                      name_lower.find('longtwig') != -1):
                    if name not in context.scene.objects:
                        twigs_collection.objects.link(bpy.data.objects[name])
                    twig_object_end = name
                    add_hashed_alpha(bpy.data.objects[name])

                elif name_lower.find('upward') != -1 or name_lower.find('vertical') != -1:
                    if name not in context.scene.objects:
                        twigs_collection.objects.link(bpy.data.objects[name])
                    twig_object_upward = name

                elif name_lower.find('dead') != -1:
                    if name not in context.scene.objects:
                        twigs_collection.objects.link(bpy.data.objects[name])
                    twig_object_dead = name

                elif name_lower.find('twig') != -1:
                    if name not in context.scene.objects:
                        twigs_collection.objects.link(bpy.data.objects[name])
                    if twig_object_end == "":
                        twig_object_end = name
                    if twig_object_side == "":
                        twig_object_side = name
                    add_hashed_alpha(bpy.data.objects[name])

    if properties.do_twig_collections:
        properties.twig_collection_long = None
        properties.twig_collection_short = None
        properties.twig_collection_upward = None
        properties.twig_collection_dead = None
    else:
        properties.twig_object_end = None
        properties.twig_object_side = None
        properties.twig_object_upward = None
        properties.twig_object_dead = None

    if twig_object_end in bpy.data.objects:
        properties.twig_object_end = bpy.data.objects[twig_object_end]
    if twig_object_side in bpy.data.objects:
        properties.twig_object_side = bpy.data.objects[twig_object_side]
    if twig_object_upward in bpy.data.objects:
        properties.twig_object_upward = bpy.data.objects[twig_object_upward]
    if twig_object_dead in bpy.data.objects:
        properties.twig_object_dead = bpy.data.objects[twig_object_dead]

    if twig_collection_long in bpy.data.collections:
        properties.twig_collection_long = bpy.data.collections[twig_collection_long]
    if twig_collection_short in bpy.data.collections:
        properties.twig_collection_short = bpy.data.collections[twig_collection_short]
    if twig_collection_upward in bpy.data.collections:
        properties.twig_collection_upward = bpy.data.collections[twig_collection_upward]
    if twig_collection_dead in bpy.data.collections:
        properties.twig_collection_dead = bpy.data.collections[twig_collection_dead]


def list_twigs_with_previews(context):
    """ A visual twig picker with large thumbnails. """

    global twig_previews

    # Create a new preview collection (only upon register)
    twig_previews = bpy.utils.previews.new()

    twigs_path = context.preferences.addons[__package__].preferences.twigs_path
    twigs = [(t('twig_pick_objects'), t('twig_pick_objects'), t('twig_pick_objects_tt'), 'GROUP', 0),
             (t('twig_no_twigs'), t('twig_no_twigs'), t('twig_no_twigs_tt'), 'X', 1)]

    i = 3
    for root, _, files in walk(twigs_path):
        for file_name in files:
            if file_name[-6:] == '.blend':
                display_name = file_name[:-6]
                # Strip the Twig at the end of the name.
                display_name = display_name.split('Twig')[0]
                # Convert CamelCase to spaces.
                display_name = sub('(?!^)([A-Z0-9]+)', r' \1', display_name)
                # Remove any duplicate spaces caused by the previous regex.
                display_name = sub('[ ]+[ ]', ' ', display_name)
                twig_preview = twig_previews.load(
                    join(root, file_name[:-6] + 'Preview.png'), join(root, file_name[:-6] + 'Preview.png'), 'IMAGE')
                twigs.append((join(root, file_name), display_name, '', twig_preview.icon_id, i))
                i += 1

    twigs.sort(key=itemgetter(1))

    return twigs


def unregister_twig_previews():
    global twig_previews

    bpy.utils.previews.remove(twig_previews)
    del bpy.types.Scene.twig_preview_menu
