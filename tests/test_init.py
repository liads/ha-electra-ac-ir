"""Tests for integration setup entry helpers."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

import pytest

from .common import clear_integration_modules, install_homeassistant_stubs


@pytest.fixture
def integration(monkeypatch):
    """Import the integration package with Home Assistant stubs."""
    install_homeassistant_stubs(monkeypatch)
    clear_integration_modules(monkeypatch)
    return importlib.import_module("custom_components.electra_ac_ir")


def test_setup_and_unload_forward_climate_platform(integration) -> None:
    """Config entries are forwarded to the climate platform."""
    calls = []

    async def async_forward_entry_setups(entry, platforms):
        calls.append(("setup", entry, platforms))

    async def async_unload_platforms(entry, platforms):
        calls.append(("unload", entry, platforms))
        return True

    entry = object()
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_forward_entry_setups=async_forward_entry_setups,
            async_unload_platforms=async_unload_platforms,
        )
    )

    assert asyncio.run(integration.async_setup_entry(hass, entry)) is True
    assert asyncio.run(integration.async_unload_entry(hass, entry)) is True
    assert calls == [
        ("setup", entry, integration.PLATFORMS),
        ("unload", entry, integration.PLATFORMS),
    ]
