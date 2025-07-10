# [the_grove_core](./the_grove_core.html).Node

A branch is a list of connected nodes, and every node has a list of side branches.
  * Node.direction (Vector) - A relative Vector that points from this node to the next node.
  * Node.pos (Vector) - The absolute position of the node after bending.
  * Node.radius (float) - Half the thickness of the branch section at that point. This grows every year in the process of secondary growth.
  * Node.thickness (float) - A normalized value where 1.0 is the thickest point at the base of the tree.
  * Node.side_branches ([branch]) - Every node can have a number of side branches.



#the grove/the grove core/python api#