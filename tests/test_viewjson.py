"""view.json writer: parses step-02 logs incrementally and validates against the cockpit schema."""
import json
import subprocess
import sys
from pathlib import Path

from dbars import viewjson

ASTRO = Path.home() / "astro/wt/_scratch/round1/scripts/cluster/lib/viewcheck.py"


def _write(path, rows, mode="a"):
    with open(path, mode) as f:
        for i, (sid, st, lab) in enumerate(rows):
            r = f" reason={lab!r}" if lab else ""
            f.write(f"2026-10-30T10:{i // 60:02d}:{i % 60:02d} sid={sid} status={st} t=30.0s{r}\n")


def test_incremental_and_counts(tmp_path):
    log = tmp_path / "diag_snap99_chunk000of002.log"
    rows = [(i, "ok", "double_candidate" if i % 10 == 0 else "single") for i in range(40)] + [(99, "fail", "ValueError: x")]
    _write(log, rows[:25])
    st = viewjson.new_state()
    assert viewjson.read_new(st, tmp_path, "diag_snap99*.log") == 25
    with open(log, "a") as f:
        f.write("2026-10-30T11:00:00 sid=500 status=ok t=3")          # half-written line is not parsed yet
    assert viewjson.read_new(st, tmp_path, "diag_snap99*.log") == 0
    with open(log, "a") as f:
        f.write("0s\n")                                                # the writer finishes it
    assert viewjson.read_new(st, tmp_path, "diag_snap99*.log") == 1
    _write(log, rows[25:])
    viewjson.read_new(st, tmp_path, "diag_snap99*.log")
    v = viewjson.build(st, 60, 99)
    assert v["estimates"][0]["counts"]["n"] == 41 and v["estimates"][0]["counts"]["double_candidate"] == 4
    assert v["checks"][0]["state"] == "WARN" and 0 < v["stages"][0]["fraction"] < 1
    assert len(json.dumps(v)) < 50_000 and viewjson.read_new(st, tmp_path, "diag_snap99*.log") == 0


def test_retry_replaces_failure_and_thinning(tmp_path):
    log = tmp_path / "diag_snap99_a.log"
    _write(log, [(1, "fail", "E: x"), (1, "ok", "single")] + [(10 + i, "ok", "unbarred") for i in range(1500)])
    st = viewjson.new_state()
    viewjson.read_new(st, tmp_path, "diag_snap99*.log")
    v = viewjson.build(st, 1501, 99)
    assert v["checks"][0]["value"].startswith("0/") and v["stages"][0]["state"] == "done"
    assert all(len(s["points"]) <= 500 for s in v["series"])


def test_script_output_validates(tmp_path):
    import pytest
    if not ASTRO.exists():
        pytest.skip("viewcheck not available")
    log = tmp_path / "logs" / "diag_snap99_a.log"
    log.parent.mkdir()
    _write(log, [(i, "ok", "single") for i in range(30)])
    st = viewjson.new_state()
    viewjson.read_new(st, log.parent, "diag_snap99*.log")
    (tmp_path / "view.json").write_text(json.dumps(viewjson.build(st, 100, 99, run="r"), allow_nan=False))
    r = subprocess.run([sys.executable, str(ASTRO), str(tmp_path / "view.json")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
