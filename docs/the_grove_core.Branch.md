# [the_grove_core](./the_grove_core.html).Branch

The structure of The Grove in a nutshell…
  * a grove is a list of branches that represent the trunks of the trees
  * a branch is a list of nodes
  * a node has a thickness, a position and a direction
  * the first node’s direction points to the the second node’s position, and so on
  * each node has a list of side branches



To access the first tree in a grove:
```python
g = Grove()
branch = g.trees[0]
```



As you can see, a tree is simply a branch itself, and the trunk of the tree is nothing different from any other branch. Each node of a branch can have a number of side branches. Here’s an example of accessing a side branch:
```python
side_branch = branch.nodes[4].side_branches[0]
```




# Traverse the tree

Here’s a way for to recursively iterate over the tree’s branches. For a branch in Grove.trees, you can:
```python
def recursive_function(branch):
    for node in branch.nodes:
        # Make changes to nodes here, from base to tip.

        if node.side_branches:
            for side_branch in node.side_branches():
                return_value = recursive_function(side_branch)
                # Make changes to nodes here, from tip to base.

    # Here you can make changes to the branch.

```



Then let’s get the first tree in a grove and call this function:
```python
recursive_function(grove.trees[0])
```



You could also reverse the traversal of the branch nodes using:
```python
for node in reversed(branch.nodes):
```



This way you can add up all kinds of useful information all the way to the base of the tree.



#the grove/the grove core/python api#