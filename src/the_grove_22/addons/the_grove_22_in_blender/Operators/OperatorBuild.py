
""" Turn the simulated trees into a polygonal 3D model.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from os.path import dirname, exists, join
from gc import disable as disable_garbage_collection
from gc import enable as enable_garbage_collection

import bpy
from mathutils import Vector
from numpy import take, repeat, empty, ones, concatenate
from numpy import arange, column_stack, argsort, split, where, diff, round

from ..Textures import apply_normal_map
from .OperatorReplant import replant
from ..Languages.Translation import t
from ..File import load_grove, save_grove


class GROVE22_OT_Build(bpy.types.Operator):

    bl_idname = "the_grove_22.build"
    bl_label = t('rebuild')
    bl_description = t('rebuild_tt')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the add object menu entry is greyed out. """

        return context.mode == 'OBJECT'

    def execute(self, context):
        """ Build or rebuild trees. """

        disable_garbage_collection()

        properties = context.collection.GROVE22_Properties
        grove = load_grove(context.collection)
        if not grove:
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            context.window.cursor_modal_restore()
            return {'CANCELLED'}

        replanted = replant(context.collection, properties, grove)

        build(context, properties, grove, context.collection, rebuild=True)

        if replanted:
            save_grove(grove, context.collection)

        context.window.cursor_modal_restore()
        enable_garbage_collection()

        return {'FINISHED'}

    def invoke(self, context, _):
        context.window.cursor_modal_set('WAIT')
        return self.execute(context)


def tag_tree_object(tree_object, properties, index):
    """ Add custom properties to the tree object, used for info and for functionality. """

    tree_object['grove_preset'] = str(properties.preset_name)
    tree_object['grove'] = 'Grown with The Grove.'
    tree_object['grove_tree_age'] = properties.age
    tree_object['grove_tree_id'] = index
    tree_object['grove_id'] = properties.unique_id
    tree_object['grove_tree_origin'] = tree_object.location


def build(context, properties, grove, grove_collection, rebuild=False, root_id=-1, origin=None):
    """ Build the tree models. First clean previous builds. """

    if not properties.record_enabled:
        clean_record(grove_collection)

    clean_grove(grove_collection)

    # Before building, recalculate thickness and bending to update the tree to any changes in properties.
    if rebuild:
        grove.set_properties(properties.convert_to_core_properties())
        grove.weigh_and_bend()
    grove.remember_orig_pos() # !!! 2.1 TODO
    if context.preferences.addons[__package__.split('.')[0]].preferences.edition == 'STARTER':
        # TODO: Which of these options will be in the starter edition...
        models = grove.build_models({
                "resolution": 16,
                "resolution_reduce": 0.8,
                "texture_repeat": properties.texture_repeat,
                "build_cutoff_age": properties.build_cutoff_age,
                "build_cutoff_thickness": properties.build_cutoff_thickness,
                "build_blend": properties.build_blend,
                "build_end_cap": properties.build_end_cap,
            })
        if properties.build_triangulate:
            for model in models:
                model.triangulate()
    else:
        models = grove.build_models({
                "resolution": properties.build_resolution,
                "resolution_reduce": properties.build_resolution_reduce,
                "texture_repeat": properties.texture_repeat,
                "build_cutoff_age": properties.build_cutoff_age,
                "build_cutoff_thickness": properties.build_cutoff_thickness,
                "build_blend": properties.build_blend,
                "build_end_cap": properties.build_end_cap,
            })
        if properties.build_triangulate:
            for model in models:
                model.triangulate()
    if properties.record_enabled:
        models_spring = grove.build_spring_shape({
                "resolution": properties.build_resolution,
                "resolution_reduce": properties.build_resolution_reduce,
                "texture_repeat": properties.texture_repeat,
                "build_cutoff_age": properties.build_cutoff_age,
                "build_cutoff_thickness": properties.build_cutoff_thickness,
                "build_blend": properties.build_blend,
                "build_end_cap": properties.build_end_cap,
            })
        if properties.build_triangulate:
            for model in models_spring:
                model.triangulate()
    
    properties.number_of_polygons = 0
    for i, model in enumerate(models):
        model.apply_uv_aspect_ratio(properties.texture_aspect_ratio)
        tree_object = create_tree_object(model, properties, context)
        properties.number_of_polygons += len(model.faces)
        grove_collection.objects.link(tree_object)
        if properties.record_enabled:
            add_spring_shape(properties, models_spring[i], tree_object)

        tag_tree_object(tree_object, properties, i)

        # Make the tree object active. Don't select it to avoid the ugly selection outline.
        context.view_layer.objects.active = tree_object

    properties.age = grove.age

    # Add twigs.
    update_twigs(properties, grove_collection)
    update_wind_breeze(properties, bpy.context)

    if properties.record_enabled:
        if properties.age != 0:
            record(grove_collection, properties)
            retime(grove_collection, properties)

        # Set the viewport to display the last frame of the growth animation.
        context.scene.frame_set(
            properties.age * properties.record_interval + properties.record_interval * 2 + properties.record_start_frame - 1)
        if properties.age == 0:
            context.scene.frame_set(1)

    properties['height'] = grove.height
    do_twig_hide(properties, context)

    properties.has_wind_animation = False


