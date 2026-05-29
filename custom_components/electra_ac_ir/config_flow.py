"""Config flow for the Electra AC IR integration."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import infrared
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import (
    CONF_ENTITY_UNIQUE_ID,
    CONF_HUMIDITY_SENSOR,
    CONF_INFRARED_ENTITY_ID,
    CONF_POWER_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_NAME,
    DOMAIN,
)

OPTIONAL_SENSOR_KEYS = (
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_POWER_SENSOR,
)


class ElectraAcIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Electra AC IR config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._async_step_config(user_input=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing config entry."""
        return await self._async_step_config(
            user_input=user_input,
            reconfigure_entry=self._get_reconfigure_entry(),
        )

    async def _async_step_config(
        self,
        *,
        user_input: dict[str, Any] | None = None,
        reconfigure_entry: ConfigEntry | None = None,
    ) -> ConfigFlowResult:
        """Handle the shared setup and reconfigure form."""
        emitter_entity_ids = infrared.async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        errors: dict[str, str] = {}
        if user_input is not None:
            data = _data_from_user_input(user_input)
            name = data[CONF_NAME]
            emitter_entity_id = user_input[CONF_INFRARED_ENTITY_ID]
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                if reconfigure_entry is None:
                    unique_id = f"electra_rc3_{uuid4().hex}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    if _is_emitter_configured_elsewhere(
                        self.hass, emitter_entity_id
                    ):
                        errors[CONF_INFRARED_ENTITY_ID] = "already_configured"
                    else:
                        data[CONF_ENTITY_UNIQUE_ID] = unique_id
                        return self.async_create_entry(title=name, data=data)
                else:
                    await self.async_set_unique_id(reconfigure_entry.unique_id)
                    self._abort_if_unique_id_mismatch()
                    if _is_emitter_configured_elsewhere(
                        self.hass, emitter_entity_id, reconfigure_entry
                    ):
                        errors[CONF_INFRARED_ENTITY_ID] = "already_configured"
                    else:
                        data[CONF_ENTITY_UNIQUE_ID] = _entity_unique_id(
                            reconfigure_entry
                        )
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            title=name,
                            data=data,
                        )

        defaults = dict(reconfigure_entry.data) if reconfigure_entry is not None else {}
        data_schema = _data_schema(emitter_entity_ids, defaults)
        if reconfigure_entry is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, defaults)

        return self.async_show_form(
            step_id="reconfigure" if reconfigure_entry is not None else "user",
            data_schema=data_schema,
            errors=errors,
        )


def _data_schema(
    emitter_entity_ids: list[str],
    defaults: dict[str, Any],
) -> vol.Schema:
    """Return the setup/reconfigure form schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=defaults.get(CONF_NAME, DEFAULT_NAME),
            ): TextSelector(),
            _required(CONF_INFRARED_ENTITY_ID, defaults): EntitySelector(
                EntitySelectorConfig(
                    domain=infrared.DOMAIN,
                    include_entities=emitter_entity_ids,
                )
            ),
            _optional(CONF_TEMPERATURE_SENSOR, defaults): EntitySelector(
                EntitySelectorConfig(
                    filter={
                        "domain": "sensor",
                        "device_class": SensorDeviceClass.TEMPERATURE,
                    }
                )
            ),
            _optional(CONF_HUMIDITY_SENSOR, defaults): EntitySelector(
                EntitySelectorConfig(
                    filter={
                        "domain": "sensor",
                        "device_class": SensorDeviceClass.HUMIDITY,
                    }
                )
            ),
            _optional(CONF_POWER_SENSOR, defaults): EntitySelector(
                EntitySelectorConfig(domain="binary_sensor")
            ),
        }
    )


def _required(key: str, defaults: dict[str, Any]) -> vol.Required:
    """Return a required field marker with a default when configured."""
    if key in defaults:
        return vol.Required(key, default=defaults.get(key))
    return vol.Required(key)


def _optional(key: str, defaults: dict[str, Any]) -> vol.Optional:
    """Return an optional field marker."""
    return vol.Optional(key)


def _data_from_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return config entry data from form input."""
    data = {
        CONF_NAME: user_input[CONF_NAME].strip(),
        CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID],
    }
    data.update(
        {
            key: value
            for key in OPTIONAL_SENSOR_KEYS
            if (value := user_input.get(key))
        }
    )
    return data


def _entity_unique_id(entry: ConfigEntry) -> str:
    """Return the stable entity/device unique ID for an entry."""
    return entry.data.get(CONF_ENTITY_UNIQUE_ID) or entry.unique_id or entry.entry_id


def _is_emitter_configured_elsewhere(
    hass,
    emitter_entity_id: str,
    entry: ConfigEntry | None = None,
) -> bool:
    """Return whether an infrared emitter is already used by another entry."""
    if not hasattr(hass, "config_entries") or not hasattr(
        hass.config_entries, "async_entries"
    ):
        return False

    for configured_entry in hass.config_entries.async_entries(DOMAIN):
        if entry is not None and configured_entry.entry_id == entry.entry_id:
            continue
        if configured_entry.data.get(CONF_INFRARED_ENTITY_ID) == emitter_entity_id:
            return True
    return False
