# GrowPy


@AGENTS.md

## Claude Code

- `/compact` preservation order: architecture decisions, modified files, verification status, open TODOs, tool outputs as summaries only.
- Auto memory is on by default. Claude writes learnings to `~/.claude/projects/<project>/memory/` — run `/memory` to inspect or edit.
- Scope path-specific rules to `.claude/rules/*.md` with a `paths:` frontmatter filter rather than inlining conditional blocks here.
- Nested `CLAUDE.md` files in subdirectories (e.g. `.claude/CLAUDE.md`) load on demand for area-specific guidance.
