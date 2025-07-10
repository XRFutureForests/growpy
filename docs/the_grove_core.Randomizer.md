# [the_grove_core](./the_grove_core.html).Randomizer

Generate pseudo-random floating point numbers from 0.0 to 1.0. Each call to Randomizer.factor() returns a new random number. A newly created Randomizer is initialized with a random seed based on system time. If you want to get the same sequence of numbers again and again, use set_seed.




### factor()  float

Get a new random number ranging from 0.0 to 1.0.




### set_seed(seed)

Manually initialize a Randomizer with an integer seed value. This will give the same sequence of pseudo-random values each time. Using the same parameters this will grow the same tree over and over - useful for speed tests. Normally the seed is initialized to a random start value so that each tree grows different.



#the grove/the grove core/python api#