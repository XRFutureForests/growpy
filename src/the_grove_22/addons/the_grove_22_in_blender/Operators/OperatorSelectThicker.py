
""" Select all geometry belonging to branch nodes that are thicker than the threshold value.
    This operator uses the Thickness attribute.

    Copyright 2018 - 2025, Wybren van Keulen, The Grove. """


import bpy
from bpy.types import Operator
import numpy as np

from bpy.props import  FloatProperty

from ..Languages.Translation import t


class GROVE22_OT_SelectThicker(Operator):
    """ A tool to easily select a tree branch, all its sub branches and their twig duplicator triangles. """

    bl_idname = "the_grove_22.select_thicker"
    bl_label = t('select_thicker')
    bl_description = t('select_thicker_tt')
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name=t('select_thicker_threshold'), description=t('select_thicker_tt'),
        default=0.1, min=0.0, max=1.0, step=10, precision=1, subtype='FACTOR')

    @classmethod
    def poll(cls, context):
        """ Check if in mesh edit mode. If not, the operator won't show up in the search bar. """

        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        
        # Deselect all, because setting the .select_vert attribute always includes the original selection.
        # Even an array filled with False will not do the trick, and neither will a mesh update.
        # Looks like a bug in Blender,
        bpy.ops.mesh.select_all(action = 'DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        obj = context.active_object

        # Read the thickness attribute from the mesh and store it in a numpy array for fast processing.
        if 'gr_thickness' in obj.data.attributes:
            thickness = np.empty([len(obj.data.vertices)], dtype=float)
            obj.data.attributes['gr_thickness'].data.foreach_get("value", thickness)
        else:
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            self.report({'ERROR_INVALID_INPUT'}, 'No thickness attribute found.')
            return {'CANCELLED'}

        selection = thickness > self.threshold

        # The old way.
        # vertices = obj.data.vertices
        # vertices.foreach_set("select", selection)

        selection_attribute = obj.data.attributes.new(".select_vert", "BOOLEAN", "POINT")
        selection_attribute.data.foreach_set("value", selection)

        # Convert the selection from vertices to faces as well.
        for face in obj.data.polygons:
            if selection[face.vertices[0]]:
                face.select = True

        # Finish up by returning to edit mode.
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        return {'FINISHED'}
