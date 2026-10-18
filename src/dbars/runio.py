"""Run plumbing shared by the scripts: chunks, stop file, atomic text writes, per-galaxy log lines, provenance.

No physics here. RESTARTABLE.md rule 1: the stop file is ``<root>/output/stop``, checked between galaxies
(one ``stat``); when present the script removes it, finishes the galaxy in hand, and exits 0.
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


def stop_requested(root) -> bool:
    return stop_file(root).exists()


def consume_stop(root) -> None:
    try:
        stop_file(root).unlink()
    except FileNotFoundError:
        pass


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
