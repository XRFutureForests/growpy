# Reference QSM datasets

Real-tree TreeQSM reference data for judging the structure of Grove-generated trees
(`growpy-qsm-to-growth`, `growpy-structure-descriptors`). Downloaded 2026-10-06 from the
original repositories; everything here except this README is git-ignored and re-downloadable.
QSM data only: no point clouds (TLS, ULS, ALS) and no foliage meshes were kept.

| Folder | Source | Content | Licence |
|--------|--------|---------|---------|
| `biodiv3dtrees_qsm/` | GRO.data [10.25625/8PB1IF](https://doi.org/10.25625/8PB1IF), paper [10.1038/s41597-025-06421-7](https://doi.org/10.1038/s41597-025-06421-7) | `QSM/raw/` (selected optimal TreeQSM 2.4.1 `.mat`) and `QSM/corrected/` (rTwig 1.4.0 corrected cylinder CSVs) for 3,386 broadleaf trees, streamed out of the 103 GB `QSM.tar.zst`. `QSM/all/` (the 80 candidate models per tree, about 95 GB) skipped | CC BY 4.0 |
| `biodiv3dtrees_graphs/` | same record | `Graphs.tar.zst` (cleaned QSM graphs, the GraphML `growpy-qsm-to-growth` reads), `labels.csv` (validity flags, species, split, volQSM), `README.md` (column dictionary) | CC BY 4.0 |
| `belgium_beech_pine_ash_larch/` | [Zenodo 4557401](https://zenodo.org/records/4557401) | 65 destructively harvested trees: `optimal_QSMs.zip` (TreeQSM 2.3 `.mat`), `Destructive_and_qsm_data_DEMOL.csv` (reference volume) | CC BY 4.0 |
| `pulse_frequency_ghent/` | [Zenodo 10671784](https://zenodo.org/records/10671784) | `optimal_QSMs.zip` (223 models: Austria 111, Gabon 39 (tropical), Belgium leaf-on 42 and leaf-off 31; each tree once per pulse frequency; flat TreeQSM layout; no species, DBH or height published), `tree_metrics_dataframe.csv` | CC BY 4.0 |
| `simpleforest_benchmark/` | [Zenodo 5131717](https://zenodo.org/records/5131717) | `tableAll.csv` only (field versus QSM volume per tree, TreeQSM and SimpleForest) | CC BY 4.0 |
| `treeml_munich/` | figshare collection [6788358](https://doi.org/10.6084/m9.figshare.c.6788358.v1), paper [10.1038/s41597-023-02873-x](https://doi.org/10.1038/s41597-023-02873-x) | 3,755 leaf-off urban trees: `Dataset_QSM.zip` (`opt/` `.mat`, `optcsv/` cylinder CSVs, `trans/`), `TreeML_Dataset.csv`, `TreeML_Dataset_QSM.csv` | CC0 |
| `wytham_woods/` | [Zenodo 7307956](https://zenodo.org/records/7307956) | `DATA_QSM_opt.zip`: 835 optimised TreeQSM models (`.mat`, 37.6 GB) | CC BY 4.0 |
| `kew_wakehurst/` | [Zenodo 15373627](https://zenodo.org/records/15373627) | `broadleaf_qsm.zip`, `conifer_qsm.zip`, `coppice_qsm.zip` (TreeQSM `.mat`), `kew-wakehurst-agc.csv` | OGL-UK-3.0 |
| `czech_central_european/` | [datarepo.eosc.cz](https://datarepo.eosc.cz/datasets/records/datst.xkadt-0cb92), DOI 10.48700/datst.xkadt-0cb92 | Only the trunk-and-branch `*_QSM.obj` meshes (`3D_TREES/<SPECIES>/<tree>/`), `3D_TREE_METADATA.csv`, `ReadMe.txt`, extracted from `Tree_dataset.zip` by range request. Meshes are reconstructed from TLS, not raw QSM cylinders | **CC BY-NC** (non-commercial) |

## Quality tiers

Keep the tier with every tree that enters a comparison; do not pool tiers anonymously.

| Tier | Meaning | Datasets | Use |
|------|---------|----------|-----|
| A | Documented validation flags and corrected topology | BioDiv with `validQSM == True` (and `validDBH`, `validH`, `validCPA`), corrected CSV | Main structural reference |
| B | Independent harvested reference volume | Belgium (65 trees), SimpleForest `tableAll.csv` | Validate volume and taper, detect systematic QSM bias |
| C | Published QSM, metadata, no strong independent check | TreeML, Wytham, Kew, Czech meshes, pulse-frequency | Species and architecture expansion, after our own acceptance checks |

`validQSM` means the QSM agrees with its own point cloud (height, DBH, crown projection
area). It does not prove the branch topology is botanically right.

## Numbers checked against `labels.csv` (2026-10-06)

- 3,386 trees have a QSM; **1,889 have `validQSM == True`** and all four flags true. A summary
  of the paper quoted 1,925; the file says 1,889, so use the file.
- Valid trees are 88% beech: *Fagus sylvatica* 1,659, *Quercus* 88, *Acer pseudoplatanus* 42,
  *Carpinus betulus* 38, *Fraxinus excelsior* 36, *Betula* 15, *Tilia* 5, *Acer platanoides* 4,
  *Prunus* 2. Only beech is well covered; linden and the two *Prunus* are too few to compare.
- All 1,543 conifers (Norway spruce, Scots pine and others) have no QSM.

## Conifers in this set

| Source | Trees | Notes |
|--------|-------|-------|
| Belgium | 30 *Pinus sylvestris*, 5 *Larix decidua* | Tier B. Our QSM volume over harvested volume: pine median 1.06 (p10 0.97, p90 1.19), larch median 2.01. Beech 1.23 and ash 1.27. Use pine as a structural reference; treat larch as a known failure case |
| Kew | 423 *Picea abies* (conifer zip: 451 files, the csv labels 434 conifer-habitat rows, a few of which name an oak) | Tier C |
| Czech meshes | 90 *Picea abies* | AdQSM trunk-and-branch meshes, not cylinder tables; not importable into the standard yet |
| Ghent, Wytham | species not yet resolved | Ghent publishes none; Wytham checked when its download ends |

BioDiv has no conifer QSM. The SimpleForest archive holds point clouds and scripts, not
finished QSMs, so only its volume table is kept. Larger conifer sets (German multi-platform
trees, TreeScanPL10K, NEWFOR) are point-cloud datasets: using them means running our own
QSM reconstruction, which has not been decided and is outside the QSM-only download.

## Limits when comparing

A QSM is a cylinder fit to leaf-off TLS: twigs are missing, radii of thin and distal branches
are overestimated, upper-crown branches are often incomplete, and TreeQSM can join cylinders
to the wrong parent in sparse regions. BioDiv's corrected CSVs address radius and some
connections, not occlusion. Forest-grown trees (BioDiv, Wytham, Kew, Belgium) and urban
street trees (TreeML) differ in architecture. Conifer QSMs exist only in Belgium (pine,
larch), Kew, and the Czech meshes.
