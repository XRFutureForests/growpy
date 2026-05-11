# Task Navigation

<!-- SCOPE: Quick navigation to active tasks. Links point to Linear (provider=linear) per .hex-skills/environment_state.json. -->
<!-- DOC_KIND: how-to -->
<!-- DOC_ROLE: working -->
<!-- READ_WHEN: Read when you need the current board, provider setup, or epic/story/task navigation. -->
<!-- SKIP_WHEN: Skip when you only need workflow policy or template rules. -->
<!-- PRIMARY_SOURCES: .hex-skills/environment_state.json, docs/tasks/README.md, Linear -->
<!-- DO NOT add here: task descriptions, implementation notes, workflow rules → tasks/README.md -->

> **Last Updated**: 2026-05-11 (Hierarchical format: Status → Epic → Story → Tasks)

## Quick Navigation

- [Task Rules](./README.md)
- [Reference Hub](../reference/README.md)
- [Architecture](../project/architecture.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Gives live navigation and provider-specific board setup for GrowPy active work. |
| Read When | You need current epics, stories, tasks, or provider coordinates. |
| Skip When | You only need lifecycle policy or documentation standards. |
| Canonical | No — working document |
| Next Docs | [Task Rules](./README.md) |
| Primary Sources | Linear (`geosense-ufr` workspace, `XRFF` team) |

---

## Provider Configuration

**Task provider:** Linear

### Linear Configuration

| Variable | Value | Description |
|----------|-------|-------------|
| **Team Name** | XR Future Forests | Linear team name |
| **Team UUID** | 5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf | Team UUID for API calls |
| **Team Key** | XRFF | Short key for issues |
| **Workspace URL** | https://linear.app/geosense-ufr | Linear workspace |

**Quick Access:**
- [Backlog](https://linear.app/geosense-ufr/team/XRFF/backlog)
- [Active Sprint](https://linear.app/geosense-ufr/team/XRFF/active)

### Common Configuration

| Variable | Value | Description |
|----------|-------|-------------|
| **Next Epic Number** | 1 | Next available Epic number |

---

## Epic Story Counters

| Epic | Last Story | Next Story | Last Task | Next Task |
|------|------------|------------|-----------|-----------|
| Epic 0 | — | US001 | — | T001 |
| Epic 1+ | — | US001 | — | T001 |

> Story numbering: US001+ per Epic. Task numbering: T001+ per Story.

---

## Work in Progress

**Format:** Status → Epic → Story → Tasks hierarchy. Stories use 2-space indent. Tasks use 4-space indent.

**Important:** Stories without tasks appear only in Backlog/Postponed with note: `_(tasks not created yet)_`

**Critical:** Done/Postponed sections contain only Stories (no Tasks).

### Backlog

No active backlog items.

### Todo

No items in Todo.

### In Progress

No items in progress.

### To Review

No items in review.

### To Rework

No items in rework.

### Done

No completed items tracked yet.

---

## Workflow Reference

| Status | Purpose |
|--------|---------|
| **Backlog** | New items requiring estimation and approval |
| **Postponed** | Deferred for future iterations |
| **Todo** | Approved, ready for development |
| **In Progress** | Active development |
| **To Review** | Awaiting review |
| **To Rework** | Needs fixes |
| **Done** | Completed and approved (last 5 stories only) |

**Manual Statuses:** Canceled, Duplicate

---

## Maintenance

**Update Triggers:**
- Epic, story, or task navigation changes
- Provider settings change
- Board numbering changes

**Verification:**
- [ ] Linear team UUID and key match active workspace
- [ ] Board links resolve
- [ ] Next counters reflect current board state

**Last Updated:** 2026-05-11

---

## Related Documentation

- [tasks/README.md](./README.md) — Task system workflow and rules
- [Reference Hub](../reference/README.md) — ADRs, guides, manuals
