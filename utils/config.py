"""
Config Loader — Mean Reversion Intraday
========================================
Centralized configuration reader. All modules should import settings
from here instead of hard-coding defaults.

Usage:
    from utils.config import config
    adx_period = config.get("indicators.adx.period", 14)
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class Config:
    """Lightweight wrapper around the YAML config file."""

    def __init__(self, path: str = None):
        path = path or os.getenv("CONFIG_PATH", _CONFIG_PATH)
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"Config file not found: {p.resolve()}\n"
                "Create it from the template or set CONFIG_PATH env var."
            )
        with open(p, "r") as f:
            self._cfg: Dict[str, Any] = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a nested config value using dot notation.

        Examples
        --------
        >>> config.get("indicators.adx.period")
        14
        >>> config.get("indicators.adx.nonexistent", 20)
        20
        """
        keys = key.split(".")
        val = self._cfg
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    @property
    def raw(self) -> Dict[str, Any]:
        """Return the full raw config dict."""
        return self._cfg


# Singleton instance — import this in other modules
config = Config()
