# bars on the cluster: the commands, step by step

The chat cannot reach the cluster: you run these and paste the output back. Login node `master`; `/home` is shared, so
`~/bars` (read-only input) and `~/astro` are visible from every node. Nothing here writes under `~/bars`.
Claims: [verified] = run on the laptop; [not verified] = never seen on the cluster.

## 0. Once, on the laptop (you)
```bash
# create a private GitHub repository named tng50-doublebars, then:
git -C ~/astro/clap/bars remote add origin git@github.com:<you>/tng50-doublebars.git
git -C ~/astro/clap/bars push -u origin main
```

## 1. Once, on the cluster: clone, environment, tests
```bash
mkdir -p ~/astro/clap ~/astro/scratch/bars/tasks ~/astro/runs/bars
git clone -b main git@github.com:<you>/tng50-doublebars.git ~/astro/clap/bars
```
Environment. The env file, the `bars` row hook and fetch rule are committed on `core-fixes-yield-archive` (d0759d1, 2026-10-18).
On the laptop, publish that branch (it also carries the unpushed merge 7518108):
```bash
git -C ~/astro/gizmo push origin core-fixes-yield-archive
```
On the cluster (the tooling clone must be on that branch):
```bash
git -C ~/astro/gizmo pull && astro pyenv create bars          # builds ~/astro/envs/bars, installs the repo (and astroplot once cloned) editable
```
If `astro pyenv` is not available there, by hand (same pins):
```bash
module load miniforge3
conda create -y -p ~/astro/envs/bars -c conda-forge python=3.12 pip numpy=2.5.4 scipy=1.18.1 h5py=3.16.0 pandas=3.0.6 \
    pyarrow=26.0.0 pyyaml=6.0.3 matplotlib=3.11.2 astropy=8.0.2 photutils=3.1.1 pytest=9.1.1
~/astro/envs/bars/bin/pip install --no-deps -e ~/astro/clap/bars
[ -d ~/astro/analysis/astroplot ] && ~/astro/envs/bars/bin/pip install --no-deps -e ~/astro/analysis/astroplot   # needed for step 04 only
```
If conda-forge lacks one of the exact versions, drop that pin and paste the error: I record what was installed.
Tests (synthetic galaxies only, about 2-6 min on one core; they write to `~/astro/scratch/bars/pytest`):
```bash
cd ~/astro/clap/bars && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nice -n 10 ~/astro/envs/bars/bin/python -m pytest -q
```
Expected: `39 passed` (at the milestone-3 commit). Paste the last 5 lines.
Tell me whether `~/astro/analysis/astroplot` exists on the cluster (figures of step 04 need it).

## 2. Which data are there (step 00, login node, one thread, a few minutes)
```bash
cd ~/astro/clap/bars
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PY=~/astro/envs/bars/bin/python
nice -n 10 $PY scripts/00_check_data.py --config config/cluster.yaml
```
Expected: a table, one row per snapshot of `snapshots:` (99 down to 91): `snap z chunks offsets npz expect miss extra complete`, e.g.
`99 0.0000 680/680 True 903 903 0 0 True`. `expect` counts the catalog subhaloes with M* >= 1e10 Msun (SubhaloMassType[4]).
If `miss`/`extra` are not 0, the extraction used another M* definition or skipped galaxies: paste the table and
`head -c 1500 ~/astro/runs/bars/manual/checks/snap99.json`. A `header:` line means the path or file layout differs from
`config/cluster.yaml` [memory: paths from the user, not yet listed by a command].

Also list the supplementary catalogues (bar_properties.hdf5 may give an independent bar sample to compare with; paste the output):
```bash
for f in ~/bars/TNG50-1/supplementary_catalogs/*.hdf5 ~/bars/extra_data/*.hdf5; do echo "== $f"
  $PY -c "import h5py,sys; f=h5py.File(sys.argv[1],'r'); f.visititems(lambda n,o: print(n, getattr(o,'shape',''), getattr(o,'dtype',''), dict(o.attrs) if len(o.attrs)<6 else '')); print('root attrs', dict(f.attrs))" "$f" | head -40; done
```

