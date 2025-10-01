# What is a twig

A twig is a 3D model that represents the last generations of tree growth – a small branch. You can use any polygonal object as a twig. Twigs are distributed at branch ends to add incredible realism to your trees.

![](https://www.thegrove3d.com/wp-content/uploads/2016/03/MannaGumTwigAlpha.png)

The twig system is very flexible. The twig models sold on this site are made for realism, they capture every detail in a twig. Although they take almost no memory with GPU rendering, the resulting 3D trees are not usable in game engines. But you can make your own twigs with just the amount of detail you want. You can distribute your own low polygon image mapped branches.


## Using The Grove’s twigs

✕

Release 6 introduced an automated twig picker menu that lists all twigs in your library. Simply click on a twig and it is appended to your scene and used on your tree. All the hassle mentioned below is a thing of the past. It’s time to update this documentation.

To use a twig, it has to be in your scene. Let’s say you’re working on a great scene which is in need of a 3D tree. First, add the twig you want to use to your scene. Either by appending the twig (File > Append), which inserts the model into your scene. Or by dynamically linking to the twig file (File > Link).

Either Append or Link will present you with a file browser. Browse to where the twig model is and click on the .blend file. This lets you dive into the file. Browse to objects and select the twig objects and hit Enter. You may want to move twigs to an invisible layer.

Start the Grove with Add > Mesh > The Grove and pick the object you just imported in the _Apical Twig_ field. If the twig has a separate lateral twig model, pick it with the _Lateral Twig_ text field. If not, you can enter the same twig in both text fields. You can find the twig pickers all the way down in the Build panel.

✕

Watch out! First append twigs, then start The Grove. If done the other way around, your twigs will disappear.
This has to do with how Blender Addons work, specifically how Operators work. Operators like the Grove create a lot of 3D data and materials. Each time your tree updates, this data is added to your 3D scene. To keep the scene clean, Blender performs an undo just before the Addon is called to do its work. This leaves your 3D scene in the state it was in just before you called the Grove. Quite brilliant, but very frustrating if you’re not aware. The solution is to first append or link your twig model, and then add a new Grove tree.


## Create your own twigs

There are just two things to keep in mind when using an object as a twig. First, its origin (pivot point) should be at the start of the branch. To do this, first place the 3D cursor at the start of the branch. Then press the space bar and search for _Set Origin_ and click it. Then select _Origin to 3D Cursor_.

Second, the Grove assumes the branch is pointing in the direction of the X-axis. It means that when you are in top view, the base of the branch should be on the left, and it should be growing out to the right. When you’ve got the twig pointing in the right direction, you have to apply its rotation and scale by pressing Ctrl+A and picking _Rotation & Scale_.

✕

For your new twig to show up in the twig picker menu, you have to put it in the twigs folder that you configured in the user preferences. There is a simple naming convention to follow. Simply name your apical twig any name you want but include ApicalTwig at the end. Same for lateral twigs, include LateralTwig in the name. If you have a single twig to be used for both, you can just include Twig in the name.


## Simple twig starter pack

To get you started, here is a small selection of _extremely_ simple twig models that was used early on in development. They have no textures and their geometry is very crude. Play around with these twigs to see how twigs of different sizes work and how even simple twigs can have a high impact. For these simple twigs, you will want to set the _Viewport Detail_ to 1.0, or you will get funky geometry.

[Download the pack of simple twigs.](https://www.thegrove3d.com/wp-content/uploads/2015/10/SimpleTwigs.zip)

![SimpleTwigs](https://www.thegrove3d.com/wp-content/uploads/2015/10/SimpleTwigs.jpg)

Learn more on twigs and how to distribute them, read [Build](https://www.thegrove3d.com/learn/build/).


## Browse Twigs

[ ![Japanese maple ‘Atropurpereum’](https://www.thegrove3d.com/wp-content/uploads/2024/02/AcerPalmatumA-500x500.png) Japanese maple ‘Atropurpereum’ ](https://www.thegrove3d.com/twigs/japanese-maple-atropurpureum/)

_Acer palmatum ‘Atropurpureum’_ – a cultivated variety of the Japanese maple tree, with deeply colored purple-red leaves. This slow grower is a wildly popular garden tree.

[ ![Spindle](https://www.thegrove3d.com/wp-content/uploads/2024/02/EuonymusEuropaeus-500x500.png) Spindle ](https://www.thegrove3d.com/twigs/spindle-2/)

_Euonymus europaeus_ – Spindles are small trees, but they pack a punch with fiery fall colors and the pink-colored fruit looks absolutely out of this world.

[ ![Woodland hawthorn](https://www.thegrove3d.com/wp-content/uploads/2024/02/CrataegusLaevigata-500x500.png) Woodland hawthorn ](https://www.thegrove3d.com/twigs/woodland-hawthorn/)

_Crataegus laevigata_ – a small tree from the rose family, hawthorn is closely related to apple trees. With abundant white flowers that later develop into clusters of red fruit.

[ ![Goat willow](https://www.thegrove3d.com/wp-content/uploads/2024/02/SalixCaprea-500x500.png) Goat willow ](https://www.thegrove3d.com/twigs/goat-willow/)

_Salix caprea_ – goat willow is a rather inconspicuous tree, with no flashy flowers, fruit or autumn colors. It’s a modest tree that dots the landscape with touches of green.

__

[More Twigs](https://www.thegrove3d.com/category/twigs)
