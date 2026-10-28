# Expert tree survey

A web survey for forest growth and dendrology experts, follow-up to the owner's blind beech
ranking (XRFF-576). Each respondent sees about 34 leaf-off trees: generated catalog trees and
real QSM trees, drawn the same way. For each tree they name the species, say real or
generated and rate naturalness. Then the intended species is shown, and they rate how typical
the tree is for it, tick flaws, pick a growth situation and can comment.

Live on dt.unr: **<https://dt.unr.uni-freiburg.de/survey/>** (links `#set-a` / `#set-b` pin a set).

## Files

| Path | What |
|---|---|
| `site/` | the deployable page: `index.html`, `items.json`, `img/` (64 trees, front + side). Frozen item set v1: answers refer to its codes |
| `survey_server.py` | serves `site/` and stores answers (`POST /api/answers`, `GET /api/health`); standard library only |
| `Dockerfile`, `docker-compose.yml` | the same as a container (local: port 8080 on localhost) |
| `docker-compose.dtunr.yml` | dt.unr overlay: no host port, answers on the NFS disk, seat on the dashboard's proxy network |
| `survey_template.html`, `survey_config.json`, `assemble.py` | source of `site/index.html`; edit these, then `python assemble.py` |
| `build_items.py` | rebuilds the item set from the standardised QSM sets (`conda run -n growpy`, about 8 min). Seeded, but **do not rebuild while a survey runs**: new items mean new codes |
| `items_key.csv` | which item is real, catalog or from the ranking. Gitignored; the frozen copy is in the hub, `publications/generated-vs-real-tree-structure/expert-survey/items_key_v1.csv` |
| `analyse.py` | answers + key -> `results/summary.md` and tables |

## Run it locally

Any Python 3.10+ (no packages needed):

```bash
python survey_server.py            # http://localhost:8080/, answers in ./answers/
```

or as a container: `docker compose up -d --build`. Opening `site/index.html` directly also
works: answers then stay in the browser and the last screen offers Download / Copy.

## dt.unr

The survey is its own stack and touches nothing else: no database, its own container and data
directory. The one hook is a `location /survey/` block in the dashboard's nginx
(`digital-twin-dashboard/docker/nginx/nginx.conf`). That block resolves `xrff-survey` per
request, so nginx runs whether or not the survey does.

```bash
# once: data dir on the NFS disk, owned by the squashed uid the container runs as
docker run --rm -v /media/data:/m alpine sh -c 'mkdir -p /m/xrff-survey && chown 65534:65534 /m/xrff-survey'
# deploy or update (growpy is a sparse checkout of web/expert-survey only)
cd ~/dev/growpy && git pull && cd web/expert-survey
docker compose -f docker-compose.yml -f docker-compose.dtunr.yml up -d --build
curl -s https://dt.unr.uni-freiburg.de/survey/api/health
# offline
docker compose -f docker-compose.yml -f docker-compose.dtunr.yml down
```

After `up -d --build` the container has a new address and nginx keeps the old one for up to
30 s (`resolver ... valid=30s`), so `/survey/` can answer 502 for that long. A respondent loses
nothing: the page keeps every answer in the browser and saves the whole session again with the
next tree.

Answers are one JSON per respondent in `/media/data/xrff-survey/tree-architecture-2026-10/`.
`deploytest01.json` there is the deployment check (empty answers, skipped by `analyse.py`).
They are never served back. They may hold a respondent's name, so they stay out of git.

## Analyse

```bash
scp -r dt.unr.uni-freiburg.de:/media/data/xrff-survey/tree-architecture-2026-10 answers
python analyse.py answers        # key: items_key.csv here (copy it from the hub)
```

`results/summary.md` reports species recognition, real vs generated (AUC), naturalness and
typicality per species with catalog minus real, the species confusion table, the flaws named
most often, the retest pairs and the experts' view of the owner's ranked trees.

Known confound: Grove crowns are denser than QSM crowns even after the common prune, so "real or
generated" partly measures density. Naturalness and typicality are the main outcomes.
