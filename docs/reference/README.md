# Reference Documentation

**Version:** 1.0.0
**Last Updated:** 2026-05-11

<!-- SCOPE: Reference documentation hub (ADRs, Guides, Manuals) with links to subdirectories -->
<!-- DO NOT add here: ADR/Guide/Manual content → specific files, Project details → project/README.md -->
<!-- DOC_KIND: index -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need to route to ADRs, guides, manuals, or research notes. -->
<!-- SKIP_WHEN: Skip when you already know the exact reference document to open. -->
<!-- PRIMARY_SOURCES: docs/reference/, docs/project/architecture.md, docs/project/tech_stack.md -->

## Quick Navigation

- [Docs Hub](../README.md)
- [ADRs](adrs/)
- [Guides](guides/)
- [Manuals](manuals/)
- [Research](research/)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Routes agents and humans to the canonical reference artifacts for decisions and reusable knowledge. |
| Read When | You need the right ADR, guide, manual, or research note. |
| Skip When | You already know the exact file you need. |
| Canonical | Yes |
| Next Docs | [ADRs](adrs/), [Guides](guides/), [Manuals](manuals/), [Research](research/) |
| Primary Sources | `docs/reference/`, `docs/project/architecture.md`, `docs/project/tech_stack.md` |

---

## Overview

This directory contains reusable knowledge base and architecture decisions:

- **Architecture Decision Records (ADRs)** — Key technical decisions with context, rationale, and alternatives
- **Project Guides** — Reusable patterns and best practices specific to GrowPy
- **Package Manuals** — API reference for external libraries (none yet — see existing `docs/reference/` files)
- **Research** — Investigation documents answering specific questions

---

## Architecture Decision Records (ADRs)

| ADR | Decision | Status | Date |
|-----|----------|--------|------|
| [ADR-001: Tree Engine](adrs/adr-001-tree-engine.md) | The Grove 2.3 for procedural tree generation | Accepted | 2026-05-11 |
| [ADR-002: USD Pipeline Format](adrs/adr-002-usd-pipeline-format.md) | Pixar USD / usd-core for 3D asset exchange | Accepted | 2026-05-11 |
| [ADR-003: Python Environment — conda](adrs/adr-003-conda-environment.md) | conda (not venv/poetry) for environment management | Accepted | 2026-05-11 |

---

## Project Guides

| Guide | Topic | Date |
|-------|-------|------|
| [01-Pipeline Subprocess Pattern](guides/01-pipeline-subprocess-pattern.md) | Why and how each step runs isolated as a subprocess | 2026-05-11 |

---

## Package Manuals

- No package manuals yet. Existing reference docs in `docs/reference/` cover Grove API, PVE attributes, USD builder, CLI, and Python API.

---

## Research

- No research notes yet. Add research only when a concrete question is investigated.

---

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- New ADRs added to adrs/ directory
- New guides added to guides/ directory
- New manuals added to manuals/ directory
- New research added to research/ directory

**Verification:**
- [ ] All ADR links in registry are valid
- [ ] All guide links in registry are valid
- [ ] All manual links in registry are valid
- [ ] All research links in registry are valid
