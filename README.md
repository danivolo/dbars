# tng50-doublebars (`dbars`)

Find candidate double-barred (and control single-barred) galaxies in TNG50-1 from already-extracted star particles:
catalog selection, re-centring and face-on rotation, Fourier m=2 profiles, single-snapshot pattern speeds
(continuity method, Dehnen, Semczuk & Schönrich 2023), isophote ellipse fits, and a two-plateau classifier.
Short project name in the `~/astro` workflow: **`bars`**. The full brief is `~/astro/docs/bars.md`.

## Layout
- `src/dbars/` library (pure functions on NumPy arrays, units in every docstring)
- `scripts/` pipeline steps 00–04 and `make_tasks.py` (I/O, looping, logging only)
- `config/` YAML: `default.yaml` (analysis), `cluster.yaml` (cluster paths), `local_test.yaml` (synthetic data)
- `cluster/` the commands the user runs on the cluster (`cluster/README.md`), campaign and task files, proposals for the shared tooling
- `plots/` result figures (astroplot contract), `tests/` pytest on synthetic galaxies, `docs/DECISIONS.md`

No data and no outputs live in this repository. Outputs go to `--out`, else `$ASTRO_RUNDIR`, else `paths.outputs`.

## Laptop environment
Until `envs/bars.yml` is in the shared tooling (`cluster/proposed/envs/bars.yml`):
```bash
cd ~/astro/clap/bars
uv venv --python 3.12 ~/astro/envs/bars
uv pip install --python ~/astro/envs/bars/bin/python -e '.[test]'
uv pip install --python ~/astro/envs/bars/bin/python -e ~/astro/analysis/astroplot   # figures only
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 ~/astro/envs/bars/bin/python -m pytest
```

## Pipeline
All scripts take `--config`, `--set key=value` (repeatable), `--out`; per-snapshot ones `--snap`. Output root: `--out` >
`$DBARS_OUT` (resume into an earlier run) > `$ASTRO_RUNDIR` (cluster job) > `paths.outputs`.

| step | script | writes (under the output root) |
|---|---|---|
| 00 | `scripts/00_check_data.py` | `checks/snap<S>.json` + a table to paste |
| 01 | `scripts/01_catalog_table.py --snap S` | `catalog/snap<S>.parquet` |
| — | `scripts/make_tasks.py --table T --snap S` | the task file for 02 (one line per ~20 galaxies, `--sids` lists, longest first) |
| 02 | `scripts/02_galaxy_diagnostics.py --snap S --sids a,b \| --chunk i/n` | `profiles/snap<S>/sub_<SID>.h5`, `logs/<name>.log` (`done N/M failed K`) |
| 03 | `scripts/03_classify.py --snap S` | `classification_snap<S>.parquet` |
| 04 | `scripts/04_plot_candidates.py --snap S` | `figures/snap<S>/sub_<SID>.png`, `figures/snap<S>/index.html` |

Step 02 is restartable: one file per galaxy (atomic), finished galaxies skipped, failures logged and skipped, and a clean stop
between galaxies when `<root>/output/stop` exists (newer than the job start). Cluster commands: `cluster/README.md`.

Try it on synthetic galaxies (laptop, a few minutes):
```bash
export DBARS_SYNTH_DIR=~/astro/scratch/bars/synthetic PY=~/astro/envs/bars/bin/python
$PY -c "import sys; sys.path.insert(0, 'tests'); from conftest import write_synthetic_sample as w; from pathlib import Path; import os; w(Path(os.environ['DBARS_SYNTH_DIR']), 99, {3: 'double', 5: 'single', 8: 'disc'})"
C="--config config/local_test.yaml"                       # outputs in ~/astro/scratch/bars/local_test
$PY scripts/00_check_data.py $C && $PY scripts/01_catalog_table.py $C --snap 99
$PY scripts/02_galaxy_diagnostics.py $C --snap 99 --chunk 1/1 && $PY scripts/03_classify.py $C --snap 99 && $PY scripts/04_plot_candidates.py $C --snap 99
```

## Open NOTEs (to check, not silently assumed)
- Catalog layout `groups_<SNAP:03d>/fof_subhalo_tab_<SNAP:03d>.<i>.hdf5`, offsets `offsets_<SNAP:03d>.hdf5` (TNG convention [memory]); 00_check_data confirms.
- Units in `dbars.io.catalogs.UNITS` from the TNG documentation [memory]; unknown fields raise instead of guessing.
- npz scale factor: assumed the extraction did pos/h with a = 1 (`docs/DECISIONS.md` D10); `particles.correct_scale_factor` off until the legacy script is read.
- M* of the extraction cut vs `SubhaloMassType[4]`: 00_check_data compares the two sets.

## Status per milestone
- [x] 1. Skeleton: repo, pyproject, config loading, docs, pytest
- [x] 2. Library and synthetic tests (legacy scripts and the sample galaxies still to read/check: need the user's rsync, `cluster/README.md` §7)
- [x] 3. Scripts and cluster files (proposals for the shared tooling in `cluster/proposed/`, waiting for the user)
- [ ] 4. Cluster dry run (user)
- [ ] 5. Full snap 99 and 98
- [ ] 6. Time evolution (SubLink)
- [ ] 7. Mock-data release
