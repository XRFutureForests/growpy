# ADR-002: 3D Asset Exchange Format — Pixar USD

**Date:** 2026-05-11 | **Status:** Accepted | **Category:** pipeline_format | **Decision Makers:** XR Future Forests Lab, Uni Freiburg

<!-- SCOPE: Architecture Decision Record for the 3D asset exchange format selection ONLY. -->
<!-- DO NOT add here: USD export internals → docs/reference/usd-builder.md, coordinate systems → docs/reference/coordinate-systems.md -->
<!-- DOC_KIND: record -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need the rationale for using USD instead of FBX, glTF, or OBJ as the primary pipeline format. -->
<!-- SKIP_WHEN: Skip when you only need USD builder internals — see docs/reference/usd-builder.md. -->
<!-- PRIMARY_SOURCES: docs/project/architecture.md, docs/reference/usd-builder.md, docs/project/tech_stack.md -->

## Quick Navigation

- [Reference Hub](../README.md)
- [USD Builder Reference](../usd-builder.md)
- [Architecture](../../project/architecture.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Records the decision to use Pixar USD as the primary 3D asset exchange format for the GrowPy pipeline. |
| Read When | You need rationale for USD over FBX/glTF/OBJ in the pipeline. |
| Skip When | You need USD export implementation details — see docs/reference/usd-builder.md instead. |
| Canonical | Yes |
| Next Docs | [USD Builder](../usd-builder.md), [ADR-001: Tree Engine](adr-001-tree-engine.md) |
| Primary Sources | `docs/project/architecture.md`, `docs/reference/usd-builder.md` |

---

## Context

The pipeline must transfer complex tree assets (multi-mesh, multi-material, skeletal hierarchy, LOD levels, instancing) from the Python generation step into Unreal Engine 5.7+ with Nanite support and wind animation. The format must support instanced assemblies (one USD referencing many sub-assets) and be writable from Python without a DCC application.

---

## Decision

We use Pixar USD (via `usd-core>=23.11`) as the primary 3D asset exchange format. Twig assets are exported as `.usda` files; forest assemblies are exported as Nanite Assembly `.usda` files that reference twig prims via USD instancing.

---

## Rationale

1. **Native UE5 Nanite Assembly support** — Unreal Engine 5's USD importer consumes USD Nanite Assemblies (one root prim with point instancer) directly; no intermediate conversion step required.
2. **Python-native `usd-core` library** — Pixar's `usd-core` pip package allows full USD scene graph construction from Python without Blender or Houdini; the pipeline writes USD in Step 2 (twigs) and Step 4 (assemblies) entirely from code.
3. **Instancing and LOD** — USD's point instancer and variant sets handle multi-thousand-tree forests with shared prim references, keeping file sizes manageable. FBX requires one mesh per instance.

---

## Consequences

**Positive:**
- USD Nanite Assembly import into UE5 is drag-and-drop with full instancing
- `usd-core` is pip-installable; no DCC license required for export
- USD layer system enables separate twig, bark texture, and skeleton layers — clean separation of concerns

**Negative:**
- `usd-core` adds ~500 MB to the conda environment (bundled with bpy, so net cost is minimal)
- USD coordinate system (+Y up) differs from Grove (+Z up) and Unreal (+Z up) — requires per-export axis remapping (see docs/reference/coordinate-systems.md)
- USD ASCII (`.usda`) files are human-readable but large; binary `.usdz` packaging not used due to UE5 import limitations

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| FBX | Universal DCC support, UE5 native import | No Python writer without FBX SDK (C++); no instancing primitive; skeletal mesh export requires Blender roundtrip | Cannot write FBX from pure Python in pipeline context |
| glTF 2.0 | Open standard, `pygltflib` available | UE5 glTF importer does not support Nanite Assemblies or point instancers; limited skeletal animation support at time of decision | No path to UE5 Nanite Assembly workflow |

---

## Related Decisions

- ADR-001: Tree Engine (The Grove 2.3 outputs geometry; USD wraps it)
- See [docs/reference/usd-builder.md](../usd-builder.md) for implementation details
- See [docs/reference/coordinate-systems.md](../coordinate-systems.md) for axis conventions

---

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- UE5 USD importer adds new capabilities
- `usd-core` major version upgrade with API changes
- Alternative format evaluated

**Verification:**
- [ ] Decision still reflects accepted choice
- [ ] Alternatives and consequences still match current understanding
- [ ] Related links resolve
