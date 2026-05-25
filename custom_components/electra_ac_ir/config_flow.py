"""Config flow for the Electra AC IR integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import infrared
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import (
    CONF_HUMIDITY_SENSOR,
    CONF_INFRARED_ENTITY_ID,
    CONF_POWER_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_NAME,
    DOMAIN,
)


class ElectraAcIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Electra AC IR config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = infrared.async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            emitter_entity_id = user_input[CONF_INFRARED_ENTITY_ID]
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                unique_id = _unique_id_for_emitter(self.hass, emitter_entity_id)

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_NAME: name,
                    CONF_INFRARED_ENTITY_ID: emitter_entity_id,
                }
                data.update(
                    {
                        key: value
                        for key, value in user_input.items()
                        if key not in data and value
                    }
                )

                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
                    vol.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=infrared.DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    vol.Optional(CONF_TEMPERATURE_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            filter={
                                "domain": "sensor",
                                "device_class": SensorDeviceClass.TEMPERATURE,
                            }
                        )
                    ),
                    vol.Optional(CONF_HUMIDITY_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            filter={
                                "domain": "sensor",
                                "device_class": SensorDeviceClass.HUMIDITY,
                            }
                        )
                    ),
                    vol.Optional(CONF_POWER_SENSOR): EntitySelector(
                        EntitySelectorConfig(domain="binary_sensor")
                    ),
                }
            ),
            errors=errors,
        )


def _unique_id_for_emitter(hass, emitter_entity_id: str) -> str:
    """Return a stable unique ID for an emitter-backed Electra climate entity."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(emitter_entity_id)
    if entry is not None and entry.unique_id is not None:
        return f"electra_rc3_{entry.platform}_{entry.unique_id}"

    return f"electra_rc3_{emitter_entity_id}"
