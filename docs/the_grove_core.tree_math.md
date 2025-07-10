# [the_grove_core](./the_grove_core.html).tree_math

Most of these functions have to do with planting groups of trees in clumps, islands, rings and rows. The resulting list of tree positions should then be fed to add_variation to add randomness, delays and a starting direction. Lastly, in a for loop, add the trees to the grove with Grove.add_new_tree(position, direction, delay). Here’s an example:
```python
grove.clear_trees()  # remove the default tree

positions = the_grove_core.tree_math.plant_clump(
            8,  # number of trees

			1.0,  # distance between trees

            0.0  # clearing

        )

(positions, directions, delays) = the_grove_core.tree_math.add_variation(
        positions,
        0.0,  # random_shift

        0.4,  # diverge

        4,  # delay

        1,  # random_seed

    )

for i in range(len(positions)):
        grove.add_new_tree(positions[i], directions[i], delays[i])
```




### phyllotaxis_samples(number)  [vector]

Returns a list of location vectors with optimal distribution over the sky hemisphere. This is the same pattern as the distribution of seeds in a sunflower disc.



Parameters:
  * number (int) - Number of samples.




### phyllotaxis_samples_flat(number, space, random_factor)  [vector]

Optimal distribution over a flat disc shape equal to the seeds on a sunflower disc. Used to distribute trees in a natural pattern. Returns a list of vectors.



Parameters:
  * number (int) - Number of samples.
  * space (float) - Space between samples.
  * random_factor (float) - Random shift.




### plant_clump(number, space, clearing)  [vector]

Optimal distribution over a flat disc shape equal to the seeds on a sunflower disc. Used to distribute trees in a natural pattern. Returns a list of vectors.



Parameters:
  * number (int) - Number of trees.
  * space (float) - Average space between trees.
  * clearing (float) - Free space in the middle.




### plant_islands(islands_number, islands_space, trees_number, trees_space, randomize_number, random_shift, clearing, seed)  [vector]

A natural distribution of tree islands, basically clumps within clumps. Returns a list of location vectors.



Parameters:
  * islands_number (int)
  * islands_space (float)
  * trees_number (int)
  * trees_space (float)
  * randomize_number (int)
  * random_shift (float)
  * clearing (float)
  * seed (int)




### plant_rows(trees_number, tree_space, rows_number, rows_space, diamond)  [vector]

Create a forestry plantation, orchard, nursery or hedgerow. Returns a list of location vectors.



Parameters:
  * trees_number (int) - Number of trees per row.
  * tree_space (float) - Distance between each tree in a row.
  * rows_number (int) - Number of rows.
  * rows_space (float) - Distance between each row.
  * diamond (bool) - Shift every second row to get diagonal lines.





### plant_ring(number, radius)  [vector]

Plant a ring (or circle) of trees around the world origin. Returns a list of location vectors.



Parameters:
  * number (int) - Number of trees.
  * radius (float) - Radius of the circle.




### add_variation(positions, random_shift, diverge, delay, seed)  ([vector], [vector], [usize])

Take a list of tree locations, shift them around randomly, add random delays, and add rotation so that they diverge when getting close. Returns a tuple with a list of location vectors, a list of direction vectors, and a list of integer delays.





#the grove/the grove core/python api#