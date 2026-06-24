# [the_grove_core](./the_grove_core.html).Properties

Properties store all natural growth parameters that together define how the tree grows. These properties can be stored in a preset / seed for future use. There are dozens of properties, which will not be listed here. To learn more about them, check the tooltips in _The Grove in Blender_ , especially with _Python Tooltips_ enabled so they show the Python name.



Here’s how to change growth properties in Python. This example shows that you can change properties then keep growing additional years, so you can simulate changing environmental conditions.



```python
grove = the_grove_core.Grove()

grove.simulate(10)

props = grove.get_properties()
props.grow_length = 0.2
props.favor_bright = 0.7
grove.set_properties(props)

grove.simulate(10)
```



#the grove/the grove core/python api#