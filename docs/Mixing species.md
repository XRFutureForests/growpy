# Mixing species

The definition of a grove is a group of same-species trees growing together. The Grove says true to this concept, so all the trees in a single grove share the same growth characteristics.



When you want to grow a forest with more than just one species, you can create multiple groves and grow them together. The Blender add-on has the _Grow Together_ operator that does just this; you can look at its source for inspiration in `Operators/OperatorGrowTogether.py`.



Here’s the specific part we’re interested in - it makes each tree from all groves share the same light environment. We first create the groves and set their growth properties, and then put them in a Python list. In the example below I simply create two default groves. Then for each new flush we collect the shade geometry from all groves into one pile. Then we calculate the shade for each separate grove and simulate that grove for one additional flush. Note the specific order - shade needs to be calculated before simulating the next flush of growth.



```python
list_of_groves = [core.Grove(), core.Grove()]


# Here you can set the growth properties for each of the groves.

for i in range(number_of_years)
    coords = []
    for i, grove in enumerate(list_of_groves):
        coords.extend(grove.create_shade_geometry_coords())

    for i, grove in enumerate(self.list_of_groves):
        grove.calculate_shade_together(coords)
        grove.simulate(1)
```



The low-level part of the simulation in The Grove Core is not exposed to the Python API, because it follows a very specific sequence that would be useless to hook into with Python. But shade calculation is one of the steps of the simulation which I did decide to expose in the API, specifically for this purpose.



#the grove/the grove core/python api#