"""Run plumbing shared by the scripts: chunks, stop file, atomic text writes, per-galaxy log lines, provenance.

No physics here. RESTARTABLE.md rule 1: the stop file is ``<root>/output/stop`` (and ``$ASTRO_RUNDIR/output/stop``
when that differs), checked between galaxies (one ``stat`` each). The file is NOT removed: one job runs ~20 tasks
side by side and all of them must stop. A stop file older than the start of the current job (``start=`` in
``$ASTRO_RUNDIR/STATUS``, else this process's start) is stale and ignored, so a resume needs no cleaning.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .config import stop_file


def parse_chunk(spec: str):
    """'i/n' (1-based i) -> (i, n)."""
    i, n = (int(x) for x in spec.split("/"))
    if not 1 <= i <= n:
        raise ValueError(f"bad chunk {spec!r}: need 1 <= i <= n")
    return i, n


def chunk_sids(sids_by_cost, i: int, n: int):
    """Chunk i (1-based) of n: sids are dealt round-robin from the cost-sorted list (most expensive first), so
    chunks have similar cost and chunk 1 is the most expensive."""
    return list(sids_by_cost)[i - 1::n]


_T_PROC = time.time()


def job_start_time() -> float:
    """Start of the current job [unix s]: last ``start=`` of $ASTRO_RUNDIR/STATUS, else this process's start."""
    rd = os.environ.get("ASTRO_RUNDIR")
    if rd:
        try:
            starts = [ln.split("=", 1)[1].strip() for ln in open(Path(rd) / "STATUS") if ln.startswith("start=")]
            if starts:
                return time.mktime(time.strptime(starts[-1], "%Y-%m-%d %H:%M:%S"))
        except (OSError, ValueError):
            pass
    return _T_PROC


def stop_files(root):
    files = [stop_file(root)]
    rd = os.environ.get("ASTRO_RUNDIR")
    if rd and Path(rd).resolve() != Path(root).resolve():
        files.append(stop_file(rd))
    return files


def stop_requested(root, since: float | None = None) -> bool:
    """True if a stop file not older than ``since`` (default: :func:`job_start_time`) exists."""
    t0 = job_start_time() if since is None else since
    for f in stop_files(root):
        try:
            if f.stat().st_mtime >= t0 - 1.0:
                return True
        except FileNotFoundError:
            pass
    return False


def atomic_write_text(path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def git_commit(repo=None) -> str:
    """``git describe --always --dirty`` of the code checkout (``$WORKDIR`` or this package's repo), or 'unknown'."""
    repo = repo or os.environ.get("WORKDIR") or Path(__file__).resolve().parents[2]
    try:
        return subprocess.run(["git", "-C", str(repo), "describe", "--always", "--dirty"], capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class GalaxyLog:
    """Append one line per galaxy to ``<root>/logs/<name>.log``: ``sid status seconds [reason]``."""

    def __init__(self, root, name: str):
        self.path = Path(root) / "logs" / f"{name}.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def line(self, sid, status: str, seconds: float, reason: str = "") -> str:
        s = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} sid={sid} status={status} t={seconds:.1f}s"
        if reason:
            s += f" reason={reason!r}"
        with open(self.path, "a") as f:
            f.write(s + "\n")
        return s
