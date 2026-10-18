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
