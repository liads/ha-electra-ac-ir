"""Constants for the Electra AC IR integration."""

from __future__ import annotations

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
)
from homeassistant.const import Platform

DOMAIN = "electra_ac_ir"

CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_POWER_SENSOR = "power_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"

DEFAULT_NAME = "Electra AC"
DEFAULT_TEMPERATURE = 24
DEFAULT_FAN_MODE = FAN_AUTO
DEFAULT_HVAC_MODE = HVACMode.AUTO

MANUFACTURER = "Electra"
MODEL = "RC-3"

MIN_TEMPERATURE = 16
MAX_TEMPERATURE = 30

SUPPORTED_HVAC_MODES: list[HVACMode] = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
    HVACMode.DRY,
]
SUPPORTED_FAN_MODES: list[str] = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

PLATFORMS: list[Platform] = [Platform.CLIMATE]
