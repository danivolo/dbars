# bars: cockpit round 1 answers (2026-10-30)

Questionnaire: `~/astro/docs/cockpit/QUESTIONNAIRE.md`. Repo `~/astro/clap/bars`, branch `main`. No GIZMO numbers anywhere in this project.
Tags: [verified] = read from a file or run by a command while writing this; [memory] = from an earlier session or the user, not rechecked now.
**Cluster state caveat:** the last cluster output I saw was on 2026-10-19 (unit tests 39 passed, step 00/01, first cutouts). I have not seen the result of the
20-galaxy dry run (`diag99_t20`, submitted, in the queue then) nor of the retry of 17 failed snap-98 cutouts. Everything about the cluster below is [memory] from then.

---------------------------------------------------------------------------------------------------------------------------------------------------

## Q1 Alignment with `~/astro/CLAUDE.md`

| rule | yes/no | where / gap |
|---|---|---|
| Worktree, branch | yes, with a note | non-GIZMO: repo `~/astro/clap/bars`, no `wt/` (ALIGN.md §1.1) [verified: `git branch`]. All work is committed on `main`, one commit per milestone step, nothing pushed by me (the user pushed; 12 commits, `origin/main` = `main` = e89f65c at the time of writing [verified]). No feature branches. *Question for the user:* is "never commit to master" meant for `main` of non-GIZMO repos too? |
| Scratch in `scratch/bars/` | yes | `~/astro/scratch/bars/{dev,hooktest,legacy,pytest}` [verified]. pytest's `basetemp` is moved there in `tests/conftest.py`. *Gap, now closed:* the first test runs used pytest's default `/tmp/pytest-of-dvolo`; they were emptied, and nothing from the project lives in /tmp [verified: `ls`] |
| `runs/bars/<run>/` | yes | `~/astro/runs/bars/{samples,samples_check}` (real npz for manual checks; profiles and figures of 5 galaxies). Cluster runs: none fetched yet |
| RUNINFO | gap | `samples_check` (a laptop run of my own script) has no RUNINFO. Cluster runs get one from `astro submit`, with **`conda_env=gizmo_build`** (hard default `${ASTRO_CONDA_ENV:-gizmo_build}` in `astro`, line 244 [verified]), although our task lines call `$HOME/astro/envs/bars/bin/python` by absolute path. Same problem as omega; the RUNINFO says the wrong environment, the code runs in the right one. **Update 2026-10-30 (astro-43):** `aed92e8` on `core-fixes` replaces that line for `--script` runs with "chosen by the script ..." [verified: `git show aed92e8:scripts/cluster/astro`]. `core-fixes-yield-archive`, the branch the cluster tooling clone follows for the bars files, does **not** contain it yet [verified: `merge-base --is-ancestor`], so it applies only after that branch merges `core-fixes` (the user's call) and the cluster clone is pulled |
| Campaign headers | partial | 3 campaigns (`cluster/campaigns/diag_snap99_t20`, `diag_snap99`, `diag_snap98`) have `#question #criteria #cost`; none has `#expect #view #by #next #nice` [verified]. `diag_snap9x` still carry `--time TODO_FROM_DRY_RUN`. Will be added with the draft below |
| `astro` instead of hand-written sbatch | yes | only `--script $HOME/astro/gizmo/scripts/cluster/submit_python_tasks.slurm`; no private job template |
| `astro pyenv` | yes | `envs/bars.yml` committed on `core-fixes-yield-archive` (d0759d1, cc65b34); it built on the cluster after one pin fix (pyarrow 26 → 25, DECISIONS D15) and the 39 tests passed there [memory: user's paste, 2026-10-19]. Not on plain `core-fixes` (that branch has no `envs/`) |
| paperlib | yes | `paper ls --project bars`: dehnen22 (4 uses, **3 verified**: eq. 10, A4b, 25, read in the paper), erwin03, du15, rosasguevara21, zana22 (1 use each, **0 verified**: ids looked up on the web, content not read) [verified]. `paper verify` warns that dehnen22 is "verified use but no PDF hash": I read it through a tool, not from a stored PDF. Fix on request: `paper add 2211.00674 --download` |
| DECISIONS / LESSONS | DECISIONS yes, LESSONS gap | `docs/DECISIONS.md`: D1–D20, per-change style; docs claims tagged. Nothing appended to `docs/LESSONS.md`; three proposals below |
| Memory naming | n/a | this project has written no auto-memory file (none to prefix `bars-`) [verified: the memory directory is empty] |
| Scope | yes, one disclosure | edits only in `clap/bars`, `scratch/bars`, `runs/bars`. **Outside scope, with the user's OK ("shared tool proposals: ok", 2026-10-19):** two commits on `core-fixes-yield-archive` in `wt/_scratch/yield-archive` (d0759d1: env file, row hook, fetch rule, conf line, tests; cc65b34: pyarrow pin). Another session's uncommitted edits in that worktree (snakegen) were left alone |
| Never push; never kill others' processes | yes | one `kill` of my own test process by explicit PID; no `pkill -f` |
| `uptime` before long jobs | partial | I checked `uptime` several times and noted the load (30–50) in `CLAUDE.md`, but ran 3–7 min pytest suites without `nice`. Will use `nice -n 10` |
| Tracked files hygiene | yes | `.gitignore`: `*.npz *.h5 *.hdf5 *.parquet outputs/ logs/`; scripts are 755 [verified: `git ls-files -s`] |

**astroplot on the cluster:** *not as intended.* [memory] On 2026-10-18 the user said it is not cloned there and would provide it; I have no confirmation since.
Laptop: installed editable in `~/astro/envs/bars` [verified]. `envs/bars.yml` has a second `# astro-editable: ~/astro/analysis/astroplot` line, which `astro pyenv`
skips with a warning when the directory is missing [verified: `lib/pyenv.sh`]. **What breaks without it: only step 04** (figures); `scripts/04_plot_candidates.py`
and `src/dbars/plotting.py` import it, nothing else does [verified: grep]. Check on the cluster:
`ls ~/astro/analysis/astroplot && ~/astro/envs/bars/bin/python -c "import astroplot; print(astroplot.__file__)"`.

**LESSONS proposals** (for the user to approve; not appended):
1. `astro pyenv` pins taken from a PyPI-built laptop environment can be missing on conda-forge (pyarrow 26.0.0, cluster build failed): check every pin with `api.anaconda.org/package/conda-forge/<name>` before committing an env file.
2. A task farm runs ~20 tasks per job: a stop file must not be deleted by the first task that sees it (GIZMO's way); keep it and ignore it when older than the job start (STATUS `start=`).
3. `# ASTRO_RESTARTABLE=1` is read from the `--script` file (the shared template), not from the task file: a header in a task file does nothing (see Q5).

---------------------------------------------------------------------------------------------------------------------------------------------------

## Q2 Live view

**Confirm, with corrections.** "Galaxies processed plus bar and double-bar candidates so far" is right as the headline, with three corrections:
1. The unit is **galaxies of the task file with a profile file** (not tasks: a task is ~20 galaxies, hours long). The proposed row hook already does this [verified: `row_bars.sh` 19/19].
2. "Candidates so far" is **provisional**: the label written by step 02 uses the config thresholds, which are untuned (milestone 5). Step 03 recomputes labels from the stored profiles in seconds, so the number can change after tuning. The view must say so (`estimate.provisional`).
3. Counts alone do not answer the campaign's question. The question is "which galaxies are *decoupled* double bars", so the useful live estimate is the fraction of `double_candidate` / `double_decoupled` among classified galaxies with its binomial error, plus the share of inner bars that are marginal (shorter than 3 softening lengths).

**Job types**

| job | stages | question (verbatim from the campaign) | estimate | update |
|---|---|---|---|---|
| catalog/data check (00, 01), by hand, minutes | none | — | no view (`#view: none — minutes, by hand`) | — |
| **diag (02)**, the campaign | one: galaxy diagnostics, 20 tasks at a time; 03 and 04 are by hand afterwards | `#question` of `diag_snap99.campaign`: "bar diagnostics (Fourier, Omega_p, ellipse fits, maps, first labels) for every snap-99 galaxy with an npz" | fraction labelled double (candidate + decoupled) among galaxies done, ± binomial; counts per label | 3 min |
| cutout download (`fetch_cutouts.py`), login node, not a campaign | one | — | galaxies done / total, failed, GB, eta (its own progress lines) | 20 galaxies |

**Checks (diag).** Three states, always with numbers, and a reference where one exists. **All thresholds below are proposals; none is calibrated on cluster data**
(the only real timings are 5 laptop galaxies at ~30 s CPU, 2–3·10⁵ stars; the 20-galaxy dry run will give the reference):

| check | value | PASS | WARN | FAIL | reference |
|---|---|---|---|---|---|
| task exits | non-zero exits | 0 | — | ≥ 1 | — |
| failed galaxies (`status=fail` in logs) | fraction | < 1 % | 1–5 % | > 5 % | — |
| time per galaxy (rolling median) | s, and ratio to the reference | < 1.5× | 1.5–3× | > 3× | median of the 20-galaxy dry run (`diag99_t20`) |
| agreement with Zana+22 `Barred` | fraction of galaxies done where (label ≠ unbarred) = `zana_barred` | ≥ 0.85 | 0.70–0.85 | < 0.70 | none yet; legacy `cross_validate_bars.py` printed an agreement but I never saw the number |
| marginal inner bars | share of double candidates with inner length < 3 softenings | < 50 % | 50–80 % | > 80 % | — |
| stop requested | tasks stopped by the stop file | 0 | ≥ 1 (information) | — | — |

**Live curves (≤ 4):** galaxies done vs elapsed minutes (throughput); cumulative `double_candidate` and `double_decoupled` vs galaxies done (do the counts settle?);
rolling median seconds per galaxy vs galaxies done.

**Who writes it (does not exist yet).** There is no single process: 20 tasks run side by side. Proposal: `scripts/write_view.py`, called by each task after each
galaxy, doing nothing unless `view.json` is older than 3 minutes (mtime, `flock`), then reading only `logs/*.log` (one line per galaxy: sid, status, seconds, label)
and writing atomically. The Zana comparison needs the catalog table and `paths.zana_bars` on the cluster [verified: both exist as config keys]. Effort ≈ 0.5 day on the laptop,
tested on a synthetic run directory (as `row_bars.sh` does). The view then needs no new data in the run directory.

**Draft `view.json` for `diag99` (campaign `cluster/campaigns/diag_snap99.campaign`). The numbers are illustrative, not measurements**
(no cluster run has finished); the structure and the thresholds are the proposal.
```json
{
  "schema": "view/1",
  "updated": "2026-11-02T14:05:00",
  "now": "stage 1 of 1: galaxy diagnostics, 20 tasks running; 412 of 870 galaxies done, 3 failed",
  "stages": [
    {"name": "02 galaxy diagnostics", "state": "running", "fraction": 0.474, "eta": "1h20m"},
    {"name": "03 classify (by hand, login node)", "state": "not in this job"},
    {"name": "04 candidate figures (by hand)", "state": "not in this job"}
  ],
  "question": "bar diagnostics (Fourier, Omega_p, ellipse fits, maps, first labels) for every snap-99 galaxy with an npz",
  "estimate": {
    "quantity": "fraction of galaxies labelled double_candidate or double_decoupled",
    "value": 0.029, "uncertainty": 0.008, "n": 412,
    "counts": {"unbarred": 231, "single": 169, "double_candidate": 9, "double_decoupled": 3},
    "trend": "flat over the last 100 galaxies",
    "provisional": "labels use untuned thresholds (milestone 5); step 03 relabels from the stored profiles"
  },
  "checks": [
    {"name": "task exits", "state": "PASS", "value": "0 non-zero", "target": "0"},
    {"name": "failed galaxies", "state": "PASS", "value": "3/412 = 0.7 %", "target": "< 1 % (WARN 1-5 %)"},
    {"name": "time per galaxy", "state": "PASS", "value": "34 s", "target": "< 1.5x reference", "ref": "1.1x the dry-run median (31 s)"},
    {"name": "agreement with Zana+22 Barred", "state": "WARN", "value": "0.82", "target": ">= 0.85 (WARN 0.70-0.85)", "ref": "no earlier run"},
    {"name": "marginal inner bars", "state": "PASS", "value": "4/12 shorter than 3 softenings", "target": "< 50 %"}
  ],
  "series": [
    {"name": "galaxies done", "x_label": "elapsed [min]", "x": [0, 30, 60, 90], "y": [0, 120, 260, 412]},
    {"name": "double candidates", "x_label": "galaxies done", "x": [0, 120, 260, 412], "y": [0, 3, 7, 12]},
    {"name": "seconds per galaxy (rolling median)", "x_label": "galaxies done", "x": [0, 120, 260, 412], "y": [33, 35, 34, 34]}
  ],
  "notes": ["thresholds are proposals, not yet calibrated", "step 03 may change every label count"]
}
```

---------------------------------------------------------------------------------------------------------------------------------------------------

## Q3 Data products

| kind | file | produced by | size | standard plot |
|---|---|---|---|---|
| star particles (input) | `subhalo_<SID>_stars.npz` (legacy, `~/bars`, read-only) and cutouts (`~/astro/data/bars/stars_snap<S>/`, physical units, `particle_ids`, float32) | earlier extraction; `scripts/fetch_cutouts.py` | 10–300 MB | none (not a result) |
| catalog table | `catalog/snap<S>.parquet` | `01_catalog_table.py` (`sample.py`) | small | **sample view:** M★ vs r_half, centrals/satellites, has-npz |
| data check | `checks/snap<S>.json` | `00_check_data.py` | small | table: complete / missing galaxies per snapshot |
| per-galaxy profile | `profiles/snap<S>/sub_<SID>.h5` | `02_galaxy_diagnostics.py` (`analysis.py`) | < 1 MB | **snapshot level:** the 3×3 figure (`plotting.diagnostic_figure`): face-on density (full, 2 kpc zoom), m=2 residual, v_R, σ_z, edge-on, A₂/A₀ + φ₂, Ω_p(R), ε + PA, bar segments overlaid |
| classification | `classification_snap<S>.parquet` (+ `zana_*` columns) | `03_classify.py` | small | **run level:** label counts, length ratio / misalignment histograms, agreement table with Zana+22 |
| figures | `figures/snap<S>/sub_<SID>.png`, `index.html` | `04_plot_candidates.py` | ~0.1 MB each | **run level:** the contact sheet (every double candidate + 5 % controls, with a table of the key numbers) |
| logs | `logs/<name>.log` | step 02 | small | the row hook / view |

**Across a campaign (not written yet; PLOT_BRIEF requires proposing before coding).** Proposed key figures: (1) double-bar fraction vs M★ (with binomial errors, single bars for reference);
(2) inner/outer length ratio and misalignment-angle distributions; (3) Ω_in/Ω_out vs length ratio, with the decoupling threshold; (4) agreement with Zana+22: confusion table and our bar length vs their R_Φ;
(5) threshold scan (fraction of double candidates vs `a2_threshold`, as the legacy script did). `plots/` is empty (README only).

**Metrics (the future `metrics.json`; per galaxy, in the classification parquet):**

| name | definition | code |
|---|---|---|
| `A2(R)`, `phi2(R)` | m=2 amplitude over A₀ and phase [rad], log bins 0.25 kpc … 4 r_half, bootstrap errors | `fourier.fourier_profile` |
| `omega(R)`, `omega_err` | pattern speed [km/s/kpc] from one snapshot, eq. 10 / A4b of Dehnen+23, Gaussian window | `patternspeed.omega_profile` |
| `outer_/inner_r_start, r_end, a2_peak, phi2_deg, omega, omega_err` | segments where A₂ > threshold and φ₂ varies < 10° | `classify.find_segments`, `segment_properties` |
| `length_ratio` | inner end / outer end | `classify.classify_profiles` |
| `misalignment_deg`, `phase_offset_sigma` | φ₂ inner − outer, wrapped to (−90°, 90°], and its significance | same |
| `inner_len_soft`, `inner_marginal` | inner end in softening lengths; < 3 flagged | same |
| `domega_sigma` | \|Ω_in − Ω_out\| over its error | same |
| `ellipse_outer/inner/agrees` | isophote runs (ε ≥ 0.2, PA constant within 10°) matching each Fourier bar | `ellipse.ellipse_bars`, `classify._ellipse_match` |
| `zana_*` | Zana+22 flags and sizes (R_Φ, R_peak, A₂max, k_rot, …) | `io/supplementary.read_zana_bars` |

---------------------------------------------------------------------------------------------------------------------------------------------------

## Q4 Architecture map

```
~/bars (cluster, read-only)           TNG API (the user, login node)
  group catalogs, offsets, npz          scripts/fetch_cutouts.py ──► ~/astro/data/bars/stars_snap<S>/*.npz
        │                                       │
        ▼                                       ▼
 00_check_data ─► checks/*.json         io/particles.npz_dirs (cutouts first, then legacy)
 01_catalog_table ─► catalog/*.parquet ──► make_tasks.py ─► task file (--sids lists, longest first)
                                                │   astro campaign (submit_python_tasks.slurm, 20 tasks/node)
                                                ▼
                       02_galaxy_diagnostics ─► profiles/*.h5 + logs/*.log      (stop file, skip finished, atomic)
                                                ▼
                       03_classify (+ Zana+22) ─► classification_snap<S>.parquet     (thresholds re-tunable with --set)
                                                ▼
                       04_plot_candidates ─► figures/*.png + index.html
```

| component | status | tests |
|---|---|---|
| `config.py` (YAML include, `${ENV}`, overrides, output root, stop-file path) | done | `test_config.py` 8 |
| `io/catalogs.py`, `io/particles.py`, `io/supplementary.py`, `sample.py` | done; layout/units from memory of TNG docs, partly confirmed by step 00 | `test_readers.py` 7, `test_supplementary.py` 1 |
| `io/cutouts.py` + `scripts/fetch_cutouts.py` | done; format confirmed on the first 2 real cutouts; 17 of 213 snap-98 downloads failed once, retry pending | `test_cutouts.py` 4 (fake downloads) |
| `frames.py`, `fourier.py`, `patternspeed.py`, `ellipse.py`, `maps.py` | done, on synthetic and 5 real galaxies | `test_physics.py` 11 |
| `classify.py`, `analysis.py` | done; thresholds untuned | `test_classify.py` 9 |
| `synthetic.py` | done | used by all |
| `runio.py`, `io/profiles.py`, scripts 00–04, `make_tasks.py` | done; run end to end on synthetic data | `test_scripts.py` 4 (smoke ≈ 3 min wall at laptop load 35–50, not the < 1 min of the brief) |
| `plotting.py` (3×3 figure) | done; checked by eye on 5 real galaxies | smoke test only |
| shared tooling: `bars.sh` row hook, env file, fetch rule | committed on `core-fixes-yield-archive`; not exercised on the cluster | `tests/row_bars.sh` 19/19 and `test_fetch_rules.sh` there [verified, laptop] |
| `write_view.py`, `metrics.json` | **not written** | — |
| result figures (`plots/`) | **not written** | — |

44 tests in 7 files [verified: `pytest --collect-only`; 44 passed on the laptop on 2026-10-19].

---------------------------------------------------------------------------------------------------------------------------------------------------

## Q5 Pause/resume

**What exists** (step 02 only; all verified by tests on the laptop, none yet by a cluster stop/kill):
- **Stop file between galaxies:** `runio.stop_requested` checks `<root>/output/stop` and `$ASTRO_RUNDIR/output/stop` before each galaxy (one `stat`), logs `status=stop`, ends with `done N/M failed K stopped`, exit 0.
  The file is **not deleted** (20 tasks per job must all stop); one older than the job's `start=` line in STATUS (the last one) is stale and ignored, so a resume needs no cleaning.
- **Skipping finished work:** a galaxy with a profile file is skipped (`status=skip`) unless `--overwrite`.
- **Atomic writes:** profiles (tmp name with the PID, fsync, `os.replace`), parquet tables, figures, `index.html`, cutout npz, checks json.
- **A failed galaxy** is logged and skipped, never fatal.
- **Resume path today:** a new `astro submit ... --env DBARS_OUT=<old run dir>` writes into the old directory (a resume job cannot reuse a run name); it leaves `OUTPUT_ROOT` there for the row hook. `README` §6 has the commands.
- **Test:** `test_stop_and_resume`: stop during the first galaxy, a rerun in the same job stays stopped, a later job resumes, and the profile arrays and maps are **bitwise equal** to an uninterrupted run; no `.tmp` left [verified].

**What is missing**
1. **The restartable flag is inert.** `make_tasks.py` writes `# ASTRO_RESTARTABLE=1` into the *task file*, but `astro` reads the header from the `--script` file, i.e. the shared template [verified: `astro` line 169 and RESTARTABLE.md]. Fix without touching the template: `--restartable` on the campaign lines (or `--env ASTRO_RESTARTABLE=1`). Effort 15 min; to be done only after the cluster test below, as README §6 already says.
2. **Cluster stop/kill test (RESTARTABLE.md rule 5)** never run. Commands are in `cluster/README.md` §6 (reference run, cut run, `astro stop`, resume, comparison script printing `same N/N`). Needs the 20-galaxy job first.
3. **Kill test:** a SIGKILL leaves a hidden `.sub_<SID>.h5.tmp<pid>`; correct (never renamed) but never cleaned, and not tested. Effort ≈ 2 h on the laptop: a subprocess killed at a random moment, then a rerun compared with a reference, plus a cleanup of stale `.*.tmp*` files at task start.
4. **Granularity:** a task stops only after the galaxy in hand. The cost of one galaxy on the cluster is unmeasured; the 5 real laptop galaxies took ~30 s CPU, the 5·10⁶-star ones may take 10 min or more [memory: extrapolation, not measured]. Add ~20 s NFS latency (RESTARTABLE.md §5).
5. **`astro resume` for `--script` runs** does not exist (plan §4.2 proposes it). When core adds "resubmit into the same run directory with `ASTRO_RESUME=1`", bars needs nothing more: STATUS gets a new `start=`, so the stale-stop logic holds, and the same task file skips finished galaxies. `DBARS_OUT` then becomes unnecessary.
6. No yield loop (`astro yield-tick`) in the script; irrelevant until `--nice` is used.

**How to test a stop/kill:** laptop (done for the stop file; kill test to write, 2 h) and cluster (README §6, once the dry run has passed).

---------------------------------------------------------------------------------------------------------------------------------------------------

## Q6 What I need from the user now, and what I want from the cockpit

**Needs (commands, in this order):**
1. Tell me the state of the cluster since 2026-10-19: result of the dry run `diag99_t20` (the paste list at the end of `cluster/README.md` §4, which also gives memory per task and time per galaxy) and of the cutout retry.
   `cd ~/astro/clap/bars && git pull` first (the clone must have `e89f65c` and this commit).
2. Retry the 17 failed cutouts (login node, tmux, key from the environment):
   `grep 'status=fail' ~/astro/data/bars/stars_snap98/fetch_snap98.log | sed 's/.*reason=//' | sort | uniq -c`, then
   `$PY scripts/fetch_cutouts.py --config config/cluster.yaml --snap 98 --workers 2 --timeout 1200`, then `$PY scripts/01_catalog_table.py --config config/cluster.yaml --snap 98` (expect "878 with npz").
3. Clone astroplot on the cluster, and check it (command in Q1), if the figures of step 04 are wanted there; otherwise run step 04 on the laptop on fetched profiles.
4. After the dry run: `astro campaign cluster/campaigns/diag_snap99.campaign` (I fill `--mem`, `--time` first).

**Decisions:**
- Run the cluster stop/kill test (README §6) after the dry run, then mark the campaigns `--restartable`?
- Which snapshots to extract next? Snapshot 98 has 213 + 663 galaxies still without `ParticleIDs` (`--all`); 97–94 have group catalogs but no stars; 93–91 have neither. Needed only for time evolution (milestone 6); merger trees are not needed for 99/98 [from the earlier discussion].
- Approve the three LESSONS entries (Q1), and the campaign header additions (`#expect #view #by #next #nice`) with the draft view above.
- The legacy `~/bars/node_worker_stars.py` and the laptop copy contain a TNG API key in plain text: consider renewing the key.

**From the cockpit:**
- the three-state check table with numbers and the reference column;
- a **contact-sheet / candidate review** kind: the `index.html` table plus the 3×3 PNG per galaxy, where the user can mark a galaxy "confirmed double / rejected / unsure" (that curated list is the input of milestone 7 and of the threshold tuning);
- an explorer kind for the profile `.h5` (A₂, φ₂, Ω_p, ε, PA vs R, with the detected segments) and for the maps;
- a "fetch results" button that only shows the rsync line (profiles and figures are included by the proposed `bars` fetch rule);
- the Zana+22 comparison as a standard table (confusion matrix per run);
- a download view for `fetch_cutouts.py` (galaxies done, failed, GB), and a reminder that a retry is pending.
