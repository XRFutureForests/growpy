# Blender Export Migration Strategy - Revised

## Challenge

The file `blender_export.py` is 4116 lines with complex interdependencies. Manual extraction is time-consuming and error-prone.

## Pragmatic Approach

Instead of extracting everything at once, use a **phased migration** strategy:

### Phase 1: Create Module Structure (DONE)
- ✅ Created `export/`, `nanite/`, `twig/` directories
- ✅ Extracted simple modules (quality, nanite, blender_utils)

### Phase 2: Create Import Facade (DO THIS)
Create new modules that import from original `blender_export.py`:

```python
# export/usd.py
from ..blender_export import (
    export_tree_as_usd,
    export_grove_tree_as_usda_native,
    create_nanite_assembly_usd,
)

__all__ = ["export_tree_as_usd", "export_grove_tree_as_usda_native", "create_nanite_assembly_usd"]
```

This allows:
1. New import structure works immediately
2. Code using new imports works
3. Gradual migration without breaking anything

### Phase 3: Migrate Function by Function
Slowly move functions from `blender_export.py` to new modules, testing after each move.

### Phase 4: Final Cleanup
Once all functions migrated, deprecate `blender_export.py`.

## Immediate Action

Create facade modules now that re-export from `blender_export.py`. This gives us the new structure without risk.

## Benefits

- ✅ Zero risk - nothing breaks
- ✅ New code can use new structure
- ✅ Gradual migration
- ✅ Can test incrementally
- ✅ Can pause/resume anytime
