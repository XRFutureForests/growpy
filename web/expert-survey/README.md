# Tree look survey

A one-tree-at-a-time rating app for people who work with trees (XRFF-593). Each card shows
a leaf-off branch skeleton, its species and height, and a 1.75 m person for scale. The rater answers one question: *does this look right
for a <species> grown in a stand?* on a 1–5 scale. Right after the vote the page says where
the tree came from (a laser-scanned real tree or a generated one, and which), and the rater
can tick what looked off. No accounts: a random device id in the browser, and an invitation
key in the link.

The point is a growing list of rated trees: which real trees experts accept as reference
geometries, which generated trees fail and why, and per species whether raters can tell
generated from real at all (AUC). New trees, new regrow arms or other generators can be added
at any time.

Live on dt.unr: **<https://dt.unr.uni-freiburg.de/survey/?k=KEY>** (the key is in the
invitation; without it the page asks for the invitation link).

## Files

| Path | What |
|---|---|
| `site/index.html` | the page: one card, the 5-point row, the previous tree's source and flags |
| `survey_server.py` | serves the page, the card drawings and the API; standard library only |
| `add_items.py` | draws trees into the item store and appends them (`conda run -n growpy`) |
| `items/` | the item store (gitignored): `<id>/front.png`, `side.png`, `meta.json`, `manifest.jsonl` |
| `analyse.py` | votes + item store -> `results/summary.md` and `results/items_scored.csv` |
| `Dockerfile`, `docker-compose.yml` | the same as a container (local: port 8080 on localhost) |
| `docker-compose.dtunr.yml` | dt.unr overlay: no host port, votes and items on the NFS disk, the dashboard's proxy network |

## Adding trees

```bash
conda run -n growpy python web/expert-survey/add_items.py            # dry run: what it would add
conda run -n growpy python web/expert-survey/add_items.py --write    # draw and append
```

Every card is drawn the same way, real or generated: the descriptors' common prune, pipe-model
radii from the reported DBH (catalog allometry for growpy trees, field DBH for real ones),
true-scale line widths, a 1.75 m person (`tree_icon(figure_m=...)`).

What goes in:

- **Real trees:** stand-grown QSMs from BioDiv and Belgium, tier A/B, a resolved crown, and a
  stem that would not look broken on the card. The check covers gaps over 3 px and kinks
  over 35° in the lower 75 % of the height.
- **Generated trees:** the growpy catalog (stand radii 7 and 10 m) and every regrow arm under
  `data/output/structure/regrow/`.

How the pool is balanced:

- Only species with both real and generated trees.
- Per species and 5 m height class, as many generated trees as real ones, so height and
  species never give the answer away.
- Real trees rotate over the datasets, generated trees over the generator groups (catalog,
  each arm).

Rerunning adds only what is missing. A tree already in the store is never redrawn: the
renderer version `RENDER` is part of each record, so a new drawing style is a new item. To
retire a tree, append its record again with `"active": false`.

Kew is left out on purpose: it is open-grown, and there are no open-grown Grove trees yet.
Conifers other than Scots pine are missing because there are no stand-grown real QSMs; they
come with the fitter competition (XRFF-594).

## Run it locally

```bash
python survey_server.py                   # http://localhost:8080/, votes in ./answers
python survey_server.py --keys abc,def    # invitation only
```

or `docker compose up -d --build` (keys in `.env` as `SURVEY_KEYS=abc,def`).

## API

| Call | What |
|---|---|
| `GET /api/next?d=<device>&k=<key>` | the next card: the species with the fewest votes, then the kind (real/generated) with fewer votes, then the tree with the fewest; never one the device rated. `{"done": true}` at the end |
| `POST /api/vote` | `{d, k, id, rating, ms, pos, role, side}` -> the tree's source, only now; one vote per device and tree |
| `POST /api/flags` | `{d, k, id, flags}` for a tree the device rated |
| `GET /api/health` | items and votes |

`meta.json`, the manifest and everything outside the page, the drawings and the API answer 404.

## dt.unr

The survey is its own stack and touches nothing else: no database, its own container and data
directory. The one hook is the `location /survey/` block in the dashboard's nginx
(`digital-twin-dashboard/docker/nginx/nginx.conf`).

```bash
# item store: build locally, then copy to the data disk
scp -r web/expert-survey/items dt.unr.uni-freiburg.de:/media/data/xrff-survey/
# deploy or update (growpy is a sparse checkout of web/expert-survey only)
cd ~/dev/growpy && git pull && cd web/expert-survey
echo "SURVEY_KEYS=<key1>,<key2>" > .env          # once; never in git
docker compose -f docker-compose.yml -f docker-compose.dtunr.yml up -d --build
curl -s https://dt.unr.uni-freiburg.de/survey/api/health
# offline
docker compose -f docker-compose.yml -f docker-compose.dtunr.yml down
```

New items need no redeploy: copy the new item folders and the updated `manifest.jsonl`, and
the server picks them up on the next card. After `up -d --build`, `/survey/` can answer 502
for up to 30 s while nginx still holds the old container address.

Votes are appended to `/media/data/xrff-survey/tree-look-2026-10/votes.jsonl`. They are
never served back and stay out of git.

## Analyse

```bash
scp dt.unr.uni-freiburg.de:/media/data/xrff-survey/tree-look-2026-10/votes.jsonl answers/
conda run -n growpy python web/expert-survey/analyse.py answers/votes.jsonl
```

Ratings are centred per rater. `summary.md` has, per species, real against generated (mean,
centred difference, AUC), then per source group, per role and the flags.
`items_scored.csv` gives every tree a verdict:

- `reference`: real, at least 10 votes, 95 % interval above 3.5;
- `implausible`: interval below 2.5;
- `open`: everything else.

Known confound: Grove crowns are denser than QSM crowns even after the common prune, so part
of what raters see is density. The `density` flag and the per-group means show how much.
