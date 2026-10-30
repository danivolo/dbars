# bars: status (updated 2026-10-30)
<!-- Rewrite at the end of every working session; under 60 lines; history goes to DECISIONS.md. Format: ~/astro/docs/cockpit/FORMATS.md §5 -->

## Doing now
- 2026-10-30: cockpit round 2 adopted: `scripts/write_view.py` + `src/dbars/viewjson.py` (logs/*.log -> view.json, byte offsets, atomic), campaign headers, this file, `docs/inbox/`.
- 2026-10-30: milestone 4 (cluster dry run) is on the user's side; nothing of mine is running.

## Waiting on the user
- 2026-10-30: the dry run `diag99_t20`: time per galaxy, `Maximum resident set size` per task, size of the profile files. I set `--mem/--time/NPAR` of `diag_snap99` and `diag_snap98` from them.
- 2026-10-30: retry the 17 failed snapshot-98 cutouts, then check "878 with npz":
  ```bash
  cd ~/astro/clap/bars && git pull
  TNG_API_KEY=... python scripts/fetch_cutouts.py --config config/cluster.yaml --snap 98 --workers 2 --timeout 1200
  python scripts/01_catalog_table.py --config config/cluster.yaml --snap 98
  ```
- 2026-10-30: go for the cluster stop/kill test (`cluster/README.md` §6). Until it passes, campaign lines carry no `--restartable` and no `#restartable:` header (the code is restartable by design, the cluster behaviour is unproven).
- 2026-10-30: view writer as a sidecar on the login node, optional (a run directory of a job is `$ASTRO_RUNDIR`):
  ```bash
  python scripts/write_view.py --config config/cluster.yaml --snap 99 --out <RUNDIR> --interval 120 --max-minutes 600
  ```

## Blocked by
- cluster: results of the dry run (since 2026-10-19); astroplot is not cloned there (step 04 needs it).
- `core-fixes-round1` not merged: `# ASTRO_RESTARTABLE=1` in the task file is written by `make_tasks.py` but inert for now.

## For other projects
- cockpit (astro-43): FORMATS.md fits; one proposal: a fixed `estimates.counts` key set is fine for bars, but `checks` for "agreement with Zana+22" can only be filled after step 03, so the step-02 writer omits it (it cannot know it).