def record(grove_collection, properties):
    """ Move built tree models to the record collection to keep things tidy. """

    record_collection = None
    for collection in grove_collection.children:
        if collection.name.startswith('Record'):
            record_collection = collection
            break

    if record_collection is None:
        record_collection = bpy.data.collections.new('Record')
        grove_collection.children.link(record_collection)

    # If rebuilding, for example after pruning, first remove the old build, then add the newly built tree.
    for obj in reversed(record_collection.objects):
        if 'grove_tree_age' in obj:
            if obj['grove_tree_age'] == properties.age:
                # print('The Grove in Blender - Removing old yearly build.')
                record_collection.objects.unlink(obj)
                # Is this enough or should I also delete the object and its data?
            if properties.age != 0 and obj['grove_tree_age'] == 0:
                record_collection.objects.unlink(obj)
                # The zero-age object has no place in growth animation,
                # because year 1 will start from last year's shape.

    # Move new objects to growth collection.
    for obj in grove_collection.objects:
        if obj.type == 'MESH' and 'grove' in obj.data:
            record_collection.objects.link(obj)
            grove_collection.objects.unlink(obj)

            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert(data_path='hide_viewport', frame=-1)
            obj.keyframe_insert(data_path='hide_render', frame=-1)

            obj.hide_viewport = False
            obj.hide_render = False
            obj.keyframe_insert(data_path='hide_viewport', frame=0)
            obj.keyframe_insert(data_path='hide_render', frame=0)

            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert(data_path='hide_viewport', frame=4000)
            obj.keyframe_insert(data_path='hide_render', frame=4000)

            # Also key visibility for geometry nodes modifiers.
            # I would expect that object visibility would be enough, but it's very slow.
            for modifier in obj.modifiers:
                modifier.show_viewport = False
                modifier.keyframe_insert(data_path='show_viewport', frame=-1)
                modifier.show_viewport = True
                modifier.keyframe_insert(data_path='show_viewport', frame=0)
                modifier.show_viewport = False
                modifier.keyframe_insert(data_path='show_viewport', frame=4000)


def retime(grove_collection, properties):
    """ Retime keyframes for all growth steps after changing Interval. """
    
    # Support for Blender 4.4's slotted actions.
    if bpy.app.version[0] == 4 and bpy.app.version[1] > 3:
        retime_44(grove_collection, properties)
        return

    record_collection = None
    for collection in grove_collection.children:
        if collection.name.startswith('Record'):
            record_collection = collection
            break

    if record_collection is None:
        return

    record_interval = properties.record_interval
    start = properties.record_start_frame
    year = properties.age

    for obj in record_collection.objects:
        if obj.type == 'MESH' and 'grove' in obj.data and 'grove_tree_age' in obj:
            year = obj['grove_tree_age']
            if year == 0:
                continue

            frame_this_year = year * record_interval + start
            frame_last_year = frame_this_year - record_interval

            # Retime spring shape key.
            for fcurve in obj.data.shape_keys.animation_data.action.fcurves:
                if fcurve.data_path.find('SpringShape') != -1:
                    fcurve.keyframe_points[-1].co.x = frame_this_year
                    fcurve.keyframe_points[0].co.x = frame_last_year
                    fcurve.keyframe_points[0].interpolation = 'LINEAR'

                    if year == properties.age:
                        fcurve.keyframe_points[-1].co.x = frame_this_year + record_interval * 2.0
                        fcurve.keyframe_points[0].interpolation = 'CIRC'
                        fcurve.keyframe_points[0].easing = 'EASE_OUT'

                    fcurve.keyframe_points[-1].co.x -= 1
                    fcurve.keyframe_points[0].co.x -= 1

            # Retime visibility.
            for fcurve in obj.animation_data.action.fcurves:
                fcurve.keyframe_points[0].co.x = 0
                fcurve.keyframe_points[-1].co.x = frame_this_year
                fcurve.keyframe_points[1].co.x = frame_last_year

                if year == properties.age:
                    fcurve.keyframe_points[-1].co.x = 5000
                    # fcurve.keyframe_points[-1].co.y = 0
                    # Instead of inserting a keyframe far, far away to keep last year visible,
                    # change the last keyframe to keep it visible.
                # else:
                #     fcurve.keyframe_points[-1].co.y = 1


