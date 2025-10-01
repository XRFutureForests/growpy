# Shade, drop and prune

_Witness branches compete for light – drop them when too little is available. Evolve your trees into airy branching structures._

If a tree held on to every branch it grew, it would become a dense green ball that would soon collapse under its own weight. To escape this horrible fate, it drops all but the most successful branches. Dropping branches keeps the tree airy and allows light into the crown.

The Grove has 3 ways of removing unwanted branches:
  1. The tree itself drops shaded and low power branches all the time.
  2. Automatic pruning of the lower base will save you a lot of time in creating city trees.
  3. Manual pruning allows you to cut individual branches by hand, or to trim many branches at once by drawing cutting lines.


## Shade

_Trees grow up to the sky, competing with neighbors that take away light. But the biggest competition is the very tree itself, where new leaves above shade the old underneath._

![](https://www.thegrove3d.com/wp-content/uploads/2016/05/Shade.jpg)


### Ray tracing

Light is an absolutely vital ingredient to tree growth. More than any other type of plant, trees have evolved to get as much light as possible. Unique to The Grove is that it uses ray tracing to calculate the actual light at every growing tip in the tree. This allows The Grove to grow natural trees that are sensitive to changes in light and shade. Let’s take a look at how this is done.


### Sky

The branch tips are the eyes of the tree, and what they are looking for is blue sky light. Unlike directional sunlight, blue light comes equally from all directions and it makes trees grow into a balanced shape instead of leaning toward the sun.

So we sample evenly across the sky. The Grove uses a phyllotaxic distribution of samples – the same natural distribution seen in sunflower seeds and pinecones. It’s only fitting to use this optimal distribution to sample the light environment.


### Foliage

Next we need geometry to block this light, and that will be the tree’s foliage. A couple of polygons at the tip of every branch are all we need to represent all the leaves in the tree.

![](https://www.thegrove3d.com/wp-content/uploads/2020/01/TweakShadeParameters.jpg)

The interactive _Shade Preview_ offers you a view behind the scenes, you can find the circle icon in the Shade panel. It shows you where The Grove distributes shadow casting areas and just how big they are. You will see that it places two triangles at each branch tip. The size of each area is controlled by _Leaf Area_ , and this area is reduced on less vigorous branches with _Reduce_. The default values work well in most situations and you should rarely have to tweak these.


### Obstacles

You can set a _React > Shade_ object to include that object’s polygons in the shade calculation. An object like a building can block light from one side, causing the tree to loose many of its branches on that side. Another obvious effect is that of _Turn > To Light_. You can already see this effect in a single tree or in multiple trees growing together, but it is becomes very visible in trees avoiding large obstacles where trees lean toward the bright side.


## Drop

_Branches evolve and grow to the light. But when it gets crowded and they end up in shade, branches will wither and drop to the ground._

![](https://www.thegrove3d.com/wp-content/uploads/2018/05/TheGroveDeadBranches.jpg)


### Drop shaded

Alright, we’ve calculated the shade of every branch tip. Now it’s time to drop the low performers. By far most branches are dropped because of low light. A higher _Drop > Shaded_ will drop more branches, as simple as that. _Drop Shaded_ only drops young branches without side branches. Older branches can be dropped with _Drop > Obsolete_.


### Drop obsolete

This doesn’t only happen when you pick up a chainsaw and prune the tree too heavily. It happens all the time in nature, when the crown grows bigger and shades the lower branches. These lower branches will slow down and even lose many of their smaller twigs due to a lack of light, to the point where the branch is thicker than it needs to be – too thick for its dwindling leaves to keep it healthy.

When there’s just too much excess wood, the few remaining leaves can’t keep the flow of water going when conditions become dry. This is when the branch will dry out and die.


## Prune

_Nurture your tree like mother nature, or dive in with the pruning tool! Remove the branches that block the view, create space and air, and neat contours._

![manualprune](https://www.thegrove3d.com/wp-content/uploads/2016/05/ManualPrune.gif)


### Manual prune

To prune your tree, simply click _Prune_ and draw a line in the 3D view. Anything crossing the line will be pruned back.

Prune realistically cuts off branches and leaves thick and dead branch ends. A handy tool for cutting off larger branches.

Interactive pruning is fun to play with, extremely addictive, and gives rise to many more tree shapes, and even extremes like pollarded plane trees and pollarded willows.


### Regenerate

Trees respond like crazy to pruning. The excess wood volume contains so much energy that it will create regenerative branches from old wood.

Paired with the _Prune_ tool, trees will soon recover from the tyranny you impose on them. Gaping holes will soon fill up, all thanks to the shade calculation!

Regenerative branches develop after damage caused by lightning, storms and falling neighbor trees. Although regenerative branches are natural and quite common, they are an unwanted sight on the trunks of city trees. And it is the extreme pruning imposed on city dwelling trees that causes many regenerative branches along the trunk. Use _Auto Prune > Low_ for regular maintenance of your trunks.


### Auto prune

A tree naturally looses many of its lower branches that are not receiving enough sunlight. But there are other factors at play. Herbivores like deer, elephants and giraffes can’t get enough of the tasty greens and they will rip off anything they can reach, which plays a key role in the iconic shapes of African savannah trees.

We humans usually don’t eat the branches, but we do also remove the lower branches on the trees in our cities, parks and along the roads. We need trees in our cities, but they do take a lot of space. By removing lower branches we regain that space and get clear views and room for traffic and people to pass – plus we remove the risk of unsafe branches.

_Auto Prune > Low_ is a handy tool that automatically performs this work every year. Branches along the base of the tree growing lower than this will be pruned each year. This gradually kicks in only when the tree grows higher than the set height. A small tree will not yet be pruned. Only when the tree grows to twice this height, its base will be cleared to the full _Low_ height. _Keep Thick_ will keep thicker branches.

__

__