## 3. Catalog table (step 01, login node)
```bash
for s in 99 98; do nice -n 10 $PY scripts/01_catalog_table.py --config config/cluster.yaml --snap $s; done
```
Expected per snapshot: `snap 99: N galaxies in the mass window, C centrals, K with npz -> ~/astro/runs/bars/manual/catalog/snap99.parquet`.
N is below `expect` of step 00 because of the upper cut (3e11 Msun).

## 4. Dry run of step 02 on 20 galaxies (milestone 4)
Before the first campaign, register the project in `~/astro/state/astro.conf` (lines in `cluster/proposed/astro.conf.lines`).
Without the `bars` row hook (`cluster/proposed/health/bars.sh`, a core-fixes change) `astro row` shows the generic row: fine for now.
```bash
$PY scripts/make_tasks.py --table ~/astro/runs/bars/manual/catalog/snap99.parquet --snap 99 --per-chunk 1 --max-galaxies 20 \
    --out ~/astro/scratch/bars/tasks/diag_snap99_t20.txt
astro campaign ~/astro/clap/bars/cluster/campaigns/diag_snap99_t20.campaign --dry-run
astro campaign ~/astro/clap/bars/cluster/campaigns/diag_snap99_t20.campaign
astro ls
```
The task file names the 20 most expensive galaxies, one per task (worst case for memory). Expected: the dry run prints one
sbatch line and no preflight error. While it runs: `astro row diag99_t20`, `astro log diag99_t20 -n 20`.
When it has finished, paste:
```bash
R=~/astro/runs/bars/diag99_t20
cat $R/STATUS; tail -n 3 $R/py_tasks_*.out
grep -h -e 'Maximum resident' -e 'Elapsed (wall' $R/py_tasks_*/task_*.log | sort | uniq -c | sort -rn | head -40
tail -qn 1 $R/logs/*.log | sort | uniq -c
du -sh $R/profiles; ls -l $R/profiles/snap99 | sort -k5 -n | tail -3
```
From these I set `--mem`, `NPAR` and `--time` in `diag_snap99.campaign` / `diag_snap98.campaign` (now `TODO_FROM_DRY_RUN`).
(The partition has no wall-time limit [from the user, 2026-10-18]; `--time` only has to cover the job.) Then fetch to the laptop (prints an rsync line to run **on the laptop**; until the
`bars` fetch rule is in, it brings only text files, which is enough for this step):
```bash
astro fetch diag99_t20
```
And copy the task file to the laptop so it can be committed under `cluster/tasks/` (on the laptop):
```bash
rsync -av cluster:~/astro/scratch/bars/tasks/ ~/astro/clap/bars/cluster/tasks/
```

## 5. Full snapshots (milestone 5)
```bash
for s in 99 98; do $PY scripts/make_tasks.py --table ~/astro/runs/bars/manual/catalog/snap$s.parquet --snap $s \
    --out ~/astro/scratch/bars/tasks/diag_snap$s.txt; done
astro campaign ~/astro/clap/bars/cluster/campaigns/diag_snap99.campaign --dry-run      # after I replaced TODO_FROM_DRY_RUN
astro campaign ~/astro/clap/bars/cluster/campaigns/diag_snap99.campaign
```
Expected: `N tasks, M galaxies` from make_tasks (M = galaxies with an npz). Then steps 03 and 04 on the login node, on the
finished run (they read `profiles/` and write next to it; `--table` merges the catalog columns):
```bash
R=~/astro/runs/bars/diag99
nice -n 10 $PY scripts/03_classify.py --config config/cluster.yaml --snap 99 --out $R --table ~/astro/runs/bars/manual/catalog/snap99.parquet
nice -n 10 $PY scripts/04_plot_candidates.py --config config/cluster.yaml --snap 99 --out $R
astro fetch diag99
```
Expected: `snap 99: N galaxies classified, 0 unreadable: {'single': .., 'unbarred': .., 'double_candidate': .., ...}` and
`snap 99: F figures (...) -> .../figures/snap99/index.html`. Paste both lines; we inspect the contact sheet together on the laptop
(`~/astro/runs/bars/diag99/figures/snap99/index.html`) and tune the thresholds (`--set classify.omega_nsigma=...`; 03 is cheap to rerun).

## 6. Restartability proof (RESTARTABLE.md rule 5), once
Stop a run, resume it, compare with an uninterrupted one. A resume job writes into the run directory of the stopped one
(`DBARS_OUT`); a stop file older than the new job's start is ignored, so nothing has to be cleaned.
```bash
astro campaign ~/astro/clap/bars/cluster/campaigns/diag_snap99_t20.campaign     # if not yet run: the reference
# a second run of the same tasks, stopped after a few minutes:
astro submit bars cut20 --script $HOME/astro/gizmo/scripts/cluster/submit_python_tasks.slurm --env WORKDIR=$HOME/astro/clap/bars \
    --mem 64 --time 01:00:00 -- $HOME/astro/scratch/bars/tasks/diag_snap99_t20.txt
sleep 300; astro stop cut20                               # wait until it is COMPLETED (astro ls), then resume:
astro submit bars cut20_r --script $HOME/astro/gizmo/scripts/cluster/submit_python_tasks.slurm --env WORKDIR=$HOME/astro/clap/bars \
    --env DBARS_OUT=$HOME/astro/runs/bars/cut20 --mem 64 --time 01:00:00 -- $HOME/astro/scratch/bars/tasks/diag_snap99_t20.txt
# then compare (prints 'same N/N'):
$PY - <<'EOF'
import glob, os, numpy as np
from dbars.io.profiles import read_result
a, b = os.path.expanduser("~/astro/runs/bars/diag99_t20"), os.path.expanduser("~/astro/runs/bars/cut20")
fs = sorted(glob.glob(a + "/profiles/snap99/*.h5")); same = 0
for f in fs:
    ra, rb = read_result(f), read_result(f.replace(a, b))
    same += all(np.array_equal(ra["profile"][k], rb["profile"][k], equal_nan=True) for k in ra["profile"])
print(f"same {same}/{len(fs)}")
EOF
```
Expected: `same 20/20`, `done ... stopped` in some logs of `cut20`, `status=skip` lines in the logs written by `cut20_r`.
Only after this may the campaigns use `--restartable` (and `--nice`).

## 7. Legacy scripts and sample galaxies (to the laptop; run on the laptop) — needed soon
The extraction's unit conversion decides whether snapshots 91-97 (a down to ~0.9 [memory]) need the scale-factor correction,
so please run the first rsync before the full campaigns.
```bash
mkdir -p ~/astro/scratch/bars/legacy && rsync -av --include='*/' --include='*.py' --include='*.sh' --include='*.slurm' \
    --include='*.md' --exclude='*' cluster:~/bars/ ~/astro/scratch/bars/legacy/
mkdir -p ~/astro/runs/bars/samples && rsync -av cluster:'~/bars/extracted_galaxies/subhalo_{SID1,SID2,SID3,SID4,SID5}_stars.npz' ~/astro/runs/bars/samples/
```
I pick the five SIDs from the step-01 table (barred and unbarred by the TNG50 bar catalogue) and give you the exact line.

## What is not verified on the cluster
- the template's `source activate gizmo_build` with the env's python used by absolute path (it should not matter) [not verified];
- `--mem 64` together with the template's `#SBATCH --cpus-per-task=20` [not verified; ALIGN.md 5];
- the stop-file latency over NFS (~20 s measured for a toy job, RESTARTABLE.md 5): a task finishes its current galaxy first.
