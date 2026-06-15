"""
ATAM-specific configuration management.

This module reads ``config.ini`` shipped inside the ``atamsim`` package and
exposes the values through a lightweight :class:`ATAMConfig` singleton. It is
**intentionally separate** from TinyTroupe's own ``config_manager`` — we only
read ATAM-specific defaults here and never touch LLM model settings, API keys,
or any other TinyTroupe configuration.
"""

from __future__ import annotations

import configparser
import os
from typing import Any


# Default values used when a key is absent from config.ini or cannot be parsed.
_DEFAULTS: dict[str, Any] = {
    "DEFAULT_STEPS_PER_PHASE": 5,
    "SCENARIO_MAX_PER_STAKEHOLDER": 5,
    "PRIORITIZATION_VOTE_RANGE": 10,
    "ENABLE_GROUNDING_DOCUMENTS": True,
    "CONSOLIDATION_ENABLED": True,
}

# Boolean strings accepted by the parser.
_TRUE_VALUES = {"true", "1", "yes", "on"}
_FALSE_VALUES = {"false", "0", "no", "off"}


def _parse_bool(raw: str, default: bool) -> bool:
    """Parse a string into a boolean, returning *default* on failure."""
    cleaned = raw.strip().lower()
    if cleaned in _TRUE_VALUES:
        return True
    if cleaned in _FALSE_VALUES:
        return False
    return default


class ATAMConfig:
    """Read-only accessor for ATAM-specific configuration values.

    The class loads ``config.ini`` from the package directory at
    instantiation time. A module-level :data:`config` singleton is provided
    for convenience, but tests or advanced users can instantiate their own
    :class:`ATAMConfig` pointing to a custom ini file.
    """

    def __init__(self, config_path: str | None = None) -> None:
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.ini")

        self._config_path = config_path
        self._parser = configparser.ConfigParser()
        # read_file so that the semicolon comments in config.ini are honoured.
        if os.path.exists(config_path):
            self._parser.read(config_path, encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, falling back to *default*.

        Values are converted to their natural Python type (``int`` for
        integers, ``bool`` for booleans, ``str`` otherwise) based on the
        built-in defaults table.
        """
        raw = self._raw_get(key)
        if raw is None:
            # Use the provided default, or the built-in default.
            return default if default is not None else _DEFAULTS.get(key)

        # Decide the expected type from the built-in defaults.
        builtin = _DEFAULTS.get(key)
        if isinstance(builtin, bool):
            return _parse_bool(raw, builtin)
        if isinstance(builtin, int):
            try:
                return int(raw)
            except ValueError:
                return builtin
        return raw

    def get_int(self, key: str, default: int | None = None) -> int:
        """Return *key* as an int."""
        raw = self.get(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default if default is not None else int(_DEFAULTS.get(key, 0))

    def get_bool(self, key: str, default: bool | None = None) -> bool:
        """Return *key* as a bool."""
        raw = self.get(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return _parse_bool(raw, default if default is not None else True)
        return bool(raw)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _raw_get(self, key: str) -> str | None:
        """Return the raw string for *key* from the ``[ATAM]`` section."""
        if self._parser.has_option("ATAM", key):
            return self._parser.get("ATAM", key)
        return None


# Module-level singleton — import this rather than instantiating directly.
config = ATAMConfig()