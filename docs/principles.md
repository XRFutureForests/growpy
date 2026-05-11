# Development Principles

<!-- SCOPE: Project development principles and tradeoffs ONLY. Contains reusable principles, decision order, anti-patterns, and verification guidance. -->
<!-- DOC_KIND: explanation -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when making implementation or documentation decisions and you need the governing principles. -->
<!-- SKIP_WHEN: Skip when you only need routing or exact factual lookup. -->
<!-- PRIMARY_SOURCES: docs/principles.md, docs/documentation_standards.md -->

## Quick Navigation

| Need | Read |
|------|------|
| Documentation rules | [documentation_standards.md](documentation_standards.md) |
| Documentation map | [README.md](README.md) |
| Root entry point | [../AGENTS.md](../AGENTS.md) |

## Agent Entry

- Purpose: Explain the project's governing principles and decision hierarchy.
- Read when: You need to choose between alternatives or justify a tradeoff.
- Skip when: You only need a direct factual lookup.
- Canonical: Yes.
- Read next: The relevant project or reference doc for the concrete domain.
- Primary sources: `docs/principles.md`, `docs/documentation_standards.md`.

## Core Principles

| # | Principle | Application |
|---|-----------|-------------|
| 1 | Standards First | Industry and scientific standards override convenience |
| 2 | YAGNI | Build only what the pipeline step requires now |
| 3 | KISS | Prefer the simplest correct solution for each stage |
| 4 | DRY | One canonical source per species parameter, yield table, or config value |
| 5 | Consumer-First Design | Design pipeline outputs from the consumer's perspective (UE5 importer, Helios scene) |
| 6 | No Legacy Code | Remove dead compatibility layers; do not accumulate unused Grove version shims |
| 7 | Documentation-as-Code | Update docs when pipeline stages, CLI scripts, or output formats change |
| 8 | Reproducibility | Each pipeline run must be deterministically reproducible given the same inputs and config |

## Decision Framework

1. Correctness of simulation outputs (allometry, light competition, USD assembly)
2. Standards compliance (USD spec, UE5 Nanite constraints, Helios scene schema)
3. Simplicity of the pipeline stage
4. Necessity (YAGNI — no speculative pipeline branches)
5. Maintainability (clear stage boundaries, typed config)
6. Performance (batch/parallel only where bottleneck is confirmed)

## Anti-Patterns

- Hardcoding species parameters outside the TOML config or yield tables
- Accumulating Grove version shims instead of updating the interface
- Generating pipeline outputs without validating against downstream consumer constraints
- Over-engineering stage orchestration before a single-threaded path is proven correct
- Leaking USD stage details into the core forest/tree domain model
- Magic constants scattered across pipeline stages

## Verification Checklist

- [ ] Pipeline outputs validated against downstream consumer constraints (UE5, Helios)
- [ ] Species parameters sourced from config or yield tables, not hardcoded
- [ ] Unnecessary complexity avoided
- [ ] Documentation updated with any pipeline stage or CLI changes
- [ ] Reproducibility verified: same inputs → same outputs

## Maintenance

**Update Triggers:**
- When pipeline architecture changes (new stages, removed stages)
- When downstream consumers change their input requirements
- When new recurring anti-patterns appear in reviews

**Verification:**
- [ ] Principles still reflect the pipeline architecture
- [ ] Decision order still matches project priorities
- [ ] Anti-pattern list is current

**Last Updated:** 2026-05-11
