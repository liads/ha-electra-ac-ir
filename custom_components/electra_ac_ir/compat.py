"""Compatibility helpers for infrared-protocols APIs."""

from __future__ import annotations

from typing import Any


def _load_infrared_command() -> type[Any]:
    """Return the infrared-protocols command base class."""
    try:
        from infrared_protocols import Command
    except ImportError:
        from infrared_protocols.commands import Command

    return Command


InfraredCommand = _load_infrared_command()
