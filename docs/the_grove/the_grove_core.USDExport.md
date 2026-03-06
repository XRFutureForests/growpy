# USD Export

_studio edition feature_

The Grove's USD exporter is accessible from the Python API and is intended to be used programmatically in studio pipelines. The function `the_grove_core.io.model_to_usda_string(Model) -> String` converts a single tree model to a USD model. You can write the returned string directly to a `.usda` file. This USD file contains the mesh, UV maps, attributes and twig instancers.

Note that while `Grove.build_models` builds models of all trees in the current grove and returns these in a list, this function only takes one tree model at a time.

```python
import the_grove_core

grove = the_grove_core.Grove()
grove.add_new_tree(
    the_grove_core.Vector(1.0, 0.0, 0.0),
    the_grove_core.Vector(0.0, 0.0001, 0.1),
    0)

grove.simulate(30)
models = grove.build_models({"resolution": 32})

for i in range(len(models)):
    usda_string = the_grove_core.io.model_to_usda_string(models[i])
    with open(f'tree{i}.usda', 'w') as f:
        f.write(usda_string)
```

Each tree's `Xform` contains a transformation to place the tree where it belongs.

You can combine multiple trees into a grove layer:

```usda
#usda 1.0
()

def Xform "Grove"
{
    def "Tree0" (
        append references = @./tree0.usda@
    )
    {}
    def "Tree1" (
        append references = @./tree1.usda@
    )
    {}
}
```

## Twig instances

The USDA exporter sets up a pointInstancer to duplicate twigs as lightweight instances. The exporter creates a list of positions and orientation quaternions to place the twigs precisely where they need to be. The instancer was checked to function in Blender, Houdini and macOS preview.

The exporter writes a text-based `.usda` file, as opposed to the binary `.usdc` format. This means you can easily edit the file in a text editor or programmatically.

The USDA exporter does not export the twig geometry. You are expected to create these manually with materials set up for your specific rendering workflow. The instancer will look for prototypes in `./twig.usda` with this structure:

```text
root/
    Twigs/
        LongTwigs/
            LongTwigA
            AnotherLongTwigB
        ShortTwigs/
            ShortTwigA
        UpwardTwigs/
            UpwardTwig
        DeadTwigs/
```

You can use an intermediate `.usda` file to redirect to actual twig files:

```usda
#usda 1.0

def "TwigSource" (
    references = @./twigs/species_twig.usd@</root>
)
{
}

def Xform "Twigs"
{
    def Xform "LongTwigs" (
        references = </TwigSource/LongTwigs>
    )
    {}
    def "ShortTwigs" (
        references = </TwigSource/ShortTwigs>
    )
    {}
    def "UpwardTwigs" (
        references = </TwigSource/UpwardTwigs>
    )
    {}
    def "DeadTwigs" (
        references = </TwigSource/DeadTwigs>
    )
    {}
}
```

## Alignment with growpy's Unreal Pipeline

Growpy's assembly export (`assembly_export.py`) creates a more sophisticated PointInstancer setup targeted at Unreal Engine's Nanite Assembly schema:

- Uses `TwigPrototypes` Scope with per-twig-type SkelRoot/Xform children
- References actual twig USDA files directly (skeletal or static variants)
- Maps the same 4 twig types (long/short/upward/dead) to prototype indices
- Adds `NaniteAssemblySkelBindingAPI` with `bindJoints` for skeletal animation
- Supports both skeletal (wind-animated) and static (Nanite-optimized) assemblies

The Grove's native USD exporter and growpy's assembly exporter are compatible: both use PointInstancer with positions and orientation quaternions for the same 4 twig types.
