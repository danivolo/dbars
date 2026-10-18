#!/usr/bin/env bash
# Health/row hook for project bars (tng50-doublebars): step 02 task farms run through submit_python_tasks.slurm.
# Run directory (astro submit): STATUS, RUNINFO, py_tasks_<job>.out, py_tasks_<job>/{task_NNN.log,exit_NNN,<taskfile>},
# and the outputs profiles/snap<S>/sub_<SID>.h5, logs/<name>.log. A resume job writes into an earlier run directory,
# named in its OUTPUT_ROOT file.
# Row: progress = profile files present / galaxies named in the task file (--sids lists), eta = elapsed*(1-p)/p from
#   STATUS start= (the galaxies are not equal in cost: tasks are dealt so their costs match, the longest first);
#   verdict BAD on a non-zero task exit or FAILED/CANCELLED/TIMEOUT, WARN when galaxies failed (status=fail lines).
# Digest: counts and the label tally of the per-galaxy logs. Read-only, < 1 s for ~1000 galaxies.
# Install: copy to scripts/cluster/health/bars.sh on core-fixes (shared code).
source "$(dirname "$0")/lib.sh"

OUT=$H_RUN; [ -s "$H_RUN/OUTPUT_ROOT" ] && OUT=$(head -1 "$H_RUN/OUTPUT_ROOT")
TF=$(ls -t "$H_RUN"/py_tasks_*/*.txt 2>/dev/null | head -1)
STATE=$(grep -a '^state=' "$H_RUN/STATUS" 2>/dev/null | tail -1 | cut -d= -f2)
START=$(grep -a '^start=' "$H_RUN/STATUS" 2>/dev/null | tail -1 | cut -d= -f2-)
NOW=$(date +%s); EL=; [ -n "$START" ] && EL=$(( NOW - $(date -d "$START" +%s 2>/dev/null || echo "$NOW") ))

# galaxies of the task file as "snap sid", and the profile files present as "snap sid"
TOT=0; DONE=0; NTASK=0
if [ -n "$TF" ]; then
  want=$(awk '!/^[[:space:]]*#/ && NF {s=""; l=""; for(i=1;i<=NF;i++){ if($i=="--snap")s=$(i+1); if($i=="--sids")l=$(i+1) } if(s!=""&&l!=""){n=split(l,a,","); for(k=1;k<=n;k++) print s, a[k]}}' "$TF")
  NTASK=$(grep -cv -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$TF")
  TOT=$(printf '%s\n' "$want" | grep -c .)
  have=$(find "$OUT/profiles" -mindepth 2 -maxdepth 2 -name 'sub_*.h5' 2>/dev/null | awk -F/ '{s=$(NF-1); f=$NF; sub(/^snap/,"",s); sub(/^sub_/,"",f); sub(/\.h5$/,"",f); print s, f}')
  DONE=$(awk 'NR==FNR {h[$0]=1; next} ($0 in h) {c++} END {print c+0}' <(printf '%s\n' "$have") <(printf '%s\n' "$want"))
fi
FAIL=0; FIN=0; for x in "$H_RUN"/py_tasks_*/exit_*; do [ -e "$x" ] || continue; FIN=$((FIN+1)); [ "$(cat "$x")" = 0 ] || FAIL=$((FAIL+1)); done
GFAIL=$(cat "$OUT"/logs/*.log 2>/dev/null | grep -c 'status=fail')
STOPPED=$(cat "$OUT"/logs/*.log 2>/dev/null | grep -c ' stopped$')

if [ "$H_MODE" = row ]; then
  if [ "$TOT" -eq 0 ]; then
    case "$STATE" in RUNNING) h_row_set note "starting, no task file yet";; *) h_row_set note "not started";; esac
    h_row_set verdict OK; h_row_emit; exit 0
  fi
  P=$(awk -v d="$DONE" -v t="$TOT" 'BEGIN{printf "%.4f", (t>0)?d/t:0}')
  h_row_set progress "$P"
  if [ "$STATE" = COMPLETED ]; then h_row_set eta 0s
  elif [ -n "$EL" ] && awk -v p="$P" 'BEGIN{exit !(p>0.002)}'; then h_row_set eta "$(h_row_dur "$(awk -v e="$EL" -v p="$P" 'BEGIN{printf "%d", e*(1-p)/p}')")"; fi
  V=OK; [ "$GFAIL" -gt 0 ] && V=WARN; [ "$FAIL" -gt 0 ] && V=BAD; case "$STATE" in FAILED|CANCELLED|TIMEOUT) V=BAD;; esac
  h_row_set verdict "$V"
  h_row_set m1 "galaxies:$DONE/$TOT"; h_row_set m2 "failed:$GFAIL"; h_row_set m3 "tasks:$FIN/$NTASK"
  N="profiles written / galaxies in the task file"; [ "$STOPPED" -gt 0 ] && N="stopped by stop file ($STOPPED tasks); $N"
  h_row_set note "$N"
  h_row_emit; exit 0
fi

# ---- digest -------------------------------------------------------------------------------------------------------
h_head "bars step 02 (galaxy diagnostics)"
h_status
h_kv "output" "$OUT"
h_kv "galaxies" "$DONE of $TOT with a profile file; $GFAIL failed (status=fail in logs/)"
h_kv "tasks" "$FIN of $NTASK finished, $FAIL non-zero exit, $STOPPED stopped by the stop file"
labels=$(cat "$OUT"/logs/*.log 2>/dev/null | sed -n "s/.*status=ok .*reason='\([a-z_]*\)'.*/\1/p" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
[ -n "$labels" ] && h_kv "labels (02)" "$labels"
slow=$(cat "$OUT"/logs/*.log 2>/dev/null | sed -n 's/.*sid=\([0-9]*\) status=ok t=\([0-9.]*\)s.*/\2 \1/p' | sort -rn | head -3 | awk '{printf "sid %s %ss, ", $2, $1}')
[ -n "$slow" ] && h_kv "slowest" "${slow%, }"
[ "$FAIL" -gt 0 ] && h_bad "$FAIL task(s) exited non-zero (see py_tasks_*/task_NNN.log)"
[ "$GFAIL" -gt 0 ] && h_warn "$GFAIL galaxies failed: grep status=fail $OUT/logs/*.log"
h_verdict
