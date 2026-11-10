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

## D17. Zana et al. (2022) bars as the independent comparison (2026-10-19)
- `extra_data/morphs_kinematic_bars.hdf5` (MORDOR; snap 99: 4091 subhaloes, 770 Barred [verified: user's output]) is merged into
  `classification_snap<S>.parquet` as `zana_*` columns by 03_classify (`paths.zana_bars`). Rows: BarSize = (R_Phi, R_peak) kpc,
  BarStrength = (A2max(R), A2max(<R)) — order as listed on the TNG specifications page, section (t) [verified there; the page does not
  state the index mapping, to check in arXiv:2206.04693]. Their Barred flag includes R_Phi >= 2.8 softenings and kinematic cuts, so it
  is a single-bar classification: agreement is expected for our outer bars, not for inner ones.
- `snapshots: [99, 98]` in cluster.yaml: 97-91 have no npz and 93-91 no catalogues (empty folders).

## D18. Legacy scripts read (2026-10-19): what was kept, what replaced [verified: ~/astro/scratch/bars/legacy, copied from cluster ~/bars]
- Extraction (`node_worker_stars.py`, illustris_python + offsets): pos = Coordinates/h (comoving, no a), vel = raw Velocities (no sqrt(a)),
  mass x 1e10/h, a_form = GFM_StellarFormationTime (wind <= 0 kept), selection SubhaloMassType[4] > 1e10 Msun; periodic wrap around
  SubhaloPos/h, centre = mass-weighted COM of stars within 5 kpc, velocities minus the mass-weighted mean of all stars.
  -> D10 resolved: `particles.correct_scale_factor: true` (pos x a, vel x sqrt(a)); our 00/01 M* cut is the same quantity.
  Galaxies whose particles span star chunks of two batches were skipped by a batch: a likely cause of the missing sids.
- Bar detection (`03_global_bar_population_scan.py`, `02_plot_halo_diagnostics_mp.py`): face-on from L of stars within 5 kpc (fixed radius),
  linear radial bins to 10 kpc, A2/A0 local maxima > 0.2, "double" = two maxima with dphi > 12 deg and a dip < 0.85 x the smaller peak.
  Replaced: shrinking-sphere centre, L within 3 r_half, log bins to 4 r_half with bootstrap errors, phase-plateau segments, single-snapshot
  Omega_p, isophote check, softening units. Kept as ideas: the dip criterion (we split on phase or A2 drop), the threshold scan figure.
- `cross_validate_bars.py`: agreement with Zana+22 `Barred` -> now the zana_* columns of 03_classify.
- Note for the user: the legacy worker contains a TNG API key in plain text (cluster ~/bars and the laptop scratch copy); never committed here.

## D19. Check on 5 real snap-99 galaxies (2026-10-19, laptop) [verified: ~/astro/runs/bars/samples_check, script scratch/bars/dev/samples_check.py]
Picked on the cluster from the step-01 table: 3 Zana+22 barred, 2 unbarred discs (k_rot > 0.6), < 4e5 star particles each.
| sid | N* | r_half [kpc] | centre shift [pc] | label | bar end [kpc] | Omega_p [km/s/kpc] | ellipse |
|---|---|---|---|---|---|---|---|
| 20 | 318k | 3.96 | 107 | single | 5.06 | 13.9 +- 0.6 | agrees |
| 460725 | 232k | 1.79 | 37 | single | 2.04 | 51.2 +- 1.1 | agrees |
| 585517 | 239k | 1.48 | 17 | single | 2.30 | 32.0 +- 0.9 | agrees |
| 313695 | 285k | 5.64 | 181 | unbarred | — | — | — |
| 633437 | 212k | 2.26 | 36 | unbarred | — | — | one PA run 0.2-2.0 kpc |
- Labels match the intended Zana barred/unbarred split [assumed from the pick order; the user's table was not pasted].
- 633437: a weak oval, A2 peak ~0.155 just above the 0.15 threshold over too few bins; the ellipse fit sees it. A borderline case for the
  milestone-5 threshold tuning.
- Re-centring moves the centre by 17-181 pc: the 5 kpc COM of the extraction is indeed too coarse for inner bars (brief).
- ~30 s CPU per galaxy at 2-3e5 particles with 100 bootstraps and the ellipse fit. No wind particles in these five files.
- Figure fixes: m=2 colour scale from the inner half of the map; wider panels so colour-bar labels do not touch the next panel.

## D20. New extraction: star-only API cutouts (2026-10-19)
- Choice: `scripts/fetch_cutouts.py` (user runs it on the login node, in tmux) downloads `.../snapshots/S/subhalos/SID/cutout.hdf5?stars=
  Coordinates,Velocities,Masses,GFM_StellarFormationTime,GFM_Metallicity,ParticleIDs`, converts to physical units (wrap around SubhaloPos,
  x a/h, vel x sqrt(a), mass x 1e10/h), centres like the legacy extraction, and writes `subhalo_<SID>_stars.npz` with `particle_ids`, a, h,
  `units="physical"` atomically to `paths.cutouts` (`~/astro/data/bars/stars_snap{snap}`); finished galaxies are skipped; key from `$TNG_API_KEY`.
- The reader searches `paths.cutouts` first, then the legacy `paths.stars_npz`; a `units="physical"` file is not scale-corrected again.
- Alternatives: whole snapshot chunks (legacy worker: all particle types, most of the volume wasted); writing into `~/bars` (read-only for this
  project by the brief).
- Why ParticleIDs: cross-snapshot matching (milestone 6) by shared star particles instead of merger trees, while only nearby snapshots are used.
- Cutout layout and units are [memory: TNG API docs]; `convert_cutout` fails on a missing field, and the first real download is checked by hand
  (`cluster/README.md` §8). Tests: `tests/test_cutouts.py` (fake cutouts across the box edge, no double correction, resume, preference order).
- 2026-10-19, first real cutouts [verified: user's output]: format as expected (all six fields, a = 0.99057 at snap 98, units physical);
  the two largest missing snap-98 galaxies have ~5e6 stars, 300+ MB at float64 (~63 B/star), 2.5-3.5 min each. Arrays now stored as
  float32 (TNG's own precision), ~40 B/star; the two float64 files stay valid (the reader converts to float64 anyway).

## D21. Cockpit view.json writer (2026-10-30)
- `scripts/write_view.py` + `src/dbars/viewjson.py` build `view.json` (astro.view/1, ~/astro/docs/cockpit/FORMATS.md §1) from `logs/diag_snap<SNAP>*.log`.
- Why a separate sidecar and not a hook inside step 02: 20 tasks write concurrently; one reader of the logs avoids races and cannot slow an analysis task.
  It reads from remembered byte offsets (`<out>/output/view_state.json`), ignores a half-written last line, writes atomically; a retry of a failed galaxy replaces its failure.
- Content: stage + ETA (rough, average rate), the double fraction with binomial error and label counts, failed-fraction check (PASS < 1 %, WARN 1-5 %), series
  (<= 400 points). `provisional` always set: thresholds untuned. Not in it: agreement with Zana+22 (exists only after step 03), task exit codes (the cockpit reads STATUS).
- Alternatives: writer inside `02_galaxy_diagnostics.py` (races, couples I/O to the job); aggregating the profile files (re-reads every file).
- Verification [verified 2026-10-30]: `astro view-check` on the output for a fake run of 60 log lines: valid; `tests/test_viewjson.py` (3 tests).

## D22. Bars must start inside r_half (milestone 5, first tuning on diag99, 2026-11-10)
- Data [verified: diag99, 870 galaxies, step 03 on the fetched profiles]: first classification gave 530 single, 304 unbarred, 25 double_decoupled, 11 double_candidate.
  Of the 36 doubles, 29 had an "outer bar" starting beyond 1.1 r_half (median 2.7 r_half) with Omega_p ~ 1-10 km/s/kpc, and the real bar (Omega_p 15-50) as the "inner" segment: outer-disc spiral or tidal m=2 taken as the outer bar because the outer bar is the longest segment (viewed: sub_184934, a plain single bar at 1-3 kpc plus a spiral at 9-13 kpc, Omega_p 8). 42 of the 'single' labels also had their only segment beyond 1 r_half (single bars start at a median of 0.12 r_half).
- Rule: `classify.bar_start_max_rhalf: 1.0`: segments starting beyond 1.0 r_half are ignored (`classify_profiles(..., r_half=...)`; unit test `test_outer_disc_segment_is_not_a_bar`). Threshold taken from the gap in the distribution of start/r_half among the doubles (0.26-0.59, then 1.17 upwards); not yet tested at 0.75 or 1.5.
- Result: 523 single, 339 unbarred, 4 double_candidate, 4 double_decoupled (0.9 %). Agreement with Zana+22 "Barred" (bar vs unbarred): 73 % (before 71 %); Zana-barred labelled unbarred by us: 60; Zana-unbarred labelled single: 167 (the 'single' class is still generous: next tuning target, A2 peak and bar length).
- Of the 8 remaining, 6 have the inner bar below 3.6 softenings (0.3-1 kpc, the first Fourier bins start at 0.25 kpc): not trustworthy as inner bars without a closer look. Best by eye so far: 501208 (inner 0.35-1.4 kpc, ellipse run agrees, Omega_p 46 vs 35 km/s/kpc, 3.7 sigma).
- Alternatives: require outer Omega_p > some value (rejected: a real slow bar exists; position is the more physical test); require corotation outside the bar end (needs a rotation curve, later).

## D23. Marginal inner bars and Omega_p plateaus (milestone 5, second tuning on diag99, 2026-11-10)
- After D22 the 8 doubles of diag99 were inspected (467415, 501208, 506151, 579509 by figure). Findings: inner bars of 1.9-3.6 softenings are unresolved; "decoupled" fired on smooth Omega_p gradients.
- Rule 1: an inner bar shorter than `inner_marginal_softenings` (3.0) gives the label `double_marginal` (listed, not counted as a double candidate, never decoupled). The flag `inner_marginal` stays.
- Rule 2: `double_decoupled` also needs a plateau of Omega_p in both segments: reduced chi^2 of a constant Omega_p in the segment (bin errors x sqrt(omega_corr_bins)) below `classify.omega_plateau_chi2: 3.0`; columns `inner_omega_chi2`, `outer_omega_chi2`. Value 3.0 is a first guess (the chi^2 over 531 bars has median 0.45, 99th percentile of order 10).
- Result on diag99 [verified: step 03 on the fetched profiles]: 523 single, 339 unbarred, 2 double_candidate (404817, 467415), 2 double_decoupled (501208, 506151), 4 double_marginal (388546, 579509, 625423, 629409). The plateau test is weak: 501208 passes (chi^2 0.8, 1.5) because its bin errors are large; 404817's outer segment fails (chi^2 236) and falls back to candidate.
- Open: 506151 has an outer Omega_p of 2.9 and a tall, narrow xz map: `scripts/05_frame_check.py` (tilt of the spin axis inside 0.5-10 kpc vs. the frame axis, `frames.tilt_profile`) to run on the cluster for the 8 galaxies. A tilted core would make the face-on maps and m=2 profiles of the inner region wrong.
- Synthetic presets: inner bar of the `double` preset lengthened from 0.8 to 1.0 kpc (3.5 softenings) and the outer bar start moved 1.3 -> 1.5 kpc, because 0.8 kpc is itself "marginal" under rule 1; smoke test uses 100k particles (60k gave a 0.47 kpc inner segment).

## D24. Tilted cores are not doubles (2026-11-10)
- `scripts/05_frame_check.py` on the 8 doubles of diag99 [verified: user's output]: the spin axis of the stars inside 0.5-2 kpc is tilted 45-52 deg against the frame axis (set by the stars within 3 r_half) for 506151 (6.8 kpc r_half) and 404817 (15 kpc); the other six: 0.2-5 deg. In the other two the inner region is not seen face-on, so its A2/phi2 profile and Omega_p are not those of a bar.
- Rule: `frame.core_tilt_deg` (tilt inside `analysis.core_tilt_radius_kpc` = 1.0 kpc, stored by step 02) above `classify.core_tilt_max_deg` = 15 turns a double label into `tilted_core` (kept in the table and the contact sheet; counts as no double). Galaxy profiles written before this change have no tilt: step 03 leaves their label alone, so step 02 has to be rerun on diag99 (16 min; `--overwrite`) to apply it.
- Not done: re-analysis of such galaxies in a frame aligned with the inner spin (would be the right treatment for galaxies whose core is genuinely misaligned; later, if the sample needs it).