def retime_44(grove_collection, properties):
    """ Version for Blender 4.4 - retime keyframes for all growth steps after changing Interval. """
    
    record_collection = None
    for collection in grove_collection.children:
        if collection.name.startswith('Record'):
            record_collection = collection
            break
    
    if record_collection is None:
        return
    
    record_interval = properties.record_interval
    start = properties.record_start_frame
    year = properties.age
    
    for obj in record_collection.objects:
        if obj.type == 'MESH' and 'grove' in obj.data and 'grove_tree_age' in obj:
            year = obj['grove_tree_age']
            if year == 0:
                continue
    
            frame_this_year = year * record_interval + start
            frame_last_year = frame_this_year - record_interval
            
            if obj.animation_data:
                strip = obj.animation_data.action.layers[0].strips[0]
                for slot in obj.animation_data.action.slots:
                    channel_bag = strip.channelbag(slot)
                    for fcurve in channel_bag.fcurves:
                        if fcurve.data_path.find('SpringShape') != -1:
                            # Retime spring shape key.
                            fcurve.keyframe_points[-1].co.x = frame_this_year
                            fcurve.keyframe_points[0].co.x = frame_last_year
                            fcurve.keyframe_points[0].interpolation = 'LINEAR'
                        
                            if year == properties.age:
                                fcurve.keyframe_points[-1].co.x = frame_this_year + record_interval * 2.0
                                fcurve.keyframe_points[0].interpolation = 'CIRC'
                                fcurve.keyframe_points[0].easing = 'EASE_OUT'
                        
                            fcurve.keyframe_points[-1].co.x -= 1
                            fcurve.keyframe_points[0].co.x -= 1
                        else:
                            # Retime visibility.
                            fcurve.keyframe_points[0].interpolation = 'CONSTANT'
                            fcurve.keyframe_points[1].interpolation = 'CONSTANT'
                            fcurve.keyframe_points[2].interpolation = 'CONSTANT'
                            fcurve.keyframe_points[0].co.x = 0
                            fcurve.keyframe_points[-1].co.x = frame_this_year
                            fcurve.keyframe_points[1].co.x = frame_last_year
                            
                            if year == properties.age:
                                fcurve.keyframe_points[-1].co.x = 5000


def add_spring_shape(properties, model_spring, obj):
    """ Add a shape key to the tree object where new growth is shortened considerably.
        This allows smooth growth animation. """

    obj.shape_key_add(name='Base', from_mix=False)

    shape_key = obj.shape_key_add(name='SpringShape', from_mix=False).data
    shape = model_spring.get_points_flat()
    shape_key.foreach_set("co", shape)

    obj.data.attributes.new("UVMapSpring", 'FLOAT2', 'CORNER').data.foreach_set("vector", model_spring.get_uvs_flat())

    # Insert keyframes for this shape.
    record_interval = properties.record_interval
    frame_this_year = properties.age * record_interval
    frame_last_year = frame_this_year - record_interval

    channel = obj.data.shape_keys.key_blocks[-1]
    channel.interpolation = 'KEY_LINEAR'
    channel.value = 1.0
    channel.keyframe_insert("value", frame=frame_last_year)
    channel.value = 0.0
    channel.keyframe_insert("value", frame=frame_this_year)

    obj.data.shape_keys.animation_data.action.fcurves[0].keyframe_points[0].interpolation = 'LINEAR'
    obj.data.shape_keys.animation_data.action.fcurves[0].keyframe_points[1].interpolation = 'LINEAR'


def clean_grove(grove_collection, roots=False):
    """ Remove all trees from the active Grove collection, for a clean start. """

    objects_to_delete = []

    for i in reversed(range(len(grove_collection.objects))):
        obj = grove_collection.objects[i]
        mesh = obj.data

        if 'grove_roots' in obj:
            objects_to_delete.append(obj)
        if not roots:
            # If only cleaning up roots, skip anything that is not a root.
            if obj.type == 'MESH' and 'grove' in mesh:
                objects_to_delete.append(obj)
            elif obj.type == 'ARMATURE' and 'grove_skeleton' in obj:
                objects_to_delete.append(obj)

    # Remove outside the loop to be safe.
    for obj in objects_to_delete:
        if obj.type == 'ARMATURE':
            grove_collection.objects.unlink(obj)
            bpy.data.objects.remove(obj)
            continue
        mesh = obj.data
        grove_collection.objects.unlink(obj)
        bpy.data.objects.remove(obj)
        if not mesh.users:
            bpy.data.meshes.remove(mesh)


