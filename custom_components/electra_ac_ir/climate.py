"""Climate platform for the Electra AC IR integration."""

from __future__ import annotations

import logging
from math import isfinite
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_MEDIUM,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_ENTITY_UNIQUE_ID,
    CONF_HUMIDITY_SENSOR,
    CONF_INFRARED_ENTITY_ID,
    CONF_POWER_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_FAN_MODE,
    DEFAULT_HVAC_MODE,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    MANUFACTURER,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    MODEL,
    SUPPORTED_FAN_MODES,
    SUPPORTED_HVAC_MODES,
)
from .protocol import ElectraRc3Command, ElectraRc3State

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SWING_OFF = "off"
SWING_ON = "on"
SWING_MODES = [SWING_OFF, SWING_ON]
LAST_ON_OPERATION = "last_on_operation"


def _coerce_target_temperature(temperature: Any) -> int | None:
    """Coerce and validate an Electra RC-3 target temperature."""
    try:
        target_temperature = round(float(temperature))
    except (TypeError, ValueError, OverflowError):
        _LOGGER.warning(
            "Ignoring non-numeric Electra RC-3 temperature: %s", temperature
        )
        return None

    if MIN_TEMPERATURE <= target_temperature <= MAX_TEMPERATURE:
        return target_temperature

    _LOGGER.warning("Temperature %s is outside the Electra RC-3 range", temperature)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an Electra RC-3 climate entity from a config entry."""
    async_add_entities([ElectraRc3Climate(entry)])


class ElectraRc3Climate(ClimateEntity, RestoreEntity):
    """Electra RC-3 climate entity controlled through an infrared emitter."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_fan_modes = SUPPORTED_FAN_MODES
    _attr_swing_modes = SWING_MODES
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the Electra RC-3 climate entity."""
        data = entry.data
        name = data[CONF_NAME]
        config_unique_id = entry.unique_id or entry.entry_id
        entity_unique_id = data.get(CONF_ENTITY_UNIQUE_ID) or config_unique_id

        self._attr_unique_id = f"{entity_unique_id}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entity_unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=name,
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature = DEFAULT_TEMPERATURE
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = DEFAULT_FAN_MODE
        self._attr_swing_mode = SWING_OFF
        self._attr_available = False

        self._infrared_emitter_entity_id = data[CONF_INFRARED_ENTITY_ID]
        self._temperature_sensor_entity_id = data.get(CONF_TEMPERATURE_SENSOR)
        self._humidity_sensor_entity_id = data.get(CONF_HUMIDITY_SENSOR)
        self._power_sensor_entity_id = data.get(CONF_POWER_SENSOR)
        self._last_on_operation = DEFAULT_HVAC_MODE
        self._last_sent_hvac_mode = HVACMode.OFF

    async def async_added_to_hass(self) -> None:
        """Subscribe to entity changes and restore the previous climate state."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._restore_climate_state(last_state.state, last_state.attributes)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._infrared_emitter_entity_id],
                self._async_infrared_emitter_changed,
            )
        )
        self._update_infrared_availability(
            self.hass.states.get(self._infrared_emitter_entity_id)
        )

        if self._temperature_sensor_entity_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._temperature_sensor_entity_id],
                    self._async_temperature_sensor_changed,
                )
            )
            self._update_temperature_from_state(
                self.hass.states.get(self._temperature_sensor_entity_id)
            )

        if self._humidity_sensor_entity_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._humidity_sensor_entity_id],
                    self._async_humidity_sensor_changed,
                )
            )
            self._update_humidity_from_state(
                self.hass.states.get(self._humidity_sensor_entity_id)
            )

        if self._power_sensor_entity_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._power_sensor_entity_id],
                    self._async_power_sensor_changed,
                )
            )
            self._update_power_from_state(
                self.hass.states.get(self._power_sensor_entity_id)
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return integration-specific state attributes."""
        return {LAST_ON_OPERATION: self._last_on_operation}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if temperature is None and hvac_mode is None:
            return

        next_temperature = self._attr_target_temperature
        if (
            temperature is not None
            and (next_temperature := _coerce_target_temperature(temperature)) is None
        ):
            return

        next_hvac_mode = self._attr_hvac_mode
        if hvac_mode is not None:
            next_hvac_mode = HVACMode(hvac_mode)

        if next_hvac_mode == HVACMode.OFF and hvac_mode is None:
            self._attr_target_temperature = next_temperature
            self.async_write_ha_state()
            return

        await self._async_apply_state(
            hvac_mode=next_hvac_mode,
            target_temperature=next_temperature,
            fan_mode=self._attr_fan_mode,
            swing_mode=self._attr_swing_mode,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        await self._async_apply_state(
            hvac_mode=HVACMode(hvac_mode),
            target_temperature=self._attr_target_temperature,
            fan_mode=self._attr_fan_mode,
            swing_mode=self._attr_swing_mode,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if fan_mode not in SUPPORTED_FAN_MODES:
            _LOGGER.warning("Unsupported Electra RC-3 fan mode: %s", fan_mode)
            return

        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()
            return

        await self._async_apply_state(
            hvac_mode=self._attr_hvac_mode,
            target_temperature=self._attr_target_temperature,
            fan_mode=fan_mode,
            swing_mode=self._attr_swing_mode,
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        if swing_mode not in SWING_MODES:
            _LOGGER.warning("Unsupported Electra RC-3 swing mode: %s", swing_mode)
            return

        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()
            return

        await self._async_apply_state(
            hvac_mode=self._attr_hvac_mode,
            target_temperature=self._attr_target_temperature,
            fan_mode=self._attr_fan_mode,
            swing_mode=swing_mode,
        )

    async def async_turn_on(self) -> None:
        """Turn on the AC using the last non-off mode."""
        await self.async_set_hvac_mode(self._last_on_operation or DEFAULT_HVAC_MODE)

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _async_apply_state(
        self,
        *,
        hvac_mode: HVACMode,
        target_temperature: int,
        fan_mode: str,
        swing_mode: str,
    ) -> None:
        """Send an IR command and update the assumed climate state."""
        if hvac_mode not in SUPPORTED_HVAC_MODES:
            _LOGGER.warning("Unsupported Electra RC-3 HVAC mode: %s", hvac_mode)
            return

        validated_temperature = _coerce_target_temperature(target_temperature)
        if validated_temperature is None:
            return
        target_temperature = validated_temperature

        command = ElectraRc3Command(
            ElectraRc3State(
                hvac_mode=hvac_mode,
                target_temperature=target_temperature,
                fan_mode=fan_mode,
                swing_mode=swing_mode,
                power=self._last_sent_hvac_mode == HVACMode.OFF
                and hvac_mode != HVACMode.OFF,
            )
        )
        await self._async_send_ir_command(command)

        self._attr_hvac_mode = hvac_mode
        self._attr_target_temperature = target_temperature
        self._attr_fan_mode = fan_mode
        self._attr_swing_mode = swing_mode
        self._last_sent_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_on_operation = hvac_mode
        self.async_write_ha_state()

    def _restore_climate_state(
        self, state: StateType, attributes: dict[str, Any]
    ) -> None:
        """Restore previous climate state attributes."""
        if state in SUPPORTED_HVAC_MODES:
            self._attr_hvac_mode = HVACMode(state)
            self._last_sent_hvac_mode = HVACMode(state)

        if (
            (temperature := attributes.get(ATTR_TEMPERATURE)) is not None
            and (restored_temperature := _coerce_target_temperature(temperature))
            is not None
        ):
            self._attr_target_temperature = restored_temperature

        if (fan_mode := attributes.get("fan_mode")) in SUPPORTED_FAN_MODES:
            self._attr_fan_mode = fan_mode
        elif self._attr_fan_mode == FAN_MEDIUM:
            self._attr_fan_mode = FAN_AUTO

        if (swing_mode := attributes.get("swing_mode")) in SWING_MODES:
            self._attr_swing_mode = swing_mode

        last_on_operation = attributes.get(LAST_ON_OPERATION)
        if (
            last_on_operation in SUPPORTED_HVAC_MODES
            and last_on_operation != HVACMode.OFF
        ):
            self._last_on_operation = HVACMode(last_on_operation)
        elif self._attr_hvac_mode != HVACMode.OFF:
            self._last_on_operation = self._attr_hvac_mode

    @callback
    def _async_infrared_emitter_changed(self, event: Event) -> None:
        """Handle infrared emitter availability changes."""
        self._update_infrared_availability(event.data["new_state"])

    @callback
    def _async_temperature_sensor_changed(self, event: Event) -> None:
        """Handle temperature sensor changes."""
        self._update_temperature_from_state(event.data["new_state"])
        self.async_write_ha_state()

    async def _async_send_ir_command(self, command: ElectraRc3Command) -> None:
        """Send an IR command through the configured infrared emitter."""
        await async_send_command(
            self.hass,
            self._infrared_emitter_entity_id,
            command,
            context=self._context,
        )

    @callback
    def _update_infrared_availability(self, state) -> None:
        """Update availability from the configured infrared emitter state."""
        available = state is not None and state.state != STATE_UNAVAILABLE
        if available == self.available:
            return

        _LOGGER.info(
            "Infrared entity %s used by %s is %s",
            self._infrared_emitter_entity_id,
            self.entity_id,
            "available" if available else "unavailable",
        )
        self._attr_available = available
        self.async_write_ha_state()

    @callback
    def _async_humidity_sensor_changed(self, event: Event) -> None:
        """Handle humidity sensor changes."""
        self._update_humidity_from_state(event.data["new_state"])
        self.async_write_ha_state()

    @callback
    def _async_power_sensor_changed(self, event: Event) -> None:
        """Handle power sensor changes."""
        self._update_power_from_state(event.data["new_state"])
        self.async_write_ha_state()

    @callback
    def _update_temperature_from_state(self, state) -> None:
        """Update the current temperature from a sensor state."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            temperature = float(state.state)
        except (TypeError, ValueError):
            _LOGGER.warning("Ignoring non-numeric temperature from %s", state.entity_id)
            return

        if not isfinite(temperature):
            _LOGGER.warning("Ignoring non-finite temperature from %s", state.entity_id)
            return

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit not in (None, UnitOfTemperature.CELSIUS):
            try:
                temperature = TemperatureConverter.convert(
                    temperature, unit, UnitOfTemperature.CELSIUS
                )
            except HomeAssistantError:
                _LOGGER.warning(
                    "Ignoring temperature from %s with unsupported unit %s",
                    state.entity_id,
                    unit,
                )
                return

        self._attr_current_temperature = temperature

    @callback
    def _update_humidity_from_state(self, state) -> None:
        """Update the current humidity from a sensor state."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            humidity = float(state.state)
        except (TypeError, ValueError):
            _LOGGER.warning("Ignoring non-numeric humidity from %s", state.entity_id)
            return

        if not isfinite(humidity):
            _LOGGER.warning("Ignoring non-finite humidity from %s", state.entity_id)
            return

        self._attr_current_humidity = humidity

    @callback
    def _update_power_from_state(self, state) -> None:
        """Update assumed HVAC mode from the optional power sensor."""
        if state is None:
            return

        if state.state == STATE_OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._last_sent_hvac_mode = HVACMode.OFF
        elif state.state == STATE_ON and self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_mode = self._last_on_operation or DEFAULT_HVAC_MODE
            self._last_sent_hvac_mode = self._attr_hvac_mode
