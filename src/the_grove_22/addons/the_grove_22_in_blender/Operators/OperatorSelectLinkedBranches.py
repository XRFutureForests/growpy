
""" Part of Grove, this operator is a tool to easily select branches
    after the tree is done growing.

    It works by selecting one or more vertices in the branch mesh.
    The operator to extends the selection to the whole branch,
    its sub branches and its twig duplicators.

    Internally, it works by using custom face attributes that are written to the
    tree mesh by The Grove. Two layers are written:
        - The attribute gr_branch_id stores a unique branch identifier for each face.
        - The attribute gr_branch_id_parent stores the parent branch id for each face.

    Copyright 2018 - 2025, Wybren van Keulen, The Grove. """


import bpy
from bpy.types import Operator
import numpy as np

from ..Languages.Translation import t


class GROVE22_OT_SelectLinkedBranches(Operator):
    """ A tool to easily select a tree branch, all its sub branches and their twig duplicator triangles. """

    bl_idname = "the_grove_22.select_linked_branches"
    bl_label = t('select_linked_branches')
    bl_description = t('select_linked_branches_tt')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Check if in mesh edit mode. If not, the operator won't show up in the search bar. """

        return context.mode == 'EDIT_MESH'

    def execute(self, context):

        # Start by exiting edit mode. Can it be done without this...
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        obj = bpy.context.active_object
        faces = obj.data.polygons

        # Extend the selection from vertices and edges to faces.
        for face in obj.data.polygons:
            for vertex in face.vertices:
                if obj.data.vertices[vertex].select:
                    face.select = True

        # Read the parent and branch index attributes from the mesh and store them in a numpy array for fast processing.
        if 'gr_branch_id_parent' in obj.data.attributes and 'gr_branch_id' in obj.data.attributes:
            parent = np.empty([len(obj.data.polygons)], dtype=int)
            obj.data.attributes['gr_branch_id_parent'].data.foreach_get("value", parent)
            branch = np.empty([len(obj.data.polygons)], dtype=int)
            obj.data.attributes['gr_branch_id'].data.foreach_get("value", branch)
        else:
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            self.report({
                'ERROR_INVALID_INPUT'},
                'This does not appear to be a tree grown with Grove. \n'
                'For this tool to work, it needs two custom attributes \n'
                'that were not found in this mesh.')
            return {'CANCELLED'}

        # Read the user selection and store it in a numpy array for fast processing.
        selection = np.zeros(len(faces), dtype='bool')
        faces.foreach_get('select', selection)

        # Extend user selection to entire branches.
        user_selected_branches = branch[selection]
        user_selected_branches = np.unique(user_selected_branches)
        selection = np.in1d(branch, user_selected_branches)

        # Then recursively select sub branches.
        for _ in range(10):
            selected_branches = branch[selection]
            selected_branches = np.unique(selected_branches)
            selection_side_branches = np.in1d(parent, selected_branches)
            # Add to the existing selection.
            selection = np.logical_or(selection, selection_side_branches)

        # Select the entire branch and all its sub branches and twig duplicators.
        faces.foreach_set("select", selection)

        # Finish up by returning to edit mode.
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        return {'FINISHED'}