def clean_record(grove_collection):
    """ Remove all trees from the growth sequence collection, for a clean start. """

    record_collection = None
    for collection in grove_collection.children:
        if collection.name.startswith('Record'):
            record_collection = collection
            break

    if record_collection is None:
        return

    for i in reversed(range(len(record_collection.objects))):
        if not record_collection.objects:
            # If a user made a linked duplicate of a tree inside this collection,
            # a previous iteration of this loop may have deleted the mesh and thereby all objects that link
            # to it. This if clause prevents an index out of range error in this case.
            continue

        obj = record_collection.objects[i]
        mesh = obj.data

        if obj.type == 'MESH' and 'grove' in mesh:
            record_collection.objects.unlink(obj)
            bpy.data.meshes.remove(mesh)


def create_tree_object(model, properties, context, roots=False):
    """ Advanced Mesh, Adaptive Mesh. Build branches with adaptive resolution, UV unwrapping,
        vertex groups and vertex colors. """

    # Load bark texture and calculate UV aspect ratio.
    if exists(properties.texture_bark):
        img = bpy.data.images.load(properties.texture_bark, check_existing=True)
        if img.size[0] == 0 or img.size[1] == 0:
            # Invalid image file.
            texture_aspect_ratio = 0.5
            properties.report_string = 'Selected bark texture is an invalid image file.'
        else:
            texture_aspect_ratio = img.size[0] / img.size[1]
    else:
        img = None
        texture_aspect_ratio = 3.0

    properties.texture_aspect_ratio = texture_aspect_ratio

    # Name branches object after the preset.
    mesh = bpy.data.meshes.new(str(properties.preset_name))
    
    mesh.from_pydata(model.get_points_as_tuples(), [], model.faces, shade_flat=False)

    try:
        bark_material = create_bark_material(img, properties, context)
        mesh.materials.append(bark_material)
    except:
        if not bark_material:
            print("WARNING:")
            print("Something went wrong while creating the bark material.")
            print("You may be using an unofficial release of Blender, an incompatible render engine, ")
            print("or an incompatible OCIO configuration. You will have to create your material manually.")
            bark_material = bpy.data.materials.new("TheGroveBranches")
            bark_material.diffuse_color = Vector((0.12, 0.09, 0.07, 1.0))
            bark_material.metallic = 0.0
            bark_material.roughness = 1.0
            properties.bark_material_name = bark_material.name
            bark_material['original_name'] = bark_material.name
            mesh.materials.append(bark_material)

    obj = bpy.data.objects.new(str(properties.preset_name), mesh)
    mesh = obj.data  # Just to be sure. This could fix the unstable behavior.

    # Add vertex layers and material groups.

    material_indices = [0] * len(model.faces)

    if not roots:
        if context.preferences.addons[__package__.split('.')[0]].preferences.edition != 'STARTER':
            mesh.attributes.new("gr_age", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_age)
            mesh.attributes.new("gr_branch_id", 'INT', 'FACE').data.foreach_set("value", model.face_attribute_branch_id)
            mesh.attributes.new("gr_branch_id_parent", 'INT', 'FACE').data.foreach_set("value", model.face_attribute_branch_id_parent)
        mesh.attributes.new("gr_dead", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_dead)
        mesh.attributes.new("gr_twig_long", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_long)
        mesh.attributes.new("gr_twig_short", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_short)
        mesh.attributes.new("gr_twig_upward", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_upward)
        mesh.attributes.new("gr_twig_dead", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_twig_dead)
        mesh.attributes.new("gr_end", 'BOOLEAN', 'FACE').data.foreach_set("value", model.face_attribute_end)
        mesh.attributes.new("gr_direction", 'FLOAT_VECTOR', 'FACE').data.foreach_set("vector", model.get_directions_flat())

    mesh.attributes.new("gr_thickness", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_thickness)
    if context.preferences.addons[__package__.split('.')[0]].preferences.edition != 'STARTER':
        mesh.attributes.new("gr_pitch", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_pitch)
        mesh.attributes.new("gr_photosynthesis", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_photosynthesis)
        mesh.attributes.new("gr_shade", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_shade)
        mesh.attributes.new("gr_vigor", 'FLOAT', 'POINT').data.foreach_set("value", model.point_attribute_vigor)
        mesh.attributes.new("gr_bone_id", 'INT', 'POINT').data.foreach_set("value", model.point_attribute_bone_id)
    mesh.attributes.new("UVMap", 'FLOAT2', 'CORNER').data.foreach_set("vector", model.get_uvs_flat())
    mesh.attributes.new("UVMapIslands", 'FLOAT2', 'CORNER').data.foreach_set("vector", model.get_uv_islands_flat())

    # Set material indices for twig duplicator faces.
    mesh.polygons.foreach_set("material_index", material_indices)

    if not roots:
        mesh['grove'] = 'Grown with Grove.'
    obj.location = Vector((model.location.x, model.location.y, model.location.z)) * properties.simulation_scale

    if not roots:
        create_geometry_nodes(properties, obj)

    return obj


