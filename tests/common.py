"""Shared test helpers for Electra AC IR."""

from __future__ import annotations

import sys
import types
from enum import IntFlag
from types import SimpleNamespace
from typing import Any


class HVACMode(str):
    """Tiny HVAC mode stub."""

    OFF = "off"
    AUTO = "auto"
    COOL = "cool"
    HEAT = "heat"
    FAN_ONLY = "fan_only"
    DRY = "dry"


class ClimateEntityFeature(IntFlag):
    """Tiny climate feature flag stub."""

    TARGET_TEMPERATURE = 1
    FAN_MODE = 2
    SWING_MODE = 4
    TURN_ON = 8
    TURN_OFF = 16


class UnitOfTemperature(str):
    """Tiny temperature unit stub."""

    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    KELVIN = "K"


class Platform(str):
    """Tiny platform stub."""

    CLIMATE = "climate"


class HomeAssistantError(Exception):
    """Tiny Home Assistant error stub."""


class ClimateEntity:
    """Tiny climate entity stub."""

    _context = None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return getattr(self, "_attr_available", True)

    async def async_added_to_hass(self) -> None:
        """Add entity to hass."""

    async def async_get_last_state(self):
        """Return a configured last state."""
        return getattr(self, "_last_state", None)

    def async_on_remove(self, remove_callback) -> None:
        """Track a remove callback."""
        self.remove_callbacks = [
            *getattr(self, "remove_callbacks", []),
            remove_callback,
        ]

    def async_write_ha_state(self) -> None:
        """Record a state write."""
        self.write_count = getattr(self, "write_count", 0) + 1


class RestoreEntity:
    """Tiny restore entity stub."""


class ConfigFlow:
    """Tiny config flow stub."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Accept Home Assistant's domain keyword."""
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id: str) -> None:
        """Record the configured unique ID."""
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        """No-op duplicate check."""

    def _abort_if_unique_id_mismatch(self) -> None:
        """Record that the reconfigure unique ID was checked."""
        self.unique_id_mismatch_checked = True

    def _get_reconfigure_entry(self):
        """Return a configured reconfigure entry."""
        return self.reconfigure_entry

    def add_suggested_values_to_schema(self, data_schema, suggested_values):
        """Add suggested values to matching form markers."""
        for marker in data_schema.schema:
            if marker.schema in suggested_values:
                marker.description = {
                    "suggested_value": suggested_values[marker.schema]
                }
        return data_schema

    def async_abort(self, *, reason: str) -> dict[str, Any]:
        """Return an abort result."""
        return {"type": "abort", "reason": reason}

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        """Return a form result."""
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        """Return a create entry result."""
        return {"type": "create_entry", **kwargs}

    def async_update_reload_and_abort(self, entry, **kwargs: Any) -> dict[str, Any]:
        """Update an entry, schedule reload, and return an abort result."""
        for attr in ("unique_id", "title", "data", "options"):
            if attr in kwargs:
                setattr(entry, attr, kwargs[attr])
        if hasattr(self.hass.config_entries, "async_schedule_reload"):
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason=kwargs.get("reason", "reconfigure_successful"))


class ConfigEntry:
    """Tiny config entry stub."""


class DeviceInfo(dict):
    """Tiny device info stub."""


class EntitySelectorConfig(dict):
    """Tiny entity selector config stub."""

    def __init__(self, **kwargs: Any) -> None:
        """Store selector configuration."""
        super().__init__(kwargs)


class EntitySelector:
    """Tiny entity selector stub."""

    def __init__(self, config: EntitySelectorConfig) -> None:
        """Store selector config."""
        self.config = config


class TextSelector:
    """Tiny text selector stub."""


class SensorDeviceClass(str):
    """Tiny sensor device class stub."""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class _VolMarker:
    """Tiny voluptuous marker stub."""

    def __init__(self, schema: str, default: Any = None) -> None:
        self.schema = schema
        self.default = default
        self.description = None

    def __hash__(self) -> int:
        return hash((self.schema, self.default, type(self).__name__))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, _VolMarker)
            and self.schema == other.schema
            and self.default == other.default
            and type(self) is type(other)
        )


class _Required(_VolMarker):
    """Tiny required marker."""


class _Optional(_VolMarker):
    """Tiny optional marker."""


class Schema:
    """Tiny voluptuous schema stub."""

    def __init__(self, schema: dict[Any, Any]) -> None:
        self.schema = schema


class TemperatureConverter:
    """Tiny temperature converter stub."""

    @staticmethod
    def convert(value: float, from_unit: str | None, to_unit: str | None) -> float:
        """Convert a temperature value."""
        if from_unit == to_unit:
            return value
        if (
            from_unit == UnitOfTemperature.FAHRENHEIT
            and to_unit == UnitOfTemperature.CELSIUS
        ):
            return (value - 32) / 1.8
        if (
            from_unit == UnitOfTemperature.KELVIN
            and to_unit == UnitOfTemperature.CELSIUS
        ):
            return value - 273.15
        raise HomeAssistantError("unsupported temperature unit")


class EntityRegistry:
    """Tiny entity registry stub."""

    def __init__(self, unique_id: str | None = None, platform: str = "test") -> None:
        self.unique_id = unique_id
        self.platform = platform

    def async_get(self, entity_id: str):
        """Return an entity registry entry."""
        if self.unique_id is None:
            return None
        return SimpleNamespace(unique_id=self.unique_id, platform=self.platform)


