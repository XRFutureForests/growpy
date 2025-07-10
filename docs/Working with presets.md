# Working with presets

For presets, The Grove uses the ubiquitous file format JSON. This standard format is easy to read and write, and the json module comes with Python by default.



Here’s how to write presets:
```python
import the_grove_22_core
import json

preset_file = open('Ash.seed.json'), 'w')
preset_dictionary = {}

grove = the_grove_22_core.Grove()
props = grove.get_properties()

for prop in dir(props):
	key = prop
	value = getattr(props, prop)
	preset_dictionary[key] = value

json.dump(preset_dictionary, preset_file, indent=4)
preset_file.close()
```



You can read presets simply by using:
```python
props = the_grove_core.io.properties_from_json_string(str)
grove.set_properties(props)
```



Or if you want to do it the manual way that is the opposite of the example of writing presets:
```python
import the_grove_22_core
import json

path = dirname(__file__)
path = join(path, 'Ash.seed.json')
preset_dictionary = {}

grove = the_grove_22_core.Grove()
props = grove.get_properties() # Beware, this makes a copy!


with open(path, 'r') as preset_file:
    preset_dictionary = json.load(preset_file)

for key, value in preset_dictionary.items():
    try:
        setattr(props, key, value)
    except TypeError:
        print("Skipping property " + key + ", it has the wrong type.")


# Because get_properties made a copy, we need to use set_properties.

grove.set_properties(props)
```



#the grove/the grove core/python api#