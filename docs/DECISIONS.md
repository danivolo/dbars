# Decisions (bars / tng50-doublebars)

Format: choice — alternatives — reason — reference. Per-change entries: symptom → root cause → fix → verification → commit.

## D1. Repository layout and branch (2026-10-18)
- Choice: one repo at `~/astro/clap/bars`, branch `main`, package `dbars` under `src/`.
- Alternatives: a `wt/` worktree (GIZMO projects only); a flat package.
- Reason: non-GIZMO projects live outside `wt/` (ALIGN.md §1.1); `src/` layout keeps tests honest (import the installed package).

## D2. Laptop environment with uv until the shared env file exists (2026-10-18)
- Choice: `uv venv --python 3.12 ~/astro/envs/bars` + `uv pip install -e .[test]`, astroplot editable.
- Alternatives: `astro pyenv` (needs `envs/bars.yml` on the shared branch: proposed, not merged); the `gizmo` env (no pip, no h5py/photutils).
- Reason: brief, "Configuration and environment". Versions tested [verified, `uv pip install` output 2026-10-18]: numpy 2.5.4, scipy 1.18.1,
  h5py 3.16.0, pandas 3.0.6, pyarrow 25.0.0 (26.0.0 first; not on conda-forge, D15), pyyaml 6.0.3, matplotlib 3.11.2, astropy 8.0.2, photutils 3.1.1, pytest 9.1.1.

## D3. Config: include + `${VAR:-default}` (2026-10-18)
- Choice: `include:` relative to the including file, deep merge, then `--set` overrides (values parsed as YAML), then `${VAR}`, `${VAR:-default}`, `~` expansion; unset `${VAR}` without default is an error.
- Reason: one command works by hand and in a job; `local_test.yaml` points at `$DBARS_SYNTH_DIR`, which the tests set to a tmp folder.
- `config_hash` covers everything except `paths`, `run` and private keys, so moving data does not invalidate finished profiles.

## D4. Softening (2026-10-18)
- 0.288 physical kpc at z ≤ 1, 0.575 comoving kpc at z > 1 (the two agree at z = 1) [memory: brief; TNG50 paper values, Pillepich et al. 2019 / Nelson et al. 2019, not yet registered in paperlib].

## D5. Pattern speed: Gaussian windows per bin, Dehnen window per bar (2026-10-18)
- Choice: Omega_p(R) with a Gaussian radial window (sigma = 1 log-bin width, `analysis.omega_window_bins`) at every Fourier bin;
  for each detected bar, one value with the smooth window of Dehnen et al. eq. 25 over [r_start, r_end] (`segment_omega`).
  Formula: eq. 10 / A4b of Dehnen, Semczuk & Schönrich (arXiv:2211.00674) for m = 2 [verified: read in the paper, 2026-10-18].
- Alternatives: top-hat annuli (biased 5–25 %, paper Sect. 2.3); finite differences between snapshots (alias at TNG spacing).
- Sign: Omega_p > 0 = rotating with the stars (z along L_star). Test: `test_pattern_speed_sign_convention`.
- Errors: Poisson bootstrap (one weight per particle and resampling, shared by all windows, so neighbouring bins are
  correlated); the paper's linear propagation (eq. A5) is an alternative. The error of a mean over a segment's bins is
  inflated by sqrt(`classify.omega_corr_bins` = 2.5) for that correlation [to check on real galaxies].
- Masking: a bin's Omega_p counts only where the window A2 >= 0.05 and >= 3 sigma.

## D6. Classifier choices (2026-10-18; thresholds to be tuned in milestone 5)
- Segments: greedy outward scan; a segment ends where A2 drops below the threshold or where the phase range would exceed `phase_tol_deg`;
  the next segment may start at that bin. So a phase jump between bars splits them even without an A2 dip.
- Outer bar = the longest segment (linear extent); inner bar = the strongest segment ending inside the outer bar's start.
  First version took the strongest segment as outer: wrong when the inner bar is as strong (synthetic double gave "single").
- Double needs |dphi| > 15 deg and > 3 sigma; decoupled needs |dOmega| > 3 sigma and > 20 % of Omega_out.
- Inner bar length in softenings is always reported; marginal below 3 softenings.

