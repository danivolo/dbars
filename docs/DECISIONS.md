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
  h5py 3.16.0, pandas 3.0.6, pyarrow 26.0.0, pyyaml 6.0.3, matplotlib 3.11.2, astropy 8.0.2, photutils 3.1.1, pytest 9.1.1.

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
