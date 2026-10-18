"""Configuration: YAML loading with ``include``, ``${ENV}`` expansion, overrides, output root.

A config file may start with ``include: other.yaml`` (path relative to the including file);
the included file is loaded first and the including file is deep-merged over it.
String values have ``${VAR}``, ``${VAR:-default}`` and a leading ``~`` expanded after merging.

The output root is resolved in this order (brief, "Configuration"):
1. an explicit ``out`` argument (the scripts' ``--out``);
2. ``$ASTRO_RUNDIR`` (set by ``astro submit`` inside a cluster job);
3. ``paths.outputs`` from the config.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

# Planck 2015 cosmology used by IllustrisTNG (Nelson et al. 2019, TNG data release).
OMEGA_M = 0.3089
OMEGA_L = 0.6911
H_TNG = 0.6774

REQUIRED = {
    "sim": ["h", "softening_phys_kpc", "softening_comov_kpc"],
    "selection": ["mstar_min", "mstar_max", "centrals_only"],
    "analysis": [
        "shrink_sphere_final_kpc", "j_radius_rhalf", "rmin_kpc", "rmax_rhalf", "n_rbins",
        "min_particles_per_bin", "n_bootstrap", "a2_threshold", "phase_tol_deg", "map_pixel_kpc",
    ],
}

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ConfigError(ValueError):
    """Raised for a missing key, an unset environment variable or a bad override."""


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _expand_str(s: str) -> str:
    def repl(m: re.Match) -> str:
        name, default = m.group(1), m.group(2)
        if name in os.environ:
            return os.environ[name]
        if default is not None:
            return default
        raise ConfigError(f"environment variable ${{{name}}} is not set (no default given)")

    s = _ENV_RE.sub(repl, s)
    if s.startswith("~"):
        s = os.path.expanduser(s)
    return s


def _expand(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    if isinstance(obj, str):
        return _expand_str(obj)
    return obj


def _load_raw(path: Path, seen: tuple[Path, ...] = ()) -> dict:
    path = path.resolve()
    if path in seen:
        raise ConfigError(f"include cycle: {' -> '.join(map(str, seen + (path,)))}")
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    inc = data.pop("include", None)
    if inc is None:
        return data
    incs = [inc] if isinstance(inc, str) else list(inc)
    base: dict = {}
    for i in incs:
        base = _deep_merge(base, _load_raw(path.parent / i, seen + (path,)))
    return _deep_merge(base, data)


def apply_overrides(cfg: dict, overrides: Iterable[str]) -> dict:
    """Apply ``key.sub=value`` overrides (value parsed as YAML, so numbers/lists work)."""
    cfg = copy.deepcopy(cfg)
    for item in overrides or ():
        if "=" not in item:
            raise ConfigError(f"override {item!r} is not of the form key.sub=value")
        key, val = item.split("=", 1)
        parts = key.strip().split(".")
        node = cfg
        for p in parts[:-1]:
            node = node.setdefault(p, {})
            if not isinstance(node, dict):
                raise ConfigError(f"override {item!r}: {p} is not a section")
        node[parts[-1]] = yaml.safe_load(val)
    return cfg


def validate(cfg: dict) -> None:
    for sec, keys in REQUIRED.items():
        if sec not in cfg:
            raise ConfigError(f"config has no section '{sec}'")
        for k in keys:
            if k not in cfg[sec]:
                raise ConfigError(f"config is missing '{sec}.{k}'")
    sel = cfg["selection"]
    if not float(sel["mstar_min"]) < float(sel["mstar_max"]):
        raise ConfigError("selection.mstar_min must be < selection.mstar_max")
    if int(cfg["analysis"]["n_rbins"]) < 2:
        raise ConfigError("analysis.n_rbins must be >= 2")


def load_config(path: str | os.PathLike, overrides: Iterable[str] = ()) -> dict:
    """Load, merge includes, apply overrides, expand ``${ENV}``/``~``, validate.

    The returned dict has an extra key ``_source`` (absolute path of the top file).
    """
    path = Path(path)
    cfg = _load_raw(path)
    cfg = apply_overrides(cfg, overrides)
    cfg = _expand(cfg)
    validate(cfg)
    # YAML may give int or str snapshot keys; normalise stars_npz to int keys.
    npz = cfg.get("paths", {}).get("stars_npz")
    if isinstance(npz, dict):
        cfg["paths"]["stars_npz"] = {int(k): v for k, v in npz.items()}
    cfg["_source"] = str(path.resolve())
    return cfg


def config_hash(cfg: dict) -> str:
    """Short SHA-256 of the analysis-relevant config (paths and private keys excluded)."""
    keep = {k: v for k, v in cfg.items() if k not in ("paths", "run") and not k.startswith("_")}
    blob = json.dumps(keep, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def output_root(cfg: dict, out: str | os.PathLike | None = None) -> Path:
    """Output root: ``out`` > ``$ASTRO_RUNDIR`` > ``paths.outputs``."""
    if out:
        return Path(os.path.expanduser(str(out)))
    rd = os.environ.get("ASTRO_RUNDIR")
    if rd:
        return Path(rd)
    try:
        return Path(cfg["paths"]["outputs"])
    except KeyError as e:
        raise ConfigError("no --out, no $ASTRO_RUNDIR and no paths.outputs in the config") from e


def stop_file(root: Path) -> Path:
    """The stop file of RESTARTABLE.md rule 1: ``<root>/output/stop``."""
    return Path(root) / "output" / "stop"


def softening_kpc(cfg: dict, a: float) -> float:
    """Stellar softening in physical kpc at scale factor ``a``.

    TNG50-1: 0.288 physical kpc for z <= 1, 0.575 comoving kpc for z > 1 (i.e. 0.575 a physical).
    """
    z = 1.0 / a - 1.0
    s = cfg["sim"]
    if z <= 1.0:
        return float(s["softening_phys_kpc"])
    return float(s["softening_comov_kpc"]) * a
