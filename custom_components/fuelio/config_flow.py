"""Config flow per l'integrazione Fuelio (Dropbox)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_AUTH_CODE,
    CONF_DEVICE_NAME,
    CONF_FILE_NAME,
    CONF_FOLDER,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_DEVICE_NAME,
    DEFAULT_FOLDER,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    DROPBOX_AUTHORIZE_URL,
    DROPBOX_TOKEN_URL,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_APP_KEY): str,
        vol.Required(CONF_APP_SECRET): str,
        vol.Required(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
        vol.Optional(CONF_FOLDER, default=DEFAULT_FOLDER): str,
        vol.Optional(CONF_FILE_NAME, default=""): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES): int,
    }
)

STEP_AUTH_SCHEMA = vol.Schema({vol.Required(CONF_AUTH_CODE): str})


class InvalidAuth(Exception):
    """Codice di autorizzazione o credenziali non validi."""


class CannotConnect(Exception):
    """Impossibile contattare Dropbox."""


async def _exchange_code_for_tokens(
    hass: HomeAssistant, app_key: str, app_secret: str, code: str
) -> dict[str, Any]:
    """Scambia il codice di autorizzazione con i token Dropbox (incluso refresh_token)."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            DROPBOX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": app_key,
                "client_secret": app_secret,
            },
        ) as resp:
            if resp.status in (400, 401):
                raise InvalidAuth
            if resp.status != 200:
                raise CannotConnect
            return await resp.json()
    except (InvalidAuth, CannotConnect):
        raise
    except Exception as err:  # noqa: BLE001
        raise CannotConnect from err


class FuelioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione per Fuelio."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Primo step: App Key, App Secret e impostazioni generali."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data = dict(user_input)
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_auth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Secondo step: apri il link, autorizza, incolla il codice."""
        errors: dict[str, str] = {}
        app_key = self._data[CONF_APP_KEY]
        authorize_url = (
            f"{DROPBOX_AUTHORIZE_URL}?client_id={app_key}"
            "&token_access_type=offline&response_type=code"
        )

        if user_input is not None:
            try:
                tokens = await _exchange_code_for_tokens(
                    self.hass,
                    app_key,
                    self._data[CONF_APP_SECRET],
                    user_input[CONF_AUTH_CODE],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self._data[CONF_REFRESH_TOKEN] = tokens["refresh_token"]
                await self.async_set_unique_id(app_key)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._data[CONF_DEVICE_NAME], data=self._data
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=STEP_AUTH_SCHEMA,
            errors=errors,
            description_placeholders={"authorize_url": authorize_url},
        )
