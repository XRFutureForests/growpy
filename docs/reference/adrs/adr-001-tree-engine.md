# ADR-001: Tree Engine Selection — The Grove 2.3

**Date:** 2026-05-11 | **Status:** Accepted | **Category:** tree_engine | **Decision Makers:** XR Future Forests Lab, Uni Freiburg

<!-- SCOPE: Architecture Decision Record for the tree generation engine selection ONLY. -->
<!-- DO NOT add here: Implementation code → task descriptions, Requirements → requirements.md -->
<!-- DOC_KIND: record -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need the decision context for why The Grove 2.3 was chosen over other tree engines. -->
<!-- SKIP_WHEN: Skip when you only need the current system overview without decision history. -->
<!-- PRIMARY_SOURCES: docs/project/architecture.md, docs/project/tech_stack.md, docs/reference/README.md -->

## Quick Navigation

- [Reference Hub](../README.md)
- [Architecture](../../project/architecture.md)
- [Tech Stack](../../project/tech_stack.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Records the decision to use The Grove 2.3 as tree simulation engine and the alternatives considered. |
| Read When | You need rationale or history behind the tree engine choice. |
| Skip When | You only need the current state without decision history. |
| Canonical | Yes |
| Next Docs | [ADR-002: USD Format](adr-002-usd-pipeline-format.md), [Architecture](../../project/architecture.md) |
| Primary Sources | `docs/project/architecture.md`, `docs/project/tech_stack.md` |

---

## Context

GrowPy must simulate physiologically plausible multi-species forest growth with calibrated height/DBH trajectories, then export geometry consumable by Unreal Engine 5 Nanite and Helios++ LiDAR. The engine must expose a Python API for pipeline automation, support skeletal mesh export for wind animation, and produce realistic crown morphology for 10 southern German tree species.

---

## Decision

We use The Grove 2.3 (thegrove3d.com) as the sole tree simulation and geometry engine, accessed via its Python module `the_grove_23_core`, bundled inside the conda environment via `bpy`.

---

## Rationale

1. **Python API with cycle-level control** — `the_grove_23_core` exposes grove, tree, and skeleton objects directly; no GUI required. This enables the automated 4-step pipeline (prepare → convert → calibrate → generate) without human interaction.
2. **Skeletal mesh output** — Grove natively produces bone hierarchies that map to Unreal Engine skeletal meshes, enabling runtime wind animation via the PVE wind system. No other evaluated engine produces export-ready skeletons.
3. **USD + Nanite compatibility** — Grove outputs geometry that, combined with `usd-core`, produces Nanite Assembly USD files. SpeedTree and Laubwerk require proprietary exporters that do not integrate with the Python pipeline.

---

## Consequences

**Positive:**
- Single engine covers simulation, LOD geometry, twig foliage, and skeleton — no stitching of separate tools
- Cycle-based growth model maps directly to yield-table calibration targets
- Established community presets for European tree species reduce species parametrisation time

**Negative:**
- Commercial license required — The Grove 2.3 cannot be bundled in the repository; developers must supply their own copy
- `bpy` import forces Step 4 to run as a subprocess (bpy cannot be imported in the orchestrator process)
- Engine updates may break the `the_grove_23_core` API; pinned to Grove 2.3 only

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| SpeedTree (IDV, Unity partnership) | Industry-standard, high-quality bark/leaf rendering, UE5 plugin | No Python API for batch automation; GUI-only workflow; per-tree export, not pipeline-native | Cannot automate multi-species batch generation without GUI |
| Custom L-system (e.g., py-lindenmayer) | Open-source, full control, no license cost | No skeletal mesh output; no yield-table calibration; would require full geometry pipeline from scratch | Months of geometry and LOD work; no proven path to Nanite Assemblies |

---

## Related Decisions

- ADR-002: USD Pipeline Format (downstream of tree engine choice)
- ADR-003: conda Environment (required by bpy bundling constraint)

---

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- Grove 2.3 API breaks (version upgrade)
- Alternative engine evaluated
- License model changes

**Verification:**
- [ ] Decision still reflects accepted choice
- [ ] Alternatives and consequences still match current understanding
- [ ] Related ADR links resolve
