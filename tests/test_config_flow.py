"""Tests for the Electra AC IR config flow."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

import pytest

from .common import (
    EntityRegistry,
    SensorDeviceClass,
    clear_integration_modules,
    install_homeassistant_stubs,
)


@pytest.fixture
def config_flow(monkeypatch):
    """Import the config flow module with Home Assistant stubs."""
    install_homeassistant_stubs(monkeypatch)
    clear_integration_modules(monkeypatch)
    return importlib.import_module("custom_components.electra_ac_ir.config_flow")


def _flow(config_flow, unique_id: str | None = None):
    flow = config_flow.ElectraAcIrConfigFlow()
    flow.hass = SimpleNamespace(entity_registry=EntityRegistry(unique_id, "remote"))
    return flow


def _schema_value(schema, field_name: str):
    for marker, value in schema.schema.items():
        if marker.schema == field_name:
            return value
    raise AssertionError(f"{field_name} was not found in schema")


def test_step_user_aborts_without_emitters(config_flow, monkeypatch) -> None:
    """The flow aborts when no infrared emitters exist."""
    monkeypatch.setattr(config_flow.infrared, "async_get_emitters", lambda hass: [])

    result = asyncio.run(_flow(config_flow).async_step_user())

    assert result == {"type": "abort", "reason": "no_emitters"}


def test_step_user_filters_optional_sensor_selectors(config_flow, monkeypatch) -> None:
    """The form limits optional sensor selectors by device class."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote"],
    )

    result = asyncio.run(_flow(config_flow).async_step_user())
    schema = result["data_schema"]

    emitter = _schema_value(schema, config_flow.CONF_INFRARED_ENTITY_ID)
    temperature = _schema_value(schema, config_flow.CONF_TEMPERATURE_SENSOR)
    humidity = _schema_value(schema, config_flow.CONF_HUMIDITY_SENSOR)

    assert emitter.config == {
        "domain": "infrared",
        "include_entities": ["infrared.remote"],
    }
    assert temperature.config["filter"] == {
        "domain": "sensor",
        "device_class": SensorDeviceClass.TEMPERATURE,
    }
    assert humidity.config["filter"] == {
        "domain": "sensor",
        "device_class": SensorDeviceClass.HUMIDITY,
    }


def test_step_user_creates_entry_with_emitter_unique_id(
    config_flow, monkeypatch
) -> None:
    """The flow stores selected entities and derives a stable unique ID."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote"],
    )

    flow = _flow(config_flow, unique_id="abc123")
    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow.CONF_NAME: " Bedroom AC ",
                config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
                config_flow.CONF_TEMPERATURE_SENSOR: "sensor.bedroom_temperature",
            }
        )
    )

    assert flow.unique_id == "electra_rc3_remote_abc123"
    assert result["type"] == "create_entry"
    assert result["title"] == "Bedroom AC"
    assert result["data"] == {
        config_flow.CONF_NAME: "Bedroom AC",
        config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
        config_flow.CONF_TEMPERATURE_SENSOR: "sensor.bedroom_temperature",
    }


def test_step_user_rejects_empty_name(config_flow, monkeypatch) -> None:
    """The flow redisplays the form when the name is empty."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote"],
    )

    result = asyncio.run(
        _flow(config_flow).async_step_user(
            {
                config_flow.CONF_NAME: " ",
                config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
            }
        )
    )

    assert result["type"] == "form"
    assert result["errors"] == {config_flow.CONF_NAME: "name_required"}
