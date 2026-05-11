# Task Tracking System

<!-- DOC_KIND: index -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need the task system workflow, state transitions, and provider rules. -->
<!-- SKIP_WHEN: Skip when you only need the live board or a specific task artifact. -->
<!-- PRIMARY_SOURCES: .hex-skills/environment_state.json, docs/tasks/kanban_board.md, docs/reference/guides/testing-strategy.md -->
<!-- SCOPE: Task tracking system workflow and rules ONLY. Contains task lifecycle, naming conventions, and integration rules. -->
<!-- DO NOT add here: actual task details → task files, kanban status → kanban_board.md, implementation guides → guides/ -->

## Quick Navigation

- [Kanban Board](kanban_board.md)
- [Reference Hub](../reference/README.md)
- [Architecture](../project/architecture.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Defines task workflow, provider rules, status meanings, and task-document conventions for GrowPy. |
| Read When | You need workflow rules, provider behavior, or task lifecycle guidance. |
| Skip When | You only need the current active items. |
| Canonical | Yes |
| Next Docs | [Kanban Board](kanban_board.md), [Reference Hub](../reference/README.md) |
| Primary Sources | `.hex-skills/environment_state.json`, `docs/tasks/kanban_board.md` |

---

## Overview

This folder contains the GrowPy project's task management system, organizing all development work into trackable units with clear status progression. Task provider: **Linear** (`workspace: xr-future-forests-lab`, `team: XR Future Forests Lab`).

### Folder Structure

```
docs/tasks/
├── README.md           # This file — task tracking workflow and rules
└── kanban_board.md     # Live navigation to active tasks
```

> All task tracking (Epics, User Stories, Tasks) is managed in **Linear** via the `mcp__linear__*` MCP methods. Linear is the single source of truth.

**Live Navigation**: [Kanban Board](kanban_board.md)

---

## Core Concepts

### Task Lifecycle

**Workflow:**

```
Backlog/Postponed → Todo → In Progress → To Review → Done
                                              ↓
                                         To Rework → (back to In Progress)
```

**Statuses:**

| Status | Meaning |
|--------|---------|
| Backlog | New items requiring estimation and approval |
| Postponed | Deferred for future iterations |
| Todo | Approved, ready for development |
| In Progress | Currently being developed |
| To Review | Awaiting code review and validation |
| To Rework | Needs fixes after review |
| Done | Completed, reviewed, tested, approved |

**Manual statuses (not in workflow):** Canceled, Duplicate

### Epic Structure

| Level | Linear Entity | Format |
|-------|--------------|--------|
| Epic | Linear Project | Name + description + target date |
| User Story | Linear Issue with label `user-story` | "As a… I want… So that…" + Given-When-Then AC |
| Task | Linear sub-issue of Story | Context + requirements + acceptance criteria |

### Foundation-First Execution Order

**Critical Rule:** Foundation tasks execute BEFORE consumer tasks (for testability).

| Layer | Examples |
|-------|---------|
| Foundation | Data processing, core pipeline modules, config |
| Consumer | CLI commands, export scripts, downstream integrations that USE foundation |

---

## Critical Rules

### Rule 1: Linear Integration

**CRITICAL:** Use `mcp__linear__*` MCP methods for all task operations. Do NOT use the `gh` command or direct Linear REST API.

### Rule 2: Tests Consolidated in Story Finalizer

**Rule:** Tests are created ONLY in the final Story task (Story Finalizer test task). Never create separate test tasks during implementation.

**Process:**
1. Implementation tasks (1-6 tasks) → To Review → Done
2. Quality gate → manual testing
3. Test planner → creates Story Finalizer test task
4. Test executor → implements all tests (E2E, Integration, Unit)

### Rule 3: Documentation Integrated in Feature Tasks

**Rule:** Documentation updates are ALWAYS part of the same task as implementation. Never create separate "Update README" or "Write API docs" tasks.

### Rule 4: Context Budget — Kanban Links Only

**Rule:** `kanban_board.md` contains ONLY links and titles — no descriptions, no implementation notes.

---

## Linear Integration

### Team Configuration

| Variable | Value |
|----------|-------|
| Workspace | `xr-future-forests-lab` |
| Team Name | XR Future Forests Lab |
| Linear URL | `https://linear.app/xr-future-forests-lab` |

### Epic Operations

| Operation | MCP Method |
|-----------|-----------|
| List Epics | `mcp__linear__list_projects(team=teamId)` |
| Get Epic | `mcp__linear__get_project(query="Epic N")` |
| Create Epic | `mcp__linear__save_project({name, description, team, state: "planned"})` |
| Update Epic | `mcp__linear__save_project({id, state, description})` |

### Story Operations

| Operation | MCP Method |
|-----------|-----------|
| List Stories | `mcp__linear__list_issues(project=epicId, label="user-story")` |
| Get Story | `mcp__linear__get_issue(id=storyId)` |
| Create Story | `mcp__linear__save_issue({title: "US{NNN}: Title", project: epicId, team, labels: ["user-story"], state: "Backlog"})` |
| Update status | `mcp__linear__save_issue({id, state: "In Progress"})` |

### Task Operations

| Operation | MCP Method |
|-----------|-----------|
| List Tasks | `mcp__linear__list_issues(parentId=storyId)` |
| Get Task | `mcp__linear__get_issue(id=taskId)` |
| Create Task | `mcp__linear__save_issue({title: "T{NNN}: Title", parentId: storyId, team, labels: ["implementation"], state: "Backlog"})` |
| Update status | `mcp__linear__save_issue({id, state: "Done"})` |

### Common Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team` | string | Team name or UUID |
| `state` | string | Backlog, Todo, In Progress, To Review, To Rework, Done |
| `assignee` | string | User ID, name, email, or "me" |
| `labels` | string[] | user-story, implementation, tests, refactoring, bug |
| `limit` | number | Max results (default 50, max 250) |

---

## Task Workflow

### Planning Guidelines

| Criterion | Rule |
|-----------|------|
| Optimal task size | 3-5 hours per task |
| Too small | < 2 hours → merge with related task |
| Too large | > 8 hours → split into subtasks |
| Story limit | Max 6 implementation tasks + 1 finalizer test task |

### Workflow Skills

| Category | Skill | Purpose |
|----------|-------|---------|
| Planning | ln-210-epic-coordinator | Decompose scope → 3-7 Epics |
| Planning | ln-220-story-coordinator | Decompose Epic → 5-10 Stories |
| Planning | ln-300-task-coordinator | Decompose Story → 1-6 Implementation Tasks |
| Validation | ln-310-multi-agent-validator | Validate Stories/Tasks → Approve (Backlog → Todo) |
| Execution | ln-400-story-executor | Orchestrate Story execution |
| Execution | ln-401-task-executor | Execute implementation tasks |
| Execution | ln-404-test-executor | Execute Story Finalizer test tasks |
| Review | ln-402-task-reviewer | Review tasks (To Review → Done/Rework) |
| Rework | ln-403-task-rework | Fix tasks after review (To Rework → To Review) |

---

## Task Templates

### User Story Template

```
Title: US{NNN}: [Feature name]
Labels: user-story
Project: [Epic Name]
State: Backlog

As a [role], I want [feature], so that [benefit].

Acceptance Criteria:
- Given [context], when [action], then [result]
```

### Implementation Task Template

```
Title: T{NNN}: [Action + Component]
Labels: implementation
Parent: [Story ID]
State: Backlog

Context: [Why this task exists]
Requirements: [What must be built]
Acceptance Criteria: [Verifiable done conditions]
```

### Story Finalizer Test Task Template

```
Title: T{NNN}: Tests — [Story Name]
Labels: tests
Parent: [Story ID]
State: Backlog (created after all implementation tasks are Done)

Test scope:
- E2E: [N scenarios, Priority ≥15]
- Integration: [N scenarios]
- Unit: [N scenarios]
```

---

## Story-Level Test Strategy

**Value-Based Testing:** Test only scenarios with Risk Priority ≥15 (Impact × Likelihood).

Each test must pass all 6 usefulness criteria: Risk Priority ≥15, Confidence ROI, Behavioral, Predictive, Specific, Non-Duplicative. No numerical targets — test count driven by risk assessment.

**Reference:** [Risk-Based Testing Guide](../reference/guides/risk-based-testing-guide.md)

---

## Label Taxonomy

| Category | Labels |
|----------|--------|
| Functional | feature, bug, refactoring, documentation, testing, infrastructure |
| Type | user-story, implementation-task, test-task |
| Status (auto) | backlog, todo, in-progress, to-review, to-rework, done, canceled |

---

## Maintenance

**Update Triggers:**
- When Linear workspace or team name changes
- When workflow skills are added or renamed
- When task lifecycle statuses change
- When test strategy limits are updated

**Verification:**
- [ ] Linear team coordinates match `kanban_board.md`
- [ ] Workflow skills table matches available skills
- [ ] Critical Rules align with current development principles

**Last Updated:** 2026-05-11