def update_twigs(properties, grove_collection):
    """ Update twigs systems to instance the correct object or collection.
        Set the number of lateral twigs to match the density parameter. """

    collections = [grove_collection]
    if properties.record_enabled:
        if 'Record' in grove_collection.children:
            collections.append(grove_collection.children['Record'])

    tree_objects = []
    for col in collections:
        for obj in col.objects:
            if 'grove' in obj:
                tree_objects.append(obj)

    for obj in tree_objects:
        name = 'Twig'
        if name in obj.modifiers:
            mod = obj.modifiers[name]

            interface = mod.node_group.interface.items_tree

            mod[interface['Use Collections'].identifier] = properties.do_twig_collections
            mod[interface['Density'].identifier] = properties.twig_density

            if properties.do_twig_collections:
                mod[interface['Long Twig Collection'].identifier] = properties.twig_collection_long
                if properties.twig_collection_upward:
                    mod[interface['Upward Twig Collection'].identifier] = \
                        properties.twig_collection_upward
                else:
                    mod[interface['Upward Twig Collection'].identifier] = \
                        properties.twig_collection_long
                mod[interface['Dead Twig Collection'].identifier] = properties.twig_collection_dead
                mod[interface['Short Twig Collection'].identifier] = properties.twig_collection_short
            else:
                mod[interface['Long Twig'].identifier] = properties.twig_object_end
                if properties.twig_object_upward:
                    mod[interface['Upward Twig'].identifier] = properties.twig_object_upward
                else:
                    mod[interface['Upward Twig'].identifier] = properties.twig_object_end
                mod[interface['Dead Twig'].identifier] = properties.twig_object_dead
                mod[interface['Short Twig'].identifier] = properties.twig_object_side

            if properties.twig_menu == t('twig_no_twigs'):
                mod.show_viewport = False
                mod.show_render = False
                mod[interface['Long Twig Collection'].identifier] = None
                mod[interface['Short Twig Collection'].identifier] = None
                mod[interface['Upward Twig Collection'].identifier] = None
                mod[interface['Dead Twig Collection'].identifier] = None
                mod[interface['Long Twig'].identifier] = None
                mod[interface['Short Twig'].identifier] = None
                mod[interface['Upward Twig'].identifier] = None
                mod[interface['Dead Twig'].identifier] = None
            else:
                mod.show_viewport = True
                mod.show_render = True

        name = 'Scale'
        if name in obj.modifiers:
            mod = obj.modifiers[name]
            interface = mod.node_group.interface.items_tree
            mod[interface['Scale'].identifier] = properties.simulation_scale


def create_geometry_nodes(properties, obj):
    """ Append the geometry nodes modifiers from an external file. """

    parent_dir = dirname(dirname(__file__))
    file = join(join(parent_dir, "Resources"), "GeometryNodes.blend")

    grove_id = str(properties.unique_id)

    node_trees = ['GroveGNScale', 'GroveGNTwig', 'GroveGNBreeze']

    for node_tree in node_trees:
        if node_tree + grove_id not in bpy.data.node_groups:
            with bpy.data.libraries.load(file) as (library_file, this_file):
                if node_tree in library_file.node_groups:
                    i = library_file.node_groups.index(node_tree)
                    this_file.node_groups.append(library_file.node_groups[i])

            for group in this_file.node_groups:
                group.name = group.name.split('.')[0] + grove_id

        modifier = obj.modifiers.new(type='NODES', name=node_tree.split('GroveGN')[1])
        modifier.node_group = bpy.data.node_groups[node_tree + grove_id]
        modifier.show_in_editmode = False


