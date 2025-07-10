# Animate growth and wind


## Animate growth

Your browser does not support the video tag.
![](https://www.thegrove3d.com/wp-content/uploads/2019/10/TheGrove8GrowthSteps.jpg)

_For the first time, we can watch natural tree growth in mere minutes, bringing seemingly inanimate organisms to life!_


### Year by year

The way of growing year by year, is a fascinating animation just waiting to be captured. Record it to see trees like never before – turning years into seconds, it will forever change your view.

Recording is fast to play back, exports well to Alembic and it is flexible. It works with every other feature and is an integral part of The Grove. Swapping twigs or textures, scaling the simulation – even manual pruning during the simulation all work flawlessly.


### Record

Just flip on _Record_ and start growing. The Grove will save your growing tree to a sequence of year-by-year objects. Each of these objects is made visible for only a couple of frames. The Grove then smoothly blends the years with two shape keys – it blends from an initial spring state to a full grown summer shape.

![](data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==)


### Timing

The speed of growth is controlled with the _Interval_ parameter, it defines the number of frames between each year. A single yearly object is visible during this time and this is also the time it takes to smoothly blend between spring and summer shapes. You can change the interval at any time to instantly update the timing of the entire animation. Use _Start_ to shift the start of the animation.

Although the growth animation itself is buttery smooth and you can grow trees as slow as you like, keep in mind that when using twigs, new twigs pop into existence every year. For bigger twigs, higher speeds work best. And even with smaller twigs, the dropping of shaded and obsolete branches will still cause abrupt changes, that’s how real trees grow.


## Animate wind

_The way of growing year by year, is a fascinating animation just waiting to be captured. Record it to see trees like never before – turning years into seconds, it will forever change your view._

Your browser does not support the video tag.


### Shape keys

There’s nothing like the mesmerizing view of branches dancing in the wind. Wind brings a tree to life. The wind system uses shape keys, which are fast and compatible with most 3D software. Calculating wind shapes and playing the animation in your viewport are both surprisingly fast, especially when stored in an Alembic file.

To add wind to your tree, go to the _Build_ panel and click _Animate_. The tree is animated through a sequence of wind shapes. Wind shapes are built from two components, directional wind and turbulence. Both use the already rock-solid bend algorithm, but instead of bending to gravity the tree now bends with the wind – with varying intensity over time.

Secondary motion caused by turbulence is perhaps the most believable. Whereas the first step is more obvious in strong winds, this step is already present in a slight breeze. It simulates the lifting of leaves. By randomizing the leaf weight of each branch over time, the tree starts dancing in the wind.


### Loop

Key frames for each wind shape are 2 frames apart. The Grove adds additional key frames at the beginning and end to make the animation loop forever. An animation with 50 wind shapes will loop seamlessly every 100 frames. When exporting to Alembic, be sure to match this frame range.
