"""``view.json`` (schema ``astro.view/1``, ~/astro/docs/cockpit/FORMATS.md §1) from the per-galaxy logs of step 02.

Pure bookkeeping, no physics. The logs are the ``logs/<name>.log`` files of :class:`dbars.runio.GalaxyLog`, lines
``<ISO time> sid=<SID> status=<ok|fail|skip|stop> t=<s>s [reason=<repr>]`` (reason of an ``ok`` line = the label,
of a ``fail`` line = the exception). :class:`LogTail` reads each file from a remembered byte offset, so a call costs
only the new lines; its state is a JSON-able dict (kept between calls in ``<root>/output/view_state.json``).
Units: times in seconds (series in minutes), counts are galaxies.
"""

from __future__ import annotations

import ast
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np

LINE = re.compile(r"^(\S+) sid=(\d+) status=(\w+) t=([\d.]+)s(?: reason=(.*))?$")
DOUBLE = ("double_candidate", "double_decoupled", "double_marginal")
LABELS = ("unbarred", "single", "double_candidate", "double_decoupled", "double_marginal")
MAX_POINTS = 400
NOTE_PROVISIONAL = "labels use untuned thresholds (milestone 5); step 03 relabels from the stored profiles"


def new_state() -> dict:
    return dict(offsets={}, t0=None, sids={}, events=[], trend=[])


def _reason(txt):
    if not txt:
        return ""
    try:
        return str(ast.literal_eval(txt))
    except (ValueError, SyntaxError):
        return txt


def read_new(state: dict, log_dir, pattern: str) -> int:
    """Read the complete new lines of every log matching ``pattern``; update ``state`` in place; returns lines read."""
    n = 0
    for p in sorted(Path(log_dir).glob(pattern)):
        off = state["offsets"].get(p.name, 0)
        if p.stat().st_size < off:           # file replaced: start again
            off = 0
        with open(p, "rb") as f:
            f.seek(off)
            chunk = f.read()
        end = chunk.rfind(b"\n") + 1         # never parse a half-written last line
        state["offsets"][p.name] = off + end
        for raw in chunk[:end].decode(errors="replace").splitlines():
            m = LINE.match(raw.strip())
            if not m:
                continue
            ts, sid, status, secs, reason = m.groups()
            if status == "stop":
                continue
            t = datetime.fromisoformat(ts).timestamp()
            state["t0"] = t if state["t0"] is None else min(state["t0"], t)
            state["sids"][sid] = [status, _reason(reason) if status != "skip" else "", float(secs), t]
            done = sum(1 for v in state["sids"].values() if v[0] in ("ok", "skip"))
            dbl = sum(1 for v in state["sids"].values() if v[0] == "ok" and v[1] in DOUBLE)
            state["events"].append([t - state["t0"], done, dbl, float(secs) if status == "ok" else None])
            n += 1
    # trend of the double fraction: one value per 10 labelled galaxies, last 50
    lab = [v for v in state["sids"].values() if v[0] == "ok"]
    while len(lab) // 10 > state.get("trend_n", 0):
        state["trend_n"] = state.get("trend_n", 0) + 1
        k = 10 * state["trend_n"]
        state["trend"].append(round(sum(v[1] in DOUBLE for v in lab[:k]) / k, 4))
    state["trend"] = state["trend"][-50:]
    return n


def _thin(points, k=MAX_POINTS):
    if len(points) <= k:
        return points
    step = int(np.ceil(len(points) / k))
    out = points[::step]
    return out if out[-1] is points[-1] else out + [points[-1]]


def _state_of(frac_fail: float) -> str:
    return "PASS" if frac_fail < 0.01 else "WARN" if frac_fail <= 0.05 else "FAIL"


