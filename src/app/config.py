"""
Centralised configuration loader.

Reads ``config.json`` once at import time and exposes the values through
a simple ``cfg`` dict.  Every module that needs a tunable value imports
``cfg`` and does a regular dict lookup — no magic, easy to grep.

Reload at runtime with ``reload_config()`` (e.g. after editing the JSON).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

cfg: Dict[str, Any] = {}


def _load(path: Path = _CONFIG_PATH) -> Dict[str, Any]:
    if not path.exists():
        logger.warning("Config file not found at %s – using empty config", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded config from %s (%d top-level keys)", path, len(data))
    return data


def reload_config(path: str | None = None) -> None:
    """Re-read config.json (useful after editing it without restarting)."""
    target = Path(path) if path else _CONFIG_PATH
    cfg.clear()
    cfg.update(_load(target))


# Auto-load on first import
reload_config()
