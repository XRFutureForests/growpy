
""" Replant trees to a new location and rotation.
    Move trees around, rotate them or even simulate a dropped tree that continues growing.

    Copyright 2020 - 2025, Wybren van Keulen, The Grove """


from bpy.types import Operator
from mathutils import Vector

from . import OperatorBuild
from ..Languages.Translation import t
from ..File import load_grove, save_grove

from ..Core import import_core
the_grove_core = import_core()


class GROVE22_OT_Replant(Operator):

    bl_idname = "the_grove_22.replant"
    bl_label = t('replant_grove')
    bl_description = t('replant_grove_tt')
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = []
        self.pile_of_branches = []

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out. """

        return context.mode == 'OBJECT'

    def execute(self, context):

        if not check_transformations(context):
            return {'CANCELLED'}

        properties = context.collection.GROVE22_Properties
        self.grove = load_grove(context.collection)

        if not self.grove:
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        if replant(context.collection, properties, self.grove):
            context.window.cursor_modal_set('WAIT')
            OperatorBuild.build(context, properties, self.grove, context.collection, rebuild=True)
            properties['height'] = self.grove.height
            save_grove(self.grove, context.collection)
            context.window.cursor_modal_restore()

        return {'FINISHED'}

    def invoke(self, context, _):
        return self.execute(context)


def check_transformations(context):
    """ First check if any trees were moved, without loading the grove to save time. """

    grove_collection = context.collection

    for obj in grove_collection.objects:
        if 'grove_tree_id' not in obj:
            continue
        _, rotation, _ = obj.matrix_world.decompose()
        new_loc = obj.location
        if 'grove_tree_origin' in obj:
            old_loc = Vector(obj['grove_tree_origin'])
        else:
            return True

        translation = new_loc - old_loc
        if translation.length == 0.0 and rotation.x == rotation.y == rotation.z == 0.0:
            continue
        else:
            return True

    return False


def replant(grove_collection, properties, grove):
    """ Check every tree model for changes in location and rotation.
        Propagate these changes into the actual node data.
        This function is separate from the operator class, allowing it to be called from elsewhere. """

    did_something = False

    positions, directions = grove.get_tree_positions_and_directions()
    for obj in grove_collection.objects:
        if ('grove_tree_id' not in obj) or 'grove_roots' in obj:
            continue

        tree_id = obj['grove_tree_id']

        _, rotation, _ = obj.matrix_world.decompose()

        new_loc = obj.location / properties.simulation_scale
        old_loc = positions[tree_id]
        old_loc = Vector((old_loc.x, old_loc.y, old_loc.z))
        translation = new_loc - old_loc

        if translation.length == 0.0 and rotation.x == rotation.y == rotation.z == 0.0:
            continue

        did_something = True

        axis, angle = rotation.to_axis_angle()
        axis = the_grove_core.Vector(axis.x, axis.y, axis.z)
        q_grove = the_grove_core.Rotation(axis, angle)
        t_grove = the_grove_core.Vector(translation.x, translation.y, translation.z)

        grove.replant_tree(tree_id, t_grove, q_grove)

    return did_something
