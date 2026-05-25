"""Tests for infrared compatibility helpers."""

from __future__ import annotations

import importlib
import sys
import types


def _clear_compat(monkeypatch) -> None:
    for name in list(sys.modules):
        if name == "custom_components.electra_ac_ir.compat":
            monkeypatch.delitem(sys.modules, name, raising=False)


def test_command_imports_from_legacy_root(monkeypatch) -> None:
    """infrared-protocols 2.x exposes Command from the package root."""

    class LegacyCommand:
        pass

    infrared_protocols = types.ModuleType("infrared_protocols")
    infrared_protocols.Command = LegacyCommand
    monkeypatch.setitem(sys.modules, "infrared_protocols", infrared_protocols)
    _clear_compat(monkeypatch)

    compat = importlib.import_module("custom_components.electra_ac_ir.compat")

    assert compat.InfraredCommand is LegacyCommand


def test_command_imports_from_newer_commands_module(monkeypatch) -> None:
    """Newer infrared-protocols exposes Command from infrared_protocols.commands."""

    class NewCommand:
        pass

    infrared_protocols = types.ModuleType("infrared_protocols")
    commands = types.ModuleType("infrared_protocols.commands")
    commands.Command = NewCommand
    monkeypatch.setitem(sys.modules, "infrared_protocols", infrared_protocols)
    monkeypatch.setitem(sys.modules, "infrared_protocols.commands", commands)
    _clear_compat(monkeypatch)

    compat = importlib.import_module("custom_components.electra_ac_ir.compat")

    assert compat.InfraredCommand is NewCommand
    assert not hasattr(infrared_protocols, "Command")


def test_fallback_does_not_modify_infrared_protocols_root(monkeypatch) -> None:
    """The fallback returns the command class without patching the dependency."""
    infrared_protocols = types.ModuleType("infrared_protocols")
    commands = types.ModuleType("infrared_protocols.commands")
    commands.Command = object
    monkeypatch.setitem(sys.modules, "infrared_protocols", infrared_protocols)
    monkeypatch.setitem(sys.modules, "infrared_protocols.commands", commands)
    _clear_compat(monkeypatch)

    importlib.import_module("custom_components.electra_ac_ir.compat")

    assert not hasattr(infrared_protocols, "Command")
