# bars: status (updated 2026-10-30)
<!-- Rewrite at the end of every working session; under 60 lines; history goes to DECISIONS.md. Format: ~/astro/docs/cockpit/FORMATS.md §5 -->

## Doing now
- 2026-11-09: `diag99` (step 02, snap 99, ~870 galaxies, `--mem 64 --time 04:00:00`) submitted by the user; nothing of mine is running.
- 2026-11-09: dry run `diag99_t20` read: 20/20 ok, 2.0-2.7 min and <= 3.4 GB per galaxy, 370 kB per profile. Snap-98 cutouts complete (878/878 with npz).

## Waiting on the user
- 2026-11-09: when `diag99` is done, steps 03 and 04 (step 04 needs astroplot on the cluster):
  ```bash
  R=~/astro/runs/bars/diag99
  nice -n 10 $PY scripts/03_classify.py --config config/cluster.yaml --snap 99 --out $R --table ~/astro/runs/bars/manual/catalog/snap99.parquet
  nice -n 10 $PY scripts/04_plot_candidates.py --config config/cluster.yaml --snap 99 --out $R
  astro fetch diag99
  ```
- 2026-11-09: optional, snapshot 98 campaign (`make_tasks --snap 98`, then `astro campaign cluster/campaigns/diag_snap98.campaign`, commands in `cluster/README.md` §5).
- 2026-11-09: on hold by the user: cluster stop/kill test (`cluster/README.md` §6); until it passes no `--restartable`.
- 2026-11-09: renew the TNG API key (it was pasted into a chat).

## Blocked by
- cluster: results of the dry run (since 2026-10-19); astroplot is not cloned there (step 04 needs it).
- `core-fixes-round1` not merged: `# ASTRO_RESTARTABLE=1` in the task file is written by `make_tasks.py` but inert for now.

## For other projects
- cockpit (astro-43): FORMATS.md fits; one proposal: a fixed `estimates.counts` key set is fine for bars, but `checks` for "agreement with Zana+22" can only be filled after step 03, so the step-02 writer omits it (it cannot know it).