def create_bark_material(img, properties, context):
    """ Create a bark material. """

    if properties.bark_material_name != '':
        if properties.bark_material_name in bpy.data.materials:
            return bpy.data.materials[properties.bark_material_name]
        else:
            for material in bpy.data.materials:
                if 'original_name' in material:
                    if material['original_name'] == properties.bark_material_name:
                        return material

    # Create a new bark material.
    bark_material = bpy.data.materials.new("TheGroveBranches")
    # Set the viewport color. To make branches more visible, make them darker if the background is dark.
    bark_material.diffuse_color = Vector((0.12, 0.09, 0.07, 1.0))
    bark_material.metallic = 0.0
    bark_material.roughness = 1.0

    # Create material nodes for Cycles or Eevee. These are the only render engine that Grove creates materials for.
    # If a different render engine is in use, switch to Eevee, because Cycles is an add-on that can be disabled.
    # Cycles and Eevee material nodes are the same.
    render_engine = context.scene.render.engine
    if render_engine not in ['CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT']:
        print('The Grove in Blender - Temporarily switching to Eevee render engine to create materials.')
        try:
            context.scene.render.engine = 'BLENDER_EEVEE'
        except:
            context.scene.render.engine = 'BLENDER_EEVEE_NEXT'

    bark_material.use_nodes = True
    node_tree = bark_material.node_tree

    # The Blender preference Interface > Translate > New Data can cause trouble.
    # It translates automatically created nodes 'Principled BSDF' and 'Material Output'.
    # Before moving forward, first make sure the nodes are properly named.
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.name = 'Principled BSDF'
        if node.type == 'OUTPUT_MATERIAL':
            node.name = 'Material Output'

    uv_node = node_tree.nodes.new('ShaderNodeAttribute')
    uv_node.location = (-1400, -90)
    uv_node.name = 'UVMapAttribute'
    uv_node.attribute_type = 'GEOMETRY'
    uv_node.attribute_name = 'UVMap'

    texture_node = node_tree.nodes.new('ShaderNodeTexImage')
    texture_node.location = (-540, 120)
    texture_node.name = 'Bark Texture'
    texture_node.label = 'Bark Texture'

    bark_normal_node = node_tree.nodes.new('ShaderNodeTexImage')
    bark_normal_node.location = (-720, -400)
    bark_normal_node.name = 'Bark Normal'
    bark_normal_node.label = 'Bark Normal'

    # Connect the UV Map to the bark textures.
    node_tree.links.new(texture_node.inputs['Vector'], uv_node.outputs['Vector'])
    node_tree.links.new(bark_normal_node.inputs['Vector'], uv_node.outputs['Vector'])

    normal_map_node = node_tree.nodes.new('ShaderNodeNormalMap')
    normal_map_node.location = (-420, -220)

    bevel_node = node_tree.nodes.new('ShaderNodeBevel')
    bevel_node.location = (-200, -220)
    bevel_node.samples = 8
    bevel_node.inputs['Radius'].default_value = 0.1

    principled_node = node_tree.nodes.get('Principled BSDF')
    principled_node.inputs['Specular IOR Level'].default_value = 0.35
    principled_node.inputs['Roughness'].default_value = 0.75
    principled_node.inputs['IOR'].default_value = 1.4
    principled_node.location = (0, 300)

    node_tree.nodes.get('Material Output').location = (320, 300)

    # Add extra awesome shading nodes.
    attribute_node = node_tree.nodes.new('ShaderNodeAttribute')
    attribute_node.location = (-1100, 300)
    attribute_node.width = 200
    attribute_node.attribute_name = 'gr_thickness'

    math_node = node_tree.nodes.new('ShaderNodeMath')
    math_node.location = (-840, 300)
    math_node.label = 'Invert'
    math_node.operation = 'SUBTRACT'
    math_node.inputs[0].default_value = 1.0

    node_tree.links.new(math_node.inputs[1], attribute_node.outputs['Fac'])

    math_node_2 = node_tree.nodes.new('ShaderNodeMath')
    math_node_2.location = (-640, 300)
    math_node_2.operation = 'POWER'
    math_node_2.inputs[1].default_value = 2.0

    node_tree.links.new(math_node_2.inputs[0], math_node.outputs['Value'])

    math_node_3 = node_tree.nodes.new('ShaderNodeMath')
    math_node_3.location = (-440, 300)
    math_node_3.operation = 'MULTIPLY'
    math_node_3.inputs[1].default_value = 0.5

    node_tree.links.new(math_node_3.inputs[0], math_node_2.outputs['Value'])

    mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
    mix_node.location = (-220, 220)
    mix_node.blend_type = 'MIX'
    mix_node.inputs['Color2'].default_value = (0.0, 0.0, 0.0, 0.0)

    node_tree.links.new(mix_node.inputs['Fac'], math_node_3.outputs['Value'])
    node_tree.links.new(mix_node.inputs['Color1'], texture_node.outputs['Color'])

    # Nodes to reduce the effect of the normal map on thinner branches.
    attribute_node_2 = node_tree.nodes.new('ShaderNodeAttribute')
    attribute_node_2.location = (-880, -220)
    attribute_node_2.width = 200
    attribute_node_2.attribute_name = 'gr_thickness'

    math_node = node_tree.nodes.new('ShaderNodeMath')
    math_node.location = (-620, -220)
    math_node.operation = 'POWER'
    math_node.inputs[1].default_value = 0.5

    node_tree.links.new(math_node.inputs[0], attribute_node_2.outputs['Fac'])

    # Link all nodes together.
    node_tree.links.new(normal_map_node.inputs['Strength'], math_node.outputs['Value'])
    node_tree.links.new(normal_map_node.inputs['Color'], bark_normal_node.outputs['Color'])
    node_tree.links.new(principled_node.inputs['Normal'], bevel_node.outputs['Normal'])
    node_tree.links.new(bevel_node.inputs['Normal'], normal_map_node.outputs['Normal'])
    node_tree.links.new(principled_node.inputs['Base Color'], mix_node.outputs['Color'])

    for node in node_tree.nodes:
        node.select = False

    if img is not None:
        texture_node.image = img

    apply_normal_map(properties, bark_material)

    if render_engine not in ['CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT']:
        # Switch back to the previous render engine.
        context.scene.render.engine = render_engine

    properties.bark_material_name = bark_material.name
    bark_material['original_name'] = bark_material.name

    return bark_material


