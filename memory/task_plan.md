# GrowPy Improvement Task Plan

Generated: 2026-02-25

## External Scripts Assessment

### calculate_tree_heights.py
- VERDICT: Redundant. core/tree.py:extract_tree_measurements() covers this.
- Scans exported USDA files with regex — slower and fragile vs in-memory model access.
- Replace with CLI subcommand calling extract_tree_measurements().

### src/the-grove-output-complete.py
- VERDICT: Partial integration. Good source for missing API wrappers.
- Root workflow (grow_roots/build_roots) missing from public API -> core/grove.py
- Smoothing comparison -> utils/analysis.py
- Grove attribute extraction -> core/tree.py
- Text-dump diagnostic pattern -> utils/diagnostics.py

---

## Priority 1 — Bug Fixes

| ID | Status | Task | File | Notes |
|----|--------|------|------|-------|
| T1 | DONE | Cache growth model per species | core/tree.py | Opens pickle per row, not per species |
| T2 | DONE | Raise ValueError on bone overflow | core/skeleton.py | Was just print(), causes silent UE corruption |
| T3 | DONE | Consistent FileNotFoundError in get_growth_model_path() | config/paths.py | Returns non-existent path unlike get_preset_path() |
| T4 | DONE | twig_idx bounds check | core/twig.py | No validation before twig_locations[twig_idx] |
| T5 | DONE | Fix orphaned bone parent walk | core/skeleton.py | Orphaned bones silently set to root=0 |

## Priority 2 — Performance

| ID | Status | Task | File | Notes |
|----|--------|------|------|-------|
| T6 | DONE | Single-pass texture directory scan | io/texture_utils.py | 3+ separate globs of same dir |
| T7 | DONE | Vectorize alias lookup | config/paths.py | iterrows() -> str.contains() |
| T8 | DONE | Pre-compute easing table | config/preset_overrides.py | Recalculated every cycle |
| T9 | DONE | Extract shared growth cycle loop | core/forest.py | ~100 LOC duplicated |

## Priority 3 — Code Quality

| ID | Status | Task | File | Notes |
|----|--------|------|------|-------|
| T10 | DONE | Replace print() with logging | all modules | Cannot redirect/filter stdout |
| T11 | DONE | Constants for magic numbers | io/texture_utils.py, core/skeleton.py | Scattered literal values |
| T12 | DONE | Add __all__ to modules | all __init__.py | Implicit public API |
| T13 | DONE | bump_to_normal error handling | io/texture_utils.py | Silent None return on exception |
| T14 | TODO | Break up pve_grove_mapper.py | io/pve_grove_mapper.py | 1395 LOC monolith |
| T15 | TODO | Break up twig_export.py | io/twig_export.py | 3720 LOC monolith |

## Priority 4 — External Script Integration

| ID | Status | Task | Source | Target |
|----|--------|------|--------|--------|
| T16 | DONE | extract_grove_attributes() | the-grove-output-complete.py:247-263 | core/tree.py |
| T17 | DONE | grow_roots()/build_roots() wrappers | the-grove-output-complete.py:206-225 | core/grove.py |
| T18 | DONE | compare_smoothing_effect() | the-grove-output-complete.py:106-178 | utils/analysis.py |
| T19 | DONE | dump_grove_data() diagnostic | the-grove-output-complete.py:382-754 | utils/diagnostics.py |
| T20 | DONE | Deprecate calculate_tree_heights.py | calculate_tree_heights.py | core/tree.py docs |
