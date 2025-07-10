# Frequently Asked Questions

_This FAQ is a constant work in progress. If you find a bug or have a question that is not answered below, please do tell! You can find contact information at the bottom. The best feature of any software is stability and this is top priority for the Grove._


### Are twigs included?

No. The Grove has users all over the world and because of that you are encouraged to create a bundle of twigs that represents the trees of your region and climate.


### What are the requirements to run The Grove?

The Grove is an addon to Blender, which runs on Windows, OSX and Linux. If Blender runs, so will The Grove. Blender is free and provides The Grove with all the power of a full 3D software, including exporting models to other software.

Blender is in rapid development, and The Grove is on top of it. The Grove supports the latest official release of Blender, but it will most likely also work in the daily builds. Unofficial custom Blender versions may have made changes that stop The Grove from working properly. In this case it’s best to use the official release to grow your trees, and then link or append the trees in the custom Blender version.


### Can I grow multiple trees together at specific locations?

Yes, you can use the _Plant_ tool to grow groups of trees in all kinds of arrangements. Or you can also plant trees at specific locations and angles. To do this, simply add empty objects inside your grove collection (Add > Empty > Single Arrow). Make sure that you add the empty objects to the active grove collection. Then restart or regrow your grove to plant the trees and start growing. Add as many trees as you like and start growing groves of trees!


### Twigs are slowing down my viewport. Do you plan on making lower resolution versions?

The twigs system provides huge savings in memory and is quick to render. But the number of polygons can have quite an impact on viewport performance. There are two easy ways to get back viewport speed. You can reduce the detail of twigs with _Twig > More > View Detail_. Behind the scenes this adds a decimate modifier to the twig models, that only reduces the detail in the viewport. At render time, the full resolution twigs will be used. Another way is to simply hide twigs in the viewport using the eye icon next to the twigs menu. This too will only hide the twigs in the viewport, not in the render.


### Are the trees suitable for use in game engines?

The Grove aims for realism and does not have game-specific tools like LOD generation. So you need to know what you’re doing to get the trees to a game engine.

The twig system is very flexible. The twig 3D models made by the Grove are made for realism, they capture every detail in a twig. Although they take almost no memory with (GPU) rendering, they are not usable in game engines. However, you can make your own twigs with just the amount of detail you want. You can distribute your own low polygon image mapped branches.


### Can I control the number of polygons?

As a tree grows older, the branching structure can get quite complex. Although the twig system can save an amazing amount of memory, branches can also fill up your (GPU) memory quite quickly. You can control the reduction of the number of polygons based on the thickness of the branch, for high poly trunks and low poly branch ends.


### Do you plan on covering desert, sub-tropical, tropical and pine trees?

Absolutely, we plan on covering the entire world and are working hard on more twigs.


### Does the Grove grow palm trees, bamboo and regular plants?

No. These plants are very regularly repeating structures. The Grove focuses on trees that evolve through branching. The Grove’s twigs are basically small plants, and these are also modeled by hand for the best quality and realism possible.


### Can I render an animation of a growing tree?

Yes you can! Read the release notes for [The Grove release 8](https://www.thegrove3d.com/releases/the-grove-release-8/) to learn more. The growth animation that The Grove creates has a timelapse feeling and works best hat higher speeds – it is not buttery smooth.
