"""Loading of the study inputs from ``configs/base.yaml``.

Why a file and not constants in code: every assumption of the study must be visible,
sourced and changeable in one place so that sensitivity runs can override a value
without touching a formula.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

__all__ = ["CONFIG_DIR", "get", "load_config"]

# configs/ sits next to src/ in the repository, not inside the package.
CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read a YAML file (default ``configs/base.yaml``) into nested dictionaries."""
    path = Path(path) if path is not None else CONFIG_DIR / "base.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get(cfg: dict[str, Any], dotted: str) -> Any:
    """Fetch ``cfg['a']['b']`` with ``get(cfg, 'a.b')``; a missing key raises ``KeyError``."""
    node: Any = cfg
    for part in dotted.split("."):
        node = node[part]
    return node
