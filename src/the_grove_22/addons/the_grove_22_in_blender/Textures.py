
""" Texture picker menu - lists every texture found in a library folder.
    Select a folder in Grove's user preferences.

    Copyright (c) 2017 - 2025, Wybren van Keulen, The Grove. """


from os import walk
from os.path import join, exists
from operator import itemgetter

import bpy
from numpy import array as np_array


def list_textures(context):
    """ List all textures found in the library folder. """

    textures_path = context.preferences.addons[__package__].preferences.textures_path
    textures = []
    extensions = ('.jpg', '.jpeg', '.png', '.tga', '.tif', '.tiff')
    normal_map_suffixes = ('_normal', 'Normal', 'normal', '_N', '_n', 'norm', 'nrm', 'nmap', 'normalmap')

    i = 0
    for root, _, files in walk(textures_path):
        for file_name in files:
            if file_name[0] == '.':
                # Don't show hidden files, which mostly are not valid image files.
                continue

            extension = file_name[-len(file_name.split('.')[-1]) - 1:]
            if extension.lower() in extensions:
                if file_name[:-len(extension)].endswith(normal_map_suffixes):
                    continue
                textures.append((join(root, file_name), file_name[:-len(extension)], '', 'IMAGEFILE', i))
                i += 1

    textures.sort(key=itemgetter(1))

    return textures


def apply_normal_map(properties, bark_material):
    """ Look for a normal map and try loading it and apply it to the bark material. """

    # try:
    node_tree = bark_material.node_tree
    normal_map_node = None
    if 'Bark Normal' in node_tree.nodes:
        normal_map_node = node_tree.nodes['Bark Normal']

    img_normal_path = ''
    extension = properties.texture_bark[-len(properties.texture_bark.split('.')[-1]) - 1:]
    suffixes = ['_normal', 'Normal', 'normal', '_N', '_n', 'norm', 'nrm', 'nmap', 'normalmap']
    for suffix in suffixes:
        if exists(properties.texture_bark[:-len(extension)] + suffix + extension):
            img_normal_path = properties.texture_bark[:-len(extension)] + suffix + extension
            break

    if img_normal_path != '':
        img_normal = bpy.data.images.load(img_normal_path, check_existing=True)

        try:
            img_normal.colorspace_settings.name = 'Non-Color'
        except TypeError:
            try:
                img_normal.colorspace_settings.name = 'Utility - Raw'
            except TypeError:
                try:
                    img_normal.colorspace_settings.name = 'Non-Colour Data'
                except TypeError:
                    try:
                        # AGX.
                        img_normal.colorspace_settings.name = 'Generic Data'
                    except TypeError:
                        print('The Grove in Blender - WARNING: Failed to set a color space for the normal map.')
                        print('You\'re likely using a custom OCIO configuration.')
                        print('Suggestion: manually set the normal map node to an appropriate linear color space.')

        if img_normal.size[0] == 0 or img_normal.size[1] == 0:
            # Invalid image file.
            properties.report_string = 'Selected bark texture is an invalid image file.'
            normal_map_node.mute = True
        else:
            if bark_material.node_tree:
                normal_map_node.mute = False
                normal_map_node.image = img_normal
    else:
        if normal_map_node:
            normal_map_node.mute = True
            normal_map_node.image = None

def swap_textures(properties, context):
    """ Change the bark texture on existing tree models. """

    bark_material = None

    if properties.bark_material_name != '':
        if properties.bark_material_name in bpy.data.materials:
            bark_material = bpy.data.materials[properties.bark_material_name]
        else:
            for material in bpy.data.materials:
                if 'original_name' in material:
                    if material['original_name'] == properties.bark_material_name:
                        bark_material = material

    if not bark_material:
        # Could not find the bark material.
        return

    if exists(properties.texture_bark):
        img = bpy.data.images.load(properties.texture_bark, check_existing=True)
        if img.size[0] == 0 or img.size[1] == 0:
            # Invalid image file.
            new_texture_aspect_ratio = 0.5
            properties.report_string = 'Selected bark texture is an invalid image file.'
        else:
            new_texture_aspect_ratio = img.size[0] / img.size[1]
    else:
        img = None
        new_texture_aspect_ratio = 3.0

    v_scale = new_texture_aspect_ratio / properties.texture_aspect_ratio
    u_scale = properties.texture_repeat / properties.previous_texture_repeat
    v_scale *= u_scale


    # Scale UV's.
    collections = [context.collection]
    if properties.record_enabled:
        # Flexibility for recording growth animation, also rescale previously recorded steps.
        if 'Record' in context.collection.children:
            collections.append(context.collection.children['Record'])

    for col in collections:
        for obj in col.objects:
            if 'grove' in obj:
                # Get current uv's.
                uv_layer = obj.data.uv_layers[0]
                old_uvs = [0.0] * (len(uv_layer.data.values()) * 2)
                uv_layer.data.foreach_get('uv', old_uvs)

                # Scale uv's.
                scaled_uvs = np_array(old_uvs)
                scaled_uvs.shape = (-1, 2)
                scaled_uvs *= [u_scale, v_scale]

                # Set new uv's.
                uv_layer.data.foreach_set("uv", [uv for pair in scaled_uvs for uv in pair])

                obj.data.update()

    properties.texture_aspect_ratio = new_texture_aspect_ratio

    if bark_material.node_tree:
        node_tree = bark_material.node_tree
        if 'Bark Texture' in node_tree.nodes:
            texture_node = node_tree.nodes['Bark Texture']
            texture_node.image = img

        apply_normal_map(properties, bark_material)
