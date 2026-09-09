# `data/` - growpy

Workspace-standard data layout:

| Folder | Purpose | Committed |
|---|---|---|
| `input/` | acquired or supplied inputs | small files only |
| `output/` | regenerable products | no |
| `tmp/` | run scratch | no |

Scratch belongs in `data/tmp/` - not a repo-root `tmp/`, `temp/` or `outputs/`.
