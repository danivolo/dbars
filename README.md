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

## Status per milestone
- [x] 1. Skeleton: repo, pyproject, config loading, docs, pytest
- [ ] 2. Library and synthetic tests
- [ ] 3. Scripts and cluster files
- [ ] 4. Cluster dry run (user)
- [ ] 5. Full snap 99 and 98
- [ ] 6. Time evolution (SubLink)
- [ ] 7. Mock-data release
