# Build

_The Grove offers adaptive polygon reduction, and a unique system of twigs that minimizes the impact on both memory and performance. During the simulation, the tree is a purely virtual data structure. After that it ’s time to build a polygonal 3D model of the branches, followed by the instancing of twig models. The Grove adds UV’s and many attributes that can be used in materials and geometry nodes. _


## Adaptive polygons

As a tree grows older, number of branches rises exponentially. And although the twig system saves amazing amounts of memory, the branches can also fill up your GPU rather quickly. The Grove’s adaptive meshing reduces the resolution along the branch as it gets thinner, and it thereby greatly reduces the total number of polygons.

The trunk and main branches require most geometric detail – you can define the resolution of the base with _Build > Mesh > Resolution_. A resolution of 24 means the base will be a circle described with 24 vertices. The base needs lots of polygons, but it makes no sense to use the same resolution for the thinnest branches way up in the tree crown. _Reduce_ will quickly lower the resolution as the branch nodes grow thinner, down to just 3 points at the thinnest tips. This creates significantly fewer polygons than a subdivision surfaces mesh would do.

Branches smoothly blend together by adding extra nodes. A lot of attention was put into this to make the connection fluent and natural.


## Textures and UVs

You can pick a bark texture from the _Build > Texture > Bark_ menu. The UV coordinates are created automatically and are randomized per branch to avoid repetition. The bark texture seamlessly repeats several times along the girth of the branch with _Repeat_. UVs update automatically to match the aspect ratio of the selected bark texture, and the UVs extend along the branch all the way to the tip.


## Attributes

There is a lot of data flowing through the tree during a simulation – like shade, thickness, photosynthesis and vigor. All of these are written to attributes, which you can use in things like materials, modifiers and geometry nodes. For instance use the thickness layer to tweak the bark material. Or transfer the photosynthesis layer over to the twig instances and use that in the twig materials to add fall colors. You can also displace points using the thickness paramater to tweak thickness after growing. Just a few out of many possibilities.


## Twigs

Twigs are the youngest branches, the new growth. Unlike older branches, twigs are like small plants – featuring leaves, flowers and fruit. The complexity and diversity of twigs can best be modeled by hand. It makes no sense to try to mimic them with software.

Instead of growing a full tree with leaves and fruit, The Grove uses twigs to finish off the tree. Distributing linked copies of a hand modeled twig saves huge numbers of polygons. This makes old trees and even groups of trees lightweight to handle and render. Add leaves, flowers and fruits with intricate detail yet little impact on memory. This makes the Grove trees ideal for GPU rendering.

Nothing is stopping you from using a single leaf as a twig object, it works great. For simpler trees and shrubs this might just do the trick. You decide on where to take over. Model a single leaf, last year’s twig or add a generation or two. Compensate the size of the twig with _Simulate > Scale_.


## Distribute twigs

When building the tree mesh, The Grove adds tiny little triangles. The location and rotation of these triangles is used to instance twig models with geometry nodes. This method cuts memory usage to just a couple of twig.

On some trees, twigs grown from end buds (apical buds) are different from twigs grown from side buds (lateral buds). End twigs are often more powerful, longer and they carry more leaves. On most species, flowers appear more prominent on one or the other. Enter the name of the _End Twig_ object and the _Side Twig_ object. You can also use the same twig for both.

The Grove distributes twig objects in the same way it adds new branches. _Density_ controls the number of side twigs – creating dense or airy trees.

Use _Simulate > Scale_ to match any size twig to any preset. An average twig contains one or two years of growth and is around 30cm long. A preset is designed to match this size. But twig models can be any size you want, from a single leaf up to several years of growth. The way to match a different size twig is to simply scale the branch model up or down. This keeps your twigs at the same real-life scale.

Although the twigs system provides huge memory savings and are quick to render, the huge number of polygons will still slow down your viewport. You can hide twigs in the viewport with the eye icon next to the twigs menu. Hiding twigs also helps you see the the branches while tweaking the tree.

To learn more about twigs, including how to create your own, read [Creating and using twigs](https://www.thegrove3d.com/learn/creating-and-using-twigs/).
