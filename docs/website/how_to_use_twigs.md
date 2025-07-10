# How to use twigs

A twig is a 3D model that represents the latest flush of growth – a small branch with leaves. Twigs are instanced at branch ends to add incredible realism to your trees. You can use any polygonal object as a twig, and this makes the twig system very flexible. The twig models sold on this site capture a lot of detail, but you can just as well use you own low polygon geometry or even single leaves.

![](https://www.thegrove3d.com/wp-content/uploads/2021/09/Collage2.jpg)


## Install a twig

After installing The Grove, it’s time to create a folder to keep all twigs together. Let’s call this folder _TwigsLibrary_ – you can place it anywhere you like, and then point to this folder in The Grove’s user preferences. When you purchase a twig, simply unzip it to the library folder.

As an example, let’s presume you purchase an ash twig and an elm twig. After a correct installation, your twigs folder will have two sub folders called _AshTwig_ and _FieldElmTwig_. Each of these will contain the .blend files for the twigs and each of them will have a separate textures folder. So each twig has it’s own folder with its own textures, keep it that way. The Grove will automatically find the two twigs and you can add them to your trees from the twigs menu.


## Apply a twig

The drop-down menu in the _Twig_ panel lists all the twigs it can find in your library folder. Simply pick a twig from the menu to add it to trees you grow. You can also use any 3D object in your scene or even an entire collection of objects.

Twigs and presets are two completely separate things – you can use any twig on any preset. This is an important concept, and it takes very little effort to adjust the preset to a different twig. Of course it would look silly to use a walnut twig on a pine preset, but with some common sense you can use a single twig on more than one preset.

The first thing to do when picking a twig for your tree is to adjust the preset to match the size of the twig. For instance the Paper Birch twig comes in several variations, one covering a bigger branch than the other. So after picking a twig, adjust _Simulate > Scale_ to make it look right. You may also have to tweak _Twig > Density_.


## Create your own twigs

You can use any 3D object as a twig by setting the twig picker menu to _Scene Objects_. Then pick objects from the scene for the end and side twigs.

There are just two things to keep in mind when using an object as a twig. First, its origin (pivot point) should be at the start of the branch. To do this, first place the 3D cursor at the start of the branch. Then press the space bar and search for _Set Origin_ and click it. Then select _Origin to 3D Cursor_.

Second, the Grove assumes the branch is pointing in the direction of the X-axis. This means that when you are in top view, the base of the branch should be on the left, and it should be growing out to the right. When you’ve got the twig pointing in the right direction, you have to apply its rotation and scale by pressing Ctrl+A and picking _Rotation & Scale_.


## Naming

If you’ve created a twig yourself, you may want to list it in the twigs menu so that you can use it in other scenes. You can do this by saving a clean .blend file with just the twigs in the folder that you configured in the user preferences. There is a simple naming convention to follow. You can name your endtwig any way you want, but make sure to end the name with _EndTwig_ in the name. Same for side twigs, end the name with _SideTwig_. And optionally an _UpwardTwig_ and _DeadTwig_. If you have a single twig to be used for both the side and end twig, you can just end the name with _Twig_.

You can also create several twig variations and group them in collections. In that case, end the collection names with _EndTwigs_ , _SideTwigs_ , _UpwardTwigs_ and _DeadTwigs_. Make sure these collections are all first level collections linked directly to the scene collection.


## Simple twig starter pack

To get you started, here is a small selection of _extremely_ simple twig models that was used early on in development. They have no textures and their geometry is very crude. Play around with these twigs to see how twigs of different sizes work and how even simple twigs can have a high impact. For these simple twigs, you will want to set the _Viewport Detail_ to 1.0, or you will get funky geometry.

[Download the pack of simple twigs.](https://www.thegrove3d.com/wp-content/uploads/2015/10/SimpleTwigs.zip)

![SimpleTwigs](https://www.thegrove3d.com/wp-content/uploads/2015/10/SimpleTwigs.jpg)

To learn more about twigs and how to instance them on your trees, read [Build](https://www.thegrove3d.com/learn/build/).
