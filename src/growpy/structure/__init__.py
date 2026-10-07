"""Tree structure as data: standardise real QSMs, then compare them with generated trees.

``schema``       the canonical cylinder and tree tables, species normalisation
``axes``         the single axis rule (which child continues, which starts a lateral axis)
``readers``      one parser per on-disk format
``standardize``  frame, axes, uniform measurements, quality numbers
``sources``      one adapter per published dataset (metadata onto the shared columns)
``store``        write and stream a standardised dataset

``growpy-qsm-standardize`` is the console entry point. The knowledge hub note
``04-LOGIC-TIER/structure-extraction-and-encoding`` holds the reasoning (why one cylinder
table, why MTG is a derived export); this package is the implementation.
"""
