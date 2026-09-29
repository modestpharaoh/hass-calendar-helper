"""Config flow for Calendar Helper."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_REGISTER_CALENDAR_SERVICES,
    DEFAULT_REGISTER_CALENDAR_SERVICES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CalendarHelperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Calendar Helper."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Calendar Helper",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_REGISTER_CALENDAR_SERVICES,
                    default=DEFAULT_REGISTER_CALENDAR_SERVICES,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow handler."""
        return CalendarHelperOptionsFlowHandler(config_entry)


class CalendarHelperOptionsFlowHandler(OptionsFlow):
    """Handle options for Calendar Helper."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Calendar Helper options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_val = self._config_entry.options.get(
            CONF_REGISTER_CALENDAR_SERVICES,
            self._config_entry.data.get(
                CONF_REGISTER_CALENDAR_SERVICES, DEFAULT_REGISTER_CALENDAR_SERVICES
            ),
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_REGISTER_CALENDAR_SERVICES,
                    default=current_val,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