def clear_integration_modules(monkeypatch) -> None:
    """Clear imported integration modules."""
    for name in list(sys.modules):
        if name == "custom_components.electra_ac_ir" or name.startswith(
            "custom_components.electra_ac_ir."
        ):
            monkeypatch.delitem(sys.modules, name, raising=False)


def install_homeassistant_stubs(monkeypatch) -> None:
    """Install minimal Home Assistant and dependency stubs."""
    climate = types.ModuleType("homeassistant.components.climate")
    climate.ClimateEntity = ClimateEntity

    climate_const = types.ModuleType("homeassistant.components.climate.const")
    climate_const.ATTR_HVAC_MODE = "hvac_mode"
    climate_const.FAN_AUTO = "auto"
    climate_const.FAN_LOW = "low"
    climate_const.FAN_MEDIUM = "medium"
    climate_const.FAN_HIGH = "high"
    climate_const.ClimateEntityFeature = ClimateEntityFeature
    climate_const.HVACMode = HVACMode

    const = types.ModuleType("homeassistant.const")
    const.ATTR_TEMPERATURE = "temperature"
    const.ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"
    const.CONF_NAME = "name"
    const.PRECISION_WHOLE = 1
    const.STATE_OFF = "off"
    const.STATE_ON = "on"
    const.STATE_UNAVAILABLE = "unavailable"
    const.STATE_UNKNOWN = "unknown"
    const.UnitOfTemperature = UnitOfTemperature
    const.Platform = Platform

    core = types.ModuleType("homeassistant.core")
    core.Event = dict
    core.HomeAssistant = object
    core.callback = lambda func: func

    diagnostics = types.ModuleType("homeassistant.components.diagnostics")
    diagnostics.async_redact_data = _redact_data

    infrared = types.ModuleType("homeassistant.components.infrared")
    infrared.DOMAIN = "infrared"
    infrared.async_get_emitters = lambda hass: ["infrared.remote"]

    async def async_send_command(hass, entity_id_or_uuid, command, *, context=None):
        hass.sent_commands = [
            *getattr(hass, "sent_commands", []),
            (entity_id_or_uuid, command, context),
        ]

    infrared.async_send_command = async_send_command

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.ConfigFlowResult = dict

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = DeviceInfo

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddConfigEntryEntitiesCallback = object

    event = types.ModuleType("homeassistant.helpers.event")
    event.async_track_state_change_event = lambda *args, **kwargs: "remove"

    restore_state = types.ModuleType("homeassistant.helpers.restore_state")
    restore_state.RestoreEntity = RestoreEntity

    typing_module = types.ModuleType("homeassistant.helpers.typing")
    typing_module.StateType = str

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.HomeAssistantError = HomeAssistantError

    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.EntitySelector = EntitySelector
    selector.EntitySelectorConfig = EntitySelectorConfig
    selector.TextSelector = TextSelector

    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda hass: getattr(
        hass, "entity_registry", EntityRegistry()
    )

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.entity_registry = entity_registry

    sensor = types.ModuleType("homeassistant.components.sensor")
    sensor.SensorDeviceClass = SensorDeviceClass

    unit_conversion = types.ModuleType("homeassistant.util.unit_conversion")
    unit_conversion.TemperatureConverter = TemperatureConverter

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Required = lambda schema, default=None: _Required(schema, default)
    voluptuous.Optional = lambda schema, default=None: _Optional(schema, default)
    voluptuous.Schema = Schema

    infrared_protocols = types.ModuleType("infrared_protocols")
    commands = types.ModuleType("infrared_protocols.commands")

    class Command:
        """Tiny infrared command stub."""

        def __init__(self, *, modulation: int, repeat_count: int = 0) -> None:
            self.modulation = modulation
            self.repeat_count = repeat_count

    commands.Command = Command

    components = types.ModuleType("homeassistant.components")
    components.infrared = infrared

    modules = {
        "homeassistant": types.ModuleType("homeassistant"),
        "homeassistant.components": components,
        "homeassistant.components.climate": climate,
        "homeassistant.components.climate.const": climate_const,
        "homeassistant.components.diagnostics": diagnostics,
        "homeassistant.components.infrared": infrared,
        "homeassistant.components.sensor": sensor,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.exceptions": exceptions,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.device_registry": device_registry,
        "homeassistant.helpers.entity_platform": entity_platform,
        "homeassistant.helpers.entity_registry": entity_registry,
        "homeassistant.helpers.event": event,
        "homeassistant.helpers.restore_state": restore_state,
        "homeassistant.helpers.selector": selector,
        "homeassistant.helpers.typing": typing_module,
        "homeassistant.util": types.ModuleType("homeassistant.util"),
        "homeassistant.util.unit_conversion": unit_conversion,
        "infrared_protocols": infrared_protocols,
        "infrared_protocols.commands": commands,
        "voluptuous": voluptuous,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def _redact_data(data: Any, keys: set[str]) -> Any:
    """Redact matching dictionary keys."""
    if isinstance(data, dict):
        return {
            key: "**REDACTED**" if key in keys else _redact_data(value, keys)
            for key, value in data.items()
        }
    return data


def fake_config_entry(module, **data_overrides: Any):
    """Return a fake config entry for the climate entity."""
    data = {
        module.CONF_NAME: "Living Room",
        module.CONF_INFRARED_ENTITY_ID: "infrared.remote",
    }
    data.update(data_overrides)
    return SimpleNamespace(
        data=data,
        unique_id="remote_uid",
        entry_id="entry_uid",
        title="Living Room",
    )
