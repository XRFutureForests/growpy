# Research Evidence — codebase-audit-20260610-091208

Status: completed_minimal. MCP Ref unavailable in session (warning). Sources gathered once; shared with workers.

## Evidence Cards

1. topic: dependency vulnerability auditing
   source_type: official (PyPA), tier_1
   source_ref: https://github.com/pypa/pip-audit ; https://pypi.org/project/pip-audit/
   claim: pip-audit in CI is the standard gate for known CVEs in Python dependency trees; Dependabot complements it.
   verdict: applicable — growpy has no visible dependency audit gate.
   impact: medium; actionability: add pip-audit to CI.

2. topic: lint/type gates
   source_type: best-practice, tier_2
   source_ref: https://softaims.com/blog/modern-python-tooling-uv-ruff-mypy-2026 ; https://www.kdnuggets.com/python-project-setup-2026-uv-ruff-ty-polars
   claim: 2026 standard Python quality stack = ruff (lint+format) + mypy/ty in CI; config consolidated in pyproject [tool.*].
   verdict: applicable — growpy lists ruff/black in dev deps but pyproject has no [tool.ruff]/[tool.mypy] sections.
   impact: medium.

3. topic: src layout
   source_type: best-practice, tier_2
   source_ref: https://inventivehq.com/blog/pyproject-toml-complete-guide
   claim: src/ layout prevents accidental import of uninstalled code; growpy follows it correctly.
   verdict: informational.

4. topic: joblib parallel safety
   source_type: official docs, tier_1
   source_ref: https://joblib.readthedocs.io (via Context7 /joblib/joblib)
   claim: worker functions must avoid mutating shared state unless require='sharedmem' (threading); on Windows, multiprocessing entry points need __main__ guards; control inner_max_num_threads to avoid oversubscription.
   verdict: applicable — growpy uses joblib; ln-628 should verify worker purity and Windows entry-point guards.
   impact: medium-high.

5. topic: supply chain
   source_type: best-practice, tier_2
   source_ref: https://bernat.tech/posts/securing-python-supply-chain/
   claim: pin/lock dependencies, avoid unpinned VCS dependencies in install requirements.
   verdict: applicable — pyproject installs pylometree from unpinned git URL (no rev pin).
   impact: medium.