def change_simulation_scale(properties, context):
    """ Simulation scale will scale the entire tree while keeping the twigs at their realistic scale. """

    collections = [context.collection]
    if properties.record_enabled:
        # Flexibility for recording growth animation, also rescale previously recorded steps.
        if 'Record' in context.collection.children:
            collections.append(context.collection.children['Record'])

    scale = properties.simulation_scale

    for col in collections:
        for obj in col.objects:
            if 'Scale' in obj.modifiers:
                modifier = obj.modifiers['Scale']
                interface = modifier.node_group.interface.items_tree
                modifier[interface['Scale'].identifier] = scale
                obj.update_tag(refresh={'DATA'})
            
            if 'grove_skeleton' in obj:
                obj.scale = (scale, scale, scale)


def do_twig_hide(properties, context):
    """ Hide twigs in the viewport for a clear view of the branches or a faster viewport. """

    collections = [context.collection]
    if properties.record_enabled:
        if 'Record' in context.collection.children:
            collections.append(context.collection.children['Record'])

    for col in collections:
        for obj in col.objects:
            if 'grove' in obj:
                if 'Twig' in obj.modifiers:
                    modifier = obj.modifiers['Twig']
                    # modifier.show_viewport = not properties.twig_hide
                    # Below is a hack to make it update.
                    modifier.show_viewport = False
                    modifier.show_viewport = True

                    interface = modifier.node_group.interface.items_tree

                    if properties.twig_menu == t('twig_no_twigs'):
                        # modifier.show_viewport = False
                        modifier[interface['Hide Twigs'].identifier] = True
                    modifier[interface['Hide Twigs'].identifier] = properties.twig_hide


def set_view_detail(properties):
    """ Viewport Detail. Add and/or configure Decimate modifiers on twig objects.
        Skip if the twig object is not a mesh, for example an empty object duplicating a collection. """

    decimate_objects = []

    if properties.do_twig_collections:
        for twig_collection in [
                properties.twig_collection_long,
                properties.twig_collection_short,
                properties.twig_collection_upward,
                properties.twig_collection_dead]:
            if not twig_collection:
                continue
            for twig_object in twig_collection.objects:
                if twig_object.type != 'MESH':
                    continue

                decimate_objects.append(twig_object)

    else:
        for twig_object in [
                properties.twig_object_end,
                properties.twig_object_side,
                properties.twig_object_upward,
                properties.twig_object_dead]:
            # If the twig field contains a name that is no longer valid, or if the field is simply emtpy.
            if not twig_object:
                continue
            if twig_object.type != 'MESH':
                continue
            decimate_objects.append(twig_object)

    for twig_object in decimate_objects:
        decimate_modifier = None

        # Find a decimate modifier.
        for modifier in twig_object.modifiers:
            if modifier.type == 'DECIMATE':
                decimate_modifier = modifier
                break

        # If no modifier is found, add one.
        if not decimate_modifier:
            decimate_modifier = twig_object.modifiers.new("Viewport Detail", 'DECIMATE')

        if decimate_modifier:
            decimate_modifier.ratio = properties.twig_view_detail
            if len(twig_object.data.polygons) < 200:
                decimate_modifier.ratio = 1.0
            decimate_modifier.show_viewport = True
            decimate_modifier.show_render = False


