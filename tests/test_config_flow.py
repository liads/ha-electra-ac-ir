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


def _schema_marker(schema, field_name: str):
    for marker in schema.schema:
        if marker.schema == field_name:
            return marker
    raise AssertionError(f"{field_name} was not found in schema")


def _schema_value(schema, field_name: str):
    for marker, value in schema.schema.items():
        if marker.schema == field_name:
            return value
    raise AssertionError(f"{field_name} was not found in schema")


def _configure_entry_manager(flow, entries=None):
    scheduled_reloads = []

    def async_entry_for_domain_unique_id(domain, unique_id):
        for entry in entries or []:
            if entry.unique_id == unique_id:
                return entry
        return None

    def async_entries(domain):
        return entries or []

    def async_schedule_reload(entry_id):
        scheduled_reloads.append(entry_id)

    flow.hass.config_entries = SimpleNamespace(
        async_entry_for_domain_unique_id=async_entry_for_domain_unique_id,
        async_entries=async_entries,
        async_schedule_reload=async_schedule_reload,
    )
    return scheduled_reloads


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

    assert flow.unique_id.startswith("electra_rc3_")
    assert result["type"] == "create_entry"
    assert result["title"] == "Bedroom AC"
    data = dict(result["data"])
    entity_unique_id = data.pop(config_flow.CONF_ENTITY_UNIQUE_ID)
    assert entity_unique_id == flow.unique_id
    assert data == {
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


def test_step_user_rejects_duplicate_transmitter(
    config_flow, monkeypatch
) -> None:
    """The setup flow rejects a transmitter already used by another entry."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote"],
    )

    duplicate_entry = SimpleNamespace(
        entry_id="other-entry",
        unique_id="other-entry-id",
        data={config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote"},
    )
    flow = _flow(config_flow)
    _configure_entry_manager(flow, entries=[duplicate_entry])

    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow.CONF_NAME: "Bedroom AC",
                config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
            }
        )
    )

    assert result["type"] == "form"
    assert result["errors"] == {
        config_flow.CONF_INFRARED_ENTITY_ID: "already_configured"
    }


def test_step_reconfigure_prefills_current_config(
    config_flow, monkeypatch
) -> None:
    """The reconfigure form defaults to the current entry data."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote", "infrared.bedroom"],
    )

    flow = _flow(config_flow)
    flow.reconfigure_entry = SimpleNamespace(
        entry_id="entry-id",
        unique_id="electra_rc3_remote_old",
        title="Bedroom AC",
        data={
            config_flow.CONF_NAME: "Bedroom AC",
            config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
            config_flow.CONF_TEMPERATURE_SENSOR: "sensor.bedroom_temperature",
        },
    )

    result = asyncio.run(flow.async_step_reconfigure())
    schema = result["data_schema"]

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert _schema_marker(schema, config_flow.CONF_NAME).default == "Bedroom AC"
    assert (
        _schema_marker(schema, config_flow.CONF_INFRARED_ENTITY_ID).default
        == "infrared.remote"
    )
    assert (
        _schema_marker(schema, config_flow.CONF_TEMPERATURE_SENSOR).description
        == {"suggested_value": "sensor.bedroom_temperature"}
    )
    assert (
        _schema_marker(schema, config_flow.CONF_TEMPERATURE_SENSOR).default
        is None
    )


