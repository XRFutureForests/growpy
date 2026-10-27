"""Tree structure as data: standardise real QSMs, then compare them with generated trees.

``schema``       the canonical cylinder and tree tables, species normalisation
``axes``         the single axis rule (which child continues, which starts a lateral axis)
``readers``      one parser per on-disk format
``standardize``  frame, axes, uniform measurements, quality numbers
``sources``      one adapter per published dataset (metadata onto the shared columns)
``store``        write and stream a standardised dataset
``reference``    the committed real-tree percentile store (``data/input/structure_reference``)
``score``        catalog against real trees per species (gap table, share within one spread)
``gate``         the realism gate and growth-over-time consistency
``adequacy``     which descriptors may gate (species, height, source effects; sensitivity)
``pointcloud``   L2 metrics on point clouds without fitting (profile, envelope, box dimension, gaps)
``synthetic_scan``  HELIOS++ virtual TLS of a generated tree, alone or in a stand

``growpy-qsm-standardize`` is the console entry point. The knowledge hub note
``04-LOGIC-TIER/structure-extraction-and-encoding`` holds the reasoning (why one cylinder
table, why MTG is a derived export); this package is the implementation.
"""
