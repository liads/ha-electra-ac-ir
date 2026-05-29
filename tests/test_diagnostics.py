"""Tests for diagnostics redaction."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

import pytest

from .common import clear_integration_modules, install_homeassistant_stubs


@pytest.fixture
def diagnostics(monkeypatch):
    """Import diagnostics with Home Assistant stubs."""
    install_homeassistant_stubs(monkeypatch)
    clear_integration_modules(monkeypatch)
    return importlib.import_module("custom_components.electra_ac_ir.diagnostics")


def test_diagnostics_redacts_personal_config_data(diagnostics) -> None:
    """Diagnostics keep structure while redacting configured names and entities."""
    entry = SimpleNamespace(
        entry_id="entry-id",
        title="Living Room",
        data={
            "name": "Living Room",
            "infrared_entity_id": "infrared.remote",
            "temperature_sensor": "sensor.living_room_temperature",
            "humidity_sensor": "sensor.living_room_humidity",
            "power_sensor": "binary_sensor.living_room_power",
            "entity_unique_id": "stable-id",
        },
    )

    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, entry))

    assert result == {
        "entry": {
            "entry_id": "entry-id",
            "title": "**REDACTED**",
            "data": {
                "name": "**REDACTED**",
                "infrared_entity_id": "**REDACTED**",
                "temperature_sensor": "**REDACTED**",
                "humidity_sensor": "**REDACTED**",
                "power_sensor": "**REDACTED**",
                "entity_unique_id": "**REDACTED**",
            },
        }
    }