def update_twigs_callback(properties, context):
    """ A callback function attached to properties that require an update of the twigs particle system.
        For the future. """

    update_twigs(properties, context.collection)
    set_view_detail(properties)
    update_twigs_density(properties, context.collection)


def update_wind_breeze(properties, context):
    """ A callback function attached to the breeze slider. """

    collection = context.collection
    collections = [collection]
    if properties.record_enabled:
        if 'Record' in collection.children:
            collections.append(collection.children['Record'])

    for col in collections:
        for obj in col.objects:
            if 'grove' in obj:
                if 'Breeze' in obj.modifiers:
                    modifier = obj.modifiers['Breeze']
                    interface = modifier.node_group.interface.items_tree
                    modifier[interface['Strength'].identifier] = properties.wind_breeze
                    obj.update_tag(refresh={'OBJECT'})


def update_twigs_density_callback(properties, context):
    """ This callback is attached to the density parameter.
        The callback needs these two arguments, but for use separate from this parameter,
        a different collection may be passed, that's why there's two functions. """

    update_twigs_density(properties, context.collection)


def update_twigs_density(properties, collection):
    """ A callback function attached to properties that require an update of the twigs particle system.
        For the future. """

    collections = [collection]
    if properties.record_enabled:
        if 'Record' in collection.children:
            collections.append(collection.children['Record'])

    for col in collections:
        for obj in col.objects:
            if 'grove' in obj:
                if 'Twig' in obj.modifiers:
                    modifier = obj.modifiers['Twig']
                    interface = modifier.node_group.interface.items_tree
                    modifier[interface['Density'].identifier] = properties.twig_density
                    obj.update_tag(refresh={'DATA'})


def vertex_group_layer_from_data(obj, name, data):
    """ Add a new named Vertex Group layer to the given object. Fill it with the given data, a list of floats.
        The list indexing matches the mesh's vertex indexing.

        Create an index list and join it with the values.
        Sort the weights, some groups have many same values; set them in one go.
        Split the array where the value changes.
        This helped: http://stackoverflow.com/questions/31863083/python-split-numpy-array-based-on-values-in-the-array
        Skip adding zero weight indices, it makes selecting impossible.

        This brute force, simple code works, but the optimized version is up to 10x as fast.
        for i, weight in enumerate(data):
        add([i], weight, 'REPLACE') """

    vertex_group = obj.vertex_groups.new(name=t(name))
    add = vertex_group.add

    # Round to 1 decimal, to reduce the number of discrete groups.
    # Roughly 6 times as fast for thickness layer.
    data_rounded = round(data, 1)
    indices = arange(0, len(data))
    data_indexed = column_stack((indices, data_rounded))
    data_sorted = data_indexed[argsort(data_indexed[:, 1])]
    data_split = split(data_sorted, where(diff(data_sorted[:, 1]))[0] + 1)

    for chunk in data_split:
        if chunk[0][1] == 0.0:
            continue
        add(chunk[:, 0].astype(int).tolist(), chunk[0][1], 'REPLACE')


def vertex_colors_layer_from_data(obj, name, data):
    """ Add a new named Vertex Colors layer to the given mesh object. Fill the layer with the given data, an array
        of floats. The list indexing matches the mesh's vertex indexing.

        Vertex colors can be used in Cycles materials with the Attribute node. They are very different from
        Vertex Groups. Similar to UV's, each corner of each face has a separate value. A vertex with four attached
        faces has 4 color values, one for each face.

        Blender stores Vertex Colors as layers in the object data. A layer is a list of tuples representing a color.
        The order of this list is defined by the object's mesh's loops list. Loops is a list of integers representing
        vertex indices for each face for each vertex in the face.

        This version is very different from all other attempts found on the internet. It was a puzzle to find
        a way to solve it without for loops. The solution uses numpy and is about 4x as fast as for loops. """

    vertex_colors = obj.data.vertex_colors.new(name=t(name))

    if vertex_colors is None:
        return False

    indices = empty([len(vertex_colors.data)], dtype=int)
    obj.data.loops.foreach_get("vertex_index", indices)

    colors = take(data, indices)
    colors = repeat(colors, 3)

    # Add alpha to colors.
    colors.shape = (colors.shape[0] // 3, 3)
    alphas = ones(colors.shape[0])
    alphas.shape = (1, alphas.shape[0])
    colors = concatenate((colors, alphas.T), axis=1)

    colors = colors.flatten()
    colors = colors.tolist()  # foreach_set is over twice as fast when using a regular list over a numpy array.
    vertex_colors.data.foreach_set("color", colors)

    return True
