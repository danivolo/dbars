# bars (tng50-doublebars, package `dbars`) — rules for Claude sessions

Full brief: `~/astro/docs/bars.md` (read it once). The `~/astro/CLAUDE.md` rules apply on top of this file.

## What
Find candidate double-barred and control single-barred galaxies in TNG50-1 from already-extracted star particles (npz, one per galaxy,
M★ > 1e10) and catalogs on the cluster under `~/bars` (**read-only**). Goal: a curated mock-data sample for double-bar theory tests.

## Where
| | laptop | cluster (user runs everything; the chat cannot reach it) |
|---|---|---|
| repo | `~/astro/clap/bars` (branch `main`) | clone at `~/astro/clap/bars` |
| env | `~/astro/envs/bars` (uv venv; see README) | `~/astro/envs/bars` (`astro pyenv`, once `envs/bars.yml` is merged) |
| scratch | `~/astro/scratch/bars/` (never `/tmp`) | same |
| outputs | `~/astro/runs/bars/<run>/` (from `astro fetch`) | `$ASTRO_RUNDIR` inside jobs |
| result figures | `~/astro/plots/bars/` via `astroplot.save` | — |
| papers | `paper ... --for bars` | — |

## Rules
1. No simulation data or outputs in the repo; tests use synthetic galaxies (`dbars.synthetic`); real samples in `~/astro/runs/bars/samples/` are for manual checks only.
2. No downloads, no TNG API, no heavy runs on the laptop (shared; check `uptime`, set `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`).
3. No hard-coded paths: everything from `config/*.yaml`. Output root: `--out` > `$ASTRO_RUNDIR` > `paths.outputs`.
4. Units and frame in every docstring (physical kpc, km/s, Msun, km/s/kpc; radians unless said otherwise).
5. Physics = pure functions in `src/dbars/`; scripts do only I/O, looping, logging.
6. Scripts are idempotent and restartable: one file per galaxy written atomically (tmp + rename), skip finished unless `--overwrite`,
   a failed galaxy is logged and skipped, stop cleanly between galaxies if `<root>/output/stop` exists (RESTARTABLE.md rule 1).
   Each task ends with the line `done N/M failed K`.
7. Small commits, `pytest` green before each; never push.
8. Uncertain TNG field/unit/layout → `NOTE:` in code and README, not a silent guess. Mark doc claims [verified]/[memory].
9. Shared tooling (`~/astro/gizmo/scripts/cluster/`: astro, templates, health hooks, env files, fetch rules) is not ours: put proposals in
   `cluster/proposed/`, stop, tell the user.
10. Decisions (especially thresholds) go to `docs/DECISIONS.md`.
11. Papers: `paper find` first; `paper add`/`paper use --for bars --where <file>`; `--verified` only when read in the paper itself.

## Science pitfalls the code must respect
- Double bars give **two** φ₂ plateaus: never require a single constant phase over the bar region.
- An inner m=2 signal can be a nuclear ring/spiral/disc; "decoupled" needs a distinct Ω_p measured from one snapshot (continuity method).
- Inner bars are a few softening lengths (0.288 kpc at z ≤ 1): report inner-bar length in softening units, flag marginal ones.
- npz caveats: wind particles (`a_form <= 0`) to drop; centring good only to ~100 pc (re-centre with a shrinking sphere);
  units converted with a = 1 (wrong for snap ≠ 99 unless corrected); no ParticleIDs.

## Status
See README "Status per milestone" and `cluster/README.md` (the user's next commands). Proposals for the shared tooling (env file, row hook,
fetch rule, astro.conf lines) are in `cluster/proposed/` and wait for the user's decision.

## Working notes
- The laptop is often at load 30-50: time with `time.process_time()`, not wall clock; the full test suite takes 2-6 min wall.
- Ellipse fits dominate the per-galaxy cost (~10 s CPU); unit tests use `do_ellipse=False` except one.
