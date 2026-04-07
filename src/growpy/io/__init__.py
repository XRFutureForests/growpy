"""Import/Export functionality for GrowPy.

Organized into three sub-packages by output target, plus cross-format
orchestration at the top level:

    io.usd/            Universal USD export (tree mesh, assembly, twig,
                       texture, preview).
    io.unreal/         Unreal Engine output (import scripts, remote exec,
                       PVE, wind JSON).
    io.helios/         Helios++ output (OBJ/MTL, mesh simplification,
                       scene XML).
    io.forest_export   Cross-format per-grove orchestrator (USD + Unreal +
                       preview) for already-simulated forest groves.

This package deliberately does not re-export symbols at the top level.
Import from the sub-module you actually need, e.g.

    from growpy.io.usd.tree_export import build_tree_mesh
    from growpy.io.forest_export import export_individual_trees

This keeps `import growpy.io` cheap and avoids pulling bpy/USD eagerly for
callers that only need one sub-package.
"""
