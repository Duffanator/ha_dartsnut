"""The Dartsnut PixelDart integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service import async_extract_config_entry_ids
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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_START_GAME = "start_game"
SERVICE_START_GAME_SCHEMA = cv.make_entity_service_schema(
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
            entry_ids = await async_extract_config_entry_ids(hass, call)
            coordinators = [
                hass.data.get(DOMAIN, {}).get(eid)
                for eid in entry_ids
                if isinstance(hass.data.get(DOMAIN, {}).get(eid), DartsnutCoordinator)
            ]
            if not coordinators:
                raise ServiceValidationError(
                    "No target Dartsnut device or entity was found for start_game"
                )
            for coord in coordinators:
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
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_START_GAME)
    return unload_ok
