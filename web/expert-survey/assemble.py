"""Assemble the survey page from survey_template.html, site/items.json and survey_config.json.

    python web/expert-survey/assemble.py

Writes
- ``site/index.html``: a complete document; ``site/`` runs as it is (double-click, a USB
  stick, ``survey_server.py``, which also stores the answers);
- ``artifact.html`` (gitignored): the same page without the document skeleton, for a
  claude.ai Artifact published with ``img/`` beside it.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "site"

items = json.loads((APP / "items.json").read_text(encoding="utf-8"))
cfg_path = HERE / "survey_config.json"
config = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
page = (HERE / "survey_template.html").read_text(encoding="utf-8")
page = page.replace("/*ITEMS*/[]", json.dumps(items, separators=(",", ":")))
page = page.replace("/*CONFIG*/{}", json.dumps(config, separators=(",", ":")))

(HERE / "artifact.html").write_text(page, encoding="utf-8")
doc = (
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "<style>img{max-width:100%}[hidden]{display:none!important}body{margin:0}</style>"
    f"</head><body>\n{page}\n</body></html>\n"
)
(APP / "index.html").write_text(doc, encoding="utf-8")
print(f"{len(items)} items -> {APP / 'index.html'} and {HERE / 'artifact.html'}")
