"""The Dartsnut PixelDart integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import DartsnutApiClient
from .const import (
    CONF_MCP_PORT,
    CONF_WS_PORT,
    DEFAULT_MCP_PORT,
    DEFAULT_WS_PORT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import DartsnutCoordinator

SERVICE_START_GAME = "start_game"
SERVICE_START_GAME_SCHEMA = vol.Schema(
    {
        vol.Required("game_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Dartsnut component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dartsnut PixelDart from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = DartsnutApiClient(
        session=session,
        host=entry.data[CONF_HOST],
        ws_port=entry.data.get(CONF_WS_PORT, DEFAULT_WS_PORT),
        mcp_port=entry.data.get(CONF_MCP_PORT, DEFAULT_MCP_PORT),
    )

    coordinator = DartsnutCoordinator(hass, client, entry.entry_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_START_GAME):

        async def _handle_start_game(call: ServiceCall) -> None:
            game_id = call.data["game_id"]
            for coord in hass.data.get(DOMAIN, {}).values():
                if isinstance(coord, DartsnutCoordinator):
                    await coord.client.start_game(game_id)
                    await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_START_GAME,
            _handle_start_game,
            schema=SERVICE_START_GAME_SCHEMA,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
