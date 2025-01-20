from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import ImmichHub, InvalidAuth

# Add the new platform for sensors
PLATFORMS: list[Platform] = [Platform.IMAGE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Immich from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize the API hub with the configuration data
    hub = ImmichHub(host=entry.data[CONF_HOST], api_key=entry.data[CONF_API_KEY])

    if not await hub.authenticate():
        raise InvalidAuth

    # Store the hub instance for use by other components
    hass.data[DOMAIN][entry.entry_id] = hub

    # Forward setup for supported platforms, including the new sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up the stored hub instance on unload
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