## D7. Ellipse fits on log maps, bars as constant-PA runs (2026-10-18)
- Choice: photutils isophotes on log10 of the face-on map (Gaussian smoothing 2 px = 0.2 kpc, maxgerr = 1, fixed centre);
  a bar = a run of >= 3 isophotes with eps >= 0.2 and PA within 10 deg; it confirms a Fourier bar if it overlaps [0.4, 1.3] x L
  and its PA is within 20 deg of phi_2.
- Alternatives tried on the synthetic double (scratch/bars/dev): linear map with 1 px smoothing — fits stopped (code 4, gradient)
  outside the nuclear disc; local-maximum-of-eps test — missed the inner bar, whose isophotes are most elongated at the centre.
- Cost: ~10 s CPU per galaxy at 1e5 particles (the slowest step); `do_ellipse=False` in the unit tests except one.

## D8. Task lines name their galaxies (2026-10-18)
- Choice: `make_tasks.py` writes `--sids a,b,c --log-name ...` per line (the brief's example used `--chunk 17/45`).
- Reason: a job's `$ASTRO_RUNDIR` is new and has no catalog table, so `--chunk` would need a second path; explicit ids also make
  the committed task file say exactly what ran and let the row hook count galaxies per task. `--chunk i/n --table T` stays for runs by hand.
- Chunks: round-robin from the cost-sorted list (cost = star-particle count), lines sorted by chunk cost, largest first.

## D9. Tests (2026-10-18)
- Synthetic galaxies of 1e5 particles in tests (generator default 2e5) and 30 bootstraps: the laptop is shared (load 40–50 while writing).
- pytest's basetemp is `~/astro/scratch/bars/pytest` (conftest), not /tmp (RAM-backed, LESSONS.md).
- Synthetic model: rigid rotation per bar with v_R = 0 satisfies the continuity equation exactly, so Omega_p tests check the estimator,
  not bar dynamics; a nuclear disc (15 % of the mass, scale 0.4 kpc) gives the inner bar enough particles.

## D10. Scale factor in the npz (open, 2026-10-18)
- Assumed [memory]: the extraction did pos/h and left velocities as stored, i.e. exact values are pos*a and vel*sqrt(a). Switch
  `particles.correct_scale_factor` (default false); the reader warns once per snapshot with a != 1. To decide after reading the legacy
  extraction script; at snap 98 (a ~ 0.99) the effect is ~1 % on lengths and ~0.5 % on Omega_p.

## D11. Stop and resume of a task farm (2026-10-18)
- Choice: every task checks `<root>/output/stop` (and `$ASTRO_RUNDIR/output/stop`) before each galaxy and never deletes it; a stop file older
  than the job's `start=` (STATUS) is stale and ignored. A resume is a new run (`astro submit ... --env DBARS_OUT=<old run dir>`) that
  writes into the old directory and skips its finished galaxies; it leaves `OUTPUT_ROOT` in its own run directory for the row hook.
- Alternatives: delete the stop file when seen (GIZMO's way) — with ~20 tasks per job only the first task would stop; `astro resume` —
  GIZMO runs only (RESTARTABLE.md §2); reusing the run name — refused by `astro submit`.
- Verification: `tests/test_scripts.py::test_stop_and_resume` (laptop; stop during the first galaxy, rerun in the same job still stopped,
  a later job resumes, results identical to an uninterrupted run). On the cluster: `cluster/README.md` §6 [not verified].
- Until §6 has passed on the cluster, the campaigns are not marked restartable (no `--restartable`, no `--nice`).

## D12. Task files are generated on the cluster, outside the clone (2026-10-18)
- Choice: `make_tasks.py --out ~/astro/scratch/bars/tasks/<name>.txt` on the cluster (it needs the step-01 table, which exists only there);
  the campaign lines point there; the user copies them back and they are committed under `cluster/tasks/` as the record of what ran.
- Reason: a file written into the clone makes it dirty, and `astro pull` refuses a dirty tree; the same file arriving later by `git pull`
  would also collide with the untracked copy.

## D13. Row hook and fetch rule proposals (2026-10-18)
- `cluster/proposed/health/bars.sh`: progress = profile files present / galaxies named in the task file (not tasks done: tasks are long,
  ~20 galaxies each); WARN on failed galaxies, BAD on a non-zero task exit or a failed job. [verified: `test_bars_row.sh` with the shared
  `lib.sh` of core-fixes-yield-archive, laptop, no Slurm]
- `cluster/proposed/fetch_rules_bars.txt`: parquet tables, `profiles/***`, `figures/***`, `checks/*.json`, `logs/*.log` and the usual text files.
- `cluster/proposed/envs/bars.yml`: the laptop pins; conda-forge availability of the exact versions not checked.

## D14. Cluster facts from the user, 2026-10-18
- No wall-time limit on the partition: `--time` just covers the job (set from the dry run).
- `~/bars` holds group catalogs 091–099, `snapdir_099`, offsets, and extracted stars for snapshots 91–99; `config/cluster.yaml` lists all
  of them so 00_check_data reports each. With a ≈ 0.9 at snap 91 [memory], the a = 1 extraction issue (D10) is no longer negligible
  for 91–97: decide the correction from the legacy `node_worker_stars.py` before running those snapshots.
- No SubLink merger trees on disk (user, not yet listed by a command). Milestone 6 then needs per-subhalo API downloads (separate
  approval) or a matching without trees; to plan when we get there.
- Supplementary catalogues present: `supplementary_catalogs/{bar_properties,circularities,autogmm_decomp}.hdf5`,
  `extra_data/{kinematic_decomposition_099,morphs_kinematic_bars,stellar_circs}.hdf5`; contents not yet listed. bar_properties may
  allow a comparison with an independent bar sample (and choosing barred/unbarred sample galaxies).
- Shared tooling: env file, row hook, fetch rule committed on `core-fixes-yield-archive` (d0759d1) after the user's OK; tests there:
  row_bars.sh 19/19, test_fetch_rules.sh, test_pyenv.sh, test_row.sh, test_campaign_dirs.sh passed [verified, laptop].

## D15. pyarrow 25.0.0 (2026-10-18)
- Symptom: `astro pyenv create bars` on the cluster: `PackagesNotFoundError: pyarrow=26.0.0` (conda-forge). Root cause: the laptop pins came
  from PyPI (uv), where 26.0.0 exists; conda-forge's latest is 25.0.0 [verified: api.anaconda.org, 2026-10-18; all other pins present there].
- Fix: pin 25.0.0 in envs/bars.yml and on the laptop (`uv pip install pyarrow==25.0.0`). pyarrow only does Parquet I/O, no effect on results.

## D16. Data on the cluster per snapshot (00_check_data, 2026-10-19) [verified: the user's pasted output]
| snap | z | catalog chunks | npz / expected (M* >= 1e10) |
|---|---|---|---|
| 99 | 0.0000 | 680/680 | 901/903 (missing sid 0 and 220595) |
| 98 | 0.0095 | 680/680 | 675/911 (236 missing: extraction incomplete) |
| 97-94 | 0.024-0.059 | 680/680 | 0 (folders exist; naming or content not yet listed) |
| 93-91 | — | chunk 0 missing | 0 |
- sid 0 is the central of the most massive halo, above `mstar_max` in any case [memory]; whether 220595 is in the window: step 01 tells.
- Supplementary: `supplementary_catalogs/{autogmm_decomp,bar_properties}.hdf5` are not HDF5 ("file signature not found": probably failed
  downloads); `circularities.hdf5` / `extra_data/stellar_circs.hdf5` are the TNG circularity catalogue; `extra_data/morphs_kinematic_bars.hdf5`
  is the TNG50 MORDOR kinematic-morphology + bar catalogue (Zana et al. 2022; per snapshot: Barred, BarSize (2,N), BarStrength (2,N),
  SubhaloID ...): an independent bar classification to compare with in milestone 5, once the meaning of the two rows is read in the paper.
- Plan: run snap 99 (complete) first; snap 98 on the 675 extracted galaxies (make_tasks uses only galaxies with an npz), flagged as partial.
