#!/usr/bin/env bash
# Laptop test of health/bars.sh on a synthetic run directory (no Slurm needed). Usage: bash test_bars_row.sh HEALTH_DIR
# HEALTH_DIR must hold lib.sh and bars.sh (e.g. scripts/cluster/health on core-fixes). Prints PASS/FAIL lines.
set -u
H=${1:?usage: test_bars_row.sh HEALTH_DIR}; T=$(mktemp -d "${ASTRO_HOME:-$HOME/astro}/scratch/bars_rowtest.XXXX"); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/py_tasks_77" "$T/profiles/snap99" "$T/logs"
printf 'jobid=77\nstart=%s\nstate=RUNNING\n' "$(date -d '-10 min' '+%F %T')" > "$T/STATUS"
printf '# h\npy 02.py --snap 99 --sids 11,12,13 --log-name a\npy 02.py --snap 99 --sids 21,22 --log-name b\n' > "$T/py_tasks_77/t.txt"
touch "$T"/profiles/snap99/sub_{11,12,21,99}.h5; echo 0 > "$T/py_tasks_77/exit_001"
printf "x sid=13 status=fail t=1.0s reason='E'\ndone 2/3 failed 1\n" > "$T/logs/a.log"
ok() { if [ "$2" = "$3" ]; then echo "PASS $1"; else echo "FAIL $1: got '$2' want '$3'"; fi; }
row=$(bash "$H/bars.sh" --row "$T")
ok progress "$(sed -n 's/.*progress=\([^ ]*\).*/\1/p' <<<"$row")" 0.6000
ok galaxies "$(sed -n 's/.*m1=\([^ ]*\).*/\1/p' <<<"$row")" galaxies:3/5
ok verdict_warn "$(sed -n 's/.*verdict=\([^ ]*\).*/\1/p' <<<"$row")" WARN
echo 1 > "$T/py_tasks_77/exit_002"
ok verdict_bad "$(bash "$H/bars.sh" --row "$T" | sed -n 's/.*verdict=\([^ ]*\).*/\1/p')" BAD
mkdir -p "$T/other/profiles/snap99"; touch "$T"/other/profiles/snap99/sub_{11,12,13,21,22}.h5; echo "$T/other" > "$T/OUTPUT_ROOT"
ok output_root "$(bash "$H/bars.sh" --row "$T" | sed -n 's/.*m1=\([^ ]*\).*/\1/p')" galaxies:5/5
