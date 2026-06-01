"""Tests for the Electra RC-3 climate entity."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from .common import (
    UnitOfTemperature,
    clear_integration_modules,
    fake_config_entry,
    install_homeassistant_stubs,
)


@pytest.fixture
def climate(monkeypatch):
    """Import the climate module with Home Assistant stubs."""
    install_homeassistant_stubs(monkeypatch)
    clear_integration_modules(monkeypatch)
    return importlib.import_module("custom_components.electra_ac_ir.climate")


def _entity(climate, **data_overrides):
    entity = climate.ElectraRc3Climate(fake_config_entry(climate, **data_overrides))
    entity.entity_id = "climate.living_room"
    return entity


def _state(state: str, **attributes):
    return SimpleNamespace(
        state=state,
        attributes=attributes,
        entity_id="sensor.test",
    )


def _event(new_state):
    return SimpleNamespace(data={"new_state": new_state})


def test_setup_entry_adds_entity(climate) -> None:
    """Platform setup creates one climate entity."""
    added = []

    asyncio.run(
        climate.async_setup_entry(None, fake_config_entry(climate), added.extend)
    )

    assert len(added) == 1
    assert isinstance(added[0], climate.ElectraRc3Climate)


def test_entity_unique_id_can_be_decoupled_from_config_entry_unique_id(
    climate,
) -> None:
    """A reconfigured entry keeps the same climate entity and device identity."""
    entity = _entity(climate, **{climate.CONF_ENTITY_UNIQUE_ID: "stable-entry-id"})

    assert entity._attr_unique_id == "stable-entry-id_climate"
    assert entity._attr_device_info["identifiers"] == {
        (climate.DOMAIN, "stable-entry-id")
    }


def test_target_temperature_is_coerced_and_validated(climate) -> None:
    """Target temperatures are rounded and range checked."""
    assert climate._coerce_target_temperature("23.6") == 24
    assert climate._coerce_target_temperature("15") is None
    assert climate._coerce_target_temperature("not-a-number") is None


def test_restore_ignores_invalid_temperature(climate) -> None:
    """Invalid restored temperatures do not replace the default target."""
    entity = _entity(climate)

    entity._restore_climate_state(
        climate.HVACMode.COOL,
        {
            climate.ATTR_TEMPERATURE: "99",
            "fan_mode": "high",
            "swing_mode": "on",
            climate.LAST_ON_OPERATION: climate.HVACMode.HEAT,
        },
    )

    assert entity._attr_hvac_mode == climate.HVACMode.COOL
    assert entity._attr_target_temperature == climate.DEFAULT_TEMPERATURE
    assert entity._attr_fan_mode == "high"
    assert entity._attr_swing_mode == "on"
    assert entity.extra_state_attributes == {
        climate.LAST_ON_OPERATION: climate.HVACMode.HEAT
    }


def test_temperature_sensor_is_converted_to_celsius(climate) -> None:
    """External temperature sensor readings are converted to climate units."""
    entity = _entity(climate)

    entity._update_temperature_from_state(
        _state(
            "77",
            **{climate.ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
        )
    )

    assert entity._attr_current_temperature == pytest.approx(25)


def test_invalid_sensor_values_are_ignored(climate) -> None:
    """Invalid sensor values do not update climate attributes."""
    entity = _entity(climate)

    entity._update_temperature_from_state(_state("nan"))
    entity._update_humidity_from_state(_state("not-a-number"))

    assert not hasattr(entity, "_attr_current_temperature")
    assert not hasattr(entity, "_attr_current_humidity")


def test_power_sensor_updates_assumed_mode(climate) -> None:
    """Power sensor state keeps assumed HVAC mode in sync."""
    entity = _entity(climate)
    entity._attr_hvac_mode = climate.HVACMode.COOL
    entity._last_sent_hvac_mode = climate.HVACMode.COOL

    entity._update_power_from_state(_state(climate.STATE_OFF))

    assert entity._attr_hvac_mode == climate.HVACMode.OFF
    assert entity._last_sent_hvac_mode == climate.HVACMode.OFF

    entity._update_power_from_state(_state(climate.STATE_ON))

    assert entity._attr_hvac_mode == climate.DEFAULT_HVAC_MODE
    assert entity._last_sent_hvac_mode == climate.DEFAULT_HVAC_MODE


@pytest.mark.parametrize(
    "emitter_state",
    [None, "unavailable", "unknown"],
)
def test_infrared_emitter_unavailable_states_mark_entity_unavailable(
    climate, emitter_state
) -> None:
    """Missing, unavailable, and unknown emitters make the climate unavailable."""
    entity = _entity(climate)
    entity._attr_available = True

    state = None if emitter_state is None else _state(emitter_state)
    entity._update_infrared_availability(state)

    assert entity._attr_available is False


def test_infrared_emitter_normal_state_marks_entity_available(climate) -> None:
    """A normal emitter state makes the climate available."""
    entity = _entity(climate)

    entity._update_infrared_availability(_state("idle"))

    assert entity._attr_available is True


def test_setters_defer_to_apply_state_or_update_offline_preferences(climate) -> None:
    """Setter methods either send state or store offline preferences."""
    entity = _entity(climate)
    entity._async_apply_state = AsyncMock()

    asyncio.run(entity.async_set_temperature(temperature=25))
    assert entity._attr_target_temperature == 25

    asyncio.run(entity.async_set_fan_mode("low"))
    assert entity._attr_fan_mode == "low"

    asyncio.run(entity.async_set_swing_mode("on"))
    assert entity._attr_swing_mode == "on"

    entity._attr_hvac_mode = climate.HVACMode.COOL
    asyncio.run(entity.async_set_fan_mode("high"))
    entity._async_apply_state.assert_awaited_with(
        hvac_mode=climate.HVACMode.COOL,
        target_temperature=25,
        fan_mode="high",
        swing_mode="on",
    )


def test_apply_state_sends_command_and_updates_assumed_state(climate) -> None:
    """Applying state sends an IR command and updates entity state."""
    entity = _entity(climate)
    entity._async_send_ir_command = AsyncMock()

    asyncio.run(
        entity._async_apply_state(
            hvac_mode=climate.HVACMode.COOL,
            target_temperature=24,
            fan_mode="auto",
            swing_mode="off",
        )
    )

    command = entity._async_send_ir_command.await_args.args[0]
    assert command.state.power is True
    assert entity._attr_hvac_mode == climate.HVACMode.COOL
    assert entity._last_on_operation == climate.HVACMode.COOL
    assert entity.write_count == 1


def test_apply_state_rejects_invalid_state(climate) -> None:
    """Unsupported state is rejected before an IR command is sent."""
    entity = _entity(climate)
    entity._async_send_ir_command = AsyncMock()

    asyncio.run(
        entity._async_apply_state(
            hvac_mode="unsupported",
            target_temperature=24,
            fan_mode="auto",
            swing_mode="off",
        )
    )
    asyncio.run(
        entity._async_apply_state(
            hvac_mode=climate.HVACMode.COOL,
            target_temperature=31,
            fan_mode="auto",
            swing_mode="off",
        )
    )

    entity._async_send_ir_command.assert_not_awaited()


def test_state_change_handlers_write_state(climate) -> None:
    """State change handlers update attributes and write state."""
    entity = _entity(climate)

    entity._async_infrared_emitter_changed(_event(_state("idle")))
    entity._async_temperature_sensor_changed(_event(_state("23")))
    entity._async_humidity_sensor_changed(_event(_state("45")))
    entity._async_power_sensor_changed(_event(_state(climate.STATE_OFF)))

    assert entity._attr_available is True
    assert entity._attr_current_temperature == 23
    assert entity._attr_current_humidity == 45
    assert entity.write_count >= 4