def build(state: dict, total: int | None, snap: int, run: str | None = None, final: bool = False,
          now: float | None = None) -> dict:
    """The view dict. ``total``: galaxies the job was asked to do (None if unknown); ``final``: job has ended."""
    now = time.time() if now is None else now
    sids = state["sids"]
    ok = [v for v in sids.values() if v[0] == "ok"]
    n_fail = sum(1 for v in sids.values() if v[0] == "fail")
    n_done = sum(1 for v in sids.values() if v[0] in ("ok", "skip"))
    n_seen = n_done + n_fail
    counts = {k: sum(1 for v in ok if v[1] == k) for k in LABELS}
    counts["n"] = len(ok)
    elapsed = (now - state["t0"]) if state["t0"] else 0.0
    finished = final or (total is not None and n_seen >= total)
    frac = min(1.0, n_seen / total) if total else None
    eta = None
    if total and n_seen and not finished and elapsed > 0:
        eta = (total - n_seen) * elapsed / n_seen
    st = dict(name="02 galaxy diagnostics", state="pending" if not n_seen else "done" if finished else "running",
              fraction=frac)
    if eta is not None:
        st["eta_s"] = round(eta)
        st["note"] = "ETA from the average rate since the first log line; tasks differ in cost, so it is rough"
    if finished and n_fail and n_done == 0:
        st["state"] = "failed"
    tot_txt = f" of {total}" if total else ""
    now_txt = (f"stage 1 of 1: galaxy diagnostics snap {snap}, {n_done}{tot_txt} galaxies done, {n_fail} failed"
               + ("" if finished else f", {elapsed / 60:.0f} min elapsed") + (" (finished)" if finished else ""))
    ev = state["events"]
    secs = [e[3] for e in ev if e[3] is not None]
    n = len(ev)
    ser = []
    if n:
        ser.append(dict(name="galaxies done", x_label="elapsed [min]", y_label="galaxies",
                        points=_thin([[round(e[0] / 60, 2), e[1]] for e in ev])))
        ser.append(dict(name="double candidates", x_label="galaxies done", y_label="all double_* labels",
                        points=_thin([[e[1], e[2]] for e in ev])))
    if len(secs) >= 5:
        w = 20
        med = [[i + 1, float(np.median(secs[max(0, i - w + 1): i + 1]))] for i in range(len(secs))]
        ser.append(dict(name="seconds per galaxy (rolling median of 20)", x_label="galaxies labelled",
                        y_label="CPU-bound wall time [s]", points=_thin(med)))
    est = []
    if ok:
        p = sum(counts[k] for k in DOUBLE)
        f = p / len(ok)
        est.append(dict(quantity="fraction of galaxies labelled double_*", value=round(f, 4),
                        error=round(float(np.sqrt(f * (1 - f) / len(ok))), 4), unit="", counts=counts,
                        trend=state["trend"], basis="labelled galaxies of this run so far (binomial error)",
                        note="provisional: " + NOTE_PROVISIONAL))
    ff = n_fail / n_seen if n_seen else 0.0
    checks = [dict(name="failed galaxies", state=_state_of(ff) if n_seen else "NOT YET",
                   value=f"{n_fail}/{n_seen} = {100 * ff:.1f} %", target="PASS < 1 %, WARN 1-5 %, FAIL > 5 %",
                   note="failed galaxies are in logs/ with status=fail; understand them before step 03")]
    if len(secs) >= 5:
        checks.append(dict(name="median time per galaxy", state="NOT YET", value=f"{np.median(secs):.0f} s",
                           target="no reference until the dry run diag99_t20 is read",
                           note="wall time of one galaxy with 1 thread"))
    return {"schema": "astro.view/1", "updated": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)), "level": "run",
            **({"run": run} if run else {}), "now": now_txt[:200],
            "question": f"bar diagnostics (Fourier, Omega_p, ellipse fits, maps, first labels) for every snap-{snap} galaxy with an npz",
            "provisional": "labels use untuned thresholds (milestone 5)",
            "stages": [st, dict(name="03 classify (by hand, login node)", state="skipped"),
                       dict(name="04 candidate figures (by hand)", state="skipped")],
            "estimates": est, "checks": checks, "series": ser,
            "notes": ["thresholds are proposals, not yet calibrated", "step 03 may change every label count",
                      "galaxies skipped because their profile already existed count as done but carry no label here"]}