def test_step_reconfigure_can_clear_optional_sensors(
    config_flow, monkeypatch
) -> None:
    """Reconfigure removes optional sensors that are omitted from form input."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote"],
    )

    flow = _flow(config_flow)
    scheduled_reloads = _configure_entry_manager(flow)
    flow.reconfigure_entry = SimpleNamespace(
        entry_id="entry-id",
        unique_id="stable-entry-id",
        title="Old AC",
        data={
            config_flow.CONF_NAME: "Old AC",
            config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
            config_flow.CONF_TEMPERATURE_SENSOR: "sensor.old_temperature",
            config_flow.CONF_HUMIDITY_SENSOR: "sensor.old_humidity",
            config_flow.CONF_POWER_SENSOR: "binary_sensor.old_power",
        },
    )

    result = asyncio.run(
        flow.async_step_reconfigure(
            {
                config_flow.CONF_NAME: "Bedroom AC",
                config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
            }
        )
    )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    assert flow.unique_id == "stable-entry-id"
    assert flow.unique_id_mismatch_checked is True
    assert flow.reconfigure_entry.data == {
        config_flow.CONF_NAME: "Bedroom AC",
        config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
        config_flow.CONF_ENTITY_UNIQUE_ID: "stable-entry-id",
    }
    assert scheduled_reloads == ["entry-id"]


def test_step_reconfigure_updates_entry_and_reloads(
    config_flow, monkeypatch
) -> None:
    """Reconfigure updates the existing entry and schedules a reload."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote", "infrared.bedroom"],
    )

    flow = _flow(config_flow, unique_id="new123")
    scheduled_reloads = _configure_entry_manager(flow)
    flow.reconfigure_entry = SimpleNamespace(
        entry_id="entry-id",
        unique_id="electra_rc3_remote_old",
        title="Old AC",
        data={
            config_flow.CONF_NAME: "Old AC",
            config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
            config_flow.CONF_TEMPERATURE_SENSOR: "sensor.old_temperature",
        },
    )

    result = asyncio.run(
        flow.async_step_reconfigure(
            {
                config_flow.CONF_NAME: " Bedroom AC ",
                config_flow.CONF_INFRARED_ENTITY_ID: "infrared.bedroom",
                config_flow.CONF_HUMIDITY_SENSOR: "sensor.bedroom_humidity",
            }
        )
    )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    assert flow.unique_id == "electra_rc3_remote_old"
    assert flow.unique_id_mismatch_checked is True
    assert flow.reconfigure_entry.unique_id == "electra_rc3_remote_old"
    assert flow.reconfigure_entry.title == "Bedroom AC"
    assert flow.reconfigure_entry.data == {
        config_flow.CONF_NAME: "Bedroom AC",
        config_flow.CONF_INFRARED_ENTITY_ID: "infrared.bedroom",
        config_flow.CONF_HUMIDITY_SENSOR: "sensor.bedroom_humidity",
        config_flow.CONF_ENTITY_UNIQUE_ID: "electra_rc3_remote_old",
    }
    assert scheduled_reloads == ["entry-id"]


def test_step_reconfigure_rejects_duplicate_transmitter(
    config_flow, monkeypatch
) -> None:
    """Reconfigure does not allow selecting another entry's transmitter."""
    monkeypatch.setattr(
        config_flow.infrared,
        "async_get_emitters",
        lambda hass: ["infrared.remote", "infrared.bedroom"],
    )

    duplicate_entry = SimpleNamespace(
        entry_id="other-entry",
        unique_id="other-entry-id",
        data={config_flow.CONF_INFRARED_ENTITY_ID: "infrared.bedroom"},
    )
    flow = _flow(config_flow, unique_id="new123")
    _configure_entry_manager(flow, entries=[duplicate_entry])
    flow.reconfigure_entry = SimpleNamespace(
        entry_id="entry-id",
        unique_id="electra_rc3_remote_old",
        title="Old AC",
        data={
            config_flow.CONF_NAME: "Old AC",
            config_flow.CONF_INFRARED_ENTITY_ID: "infrared.remote",
        },
    )

    result = asyncio.run(
        flow.async_step_reconfigure(
            {
                config_flow.CONF_NAME: "Bedroom AC",
                config_flow.CONF_INFRARED_ENTITY_ID: "infrared.bedroom",
            }
        )
    )

    assert result["type"] == "form"
    assert result["errors"] == {
        config_flow.CONF_INFRARED_ENTITY_ID: "already_configured"
    }
