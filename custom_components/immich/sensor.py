"""Sensor platform for Immich integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed
)

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_WATCHED_ALBUMS
)
from .hub import ImmichHub, CannotConnect, InvalidAuth

_LOGGER: Final = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="total_images",
        name="Immich: Total Images",
        icon="mdi:image",
        native_unit_of_measurement="images"
    ),
    SensorEntityDescription(
        key="total_videos",
        name="Immich: Total Videos",
        icon="mdi:video",
        native_unit_of_measurement="videos"
    ),
    SensorEntityDescription(
        key="total_assets",
        name="Immich: Total Assets",
        icon="mdi:folder",
        native_unit_of_measurement="assets"
    ),
    SensorEntityDescription(
        key="favorite_assets",
        name="Immich: Favorite Assets",
        icon="mdi:heart",
        native_unit_of_measurement="assets"
    ),
    SensorEntityDescription(
        key="total_people",
        name="Immich: Total People",
        icon="mdi:account-group",
        native_unit_of_measurement="people"
    ),
    SensorEntityDescription(
        key="hidden_people",
        name="Immich: Hidden People",
        icon="mdi:account-off",
        native_unit_of_measurement="people"
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Immich sensor platform."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {"sensors": {}}

    hub = ImmichHub(
        host=config_entry.data[CONF_HOST],
        api_key=config_entry.data[CONF_API_KEY]
    )

    # Create static sensors
    entities = [
        ImmichSensor(hub, description)
        for description in SENSORS
    ]
    
    # Create dynamic person sensors
    try:
        people_data = await hub.get_people()
        if isinstance(people_data, dict) and "people" in people_data:
            for person in people_data["people"]:
                if isinstance(person, dict) and person.get("name"):
                    clean_name = person['name'].lower().replace(" ", "_")
                    description = SensorEntityDescription(
                        key=f"person_{clean_name}_assets",
                        name=f"Immich: Person {person['name']} Assets",
                        icon="mdi:account",
                        native_unit_of_measurement="assets"
                    )
                    entity = ImmichSensor(hub, description)
                    entity._original_name = person['name']  # Store original name
                    entities.append(entity)
    except Exception as e:
        _LOGGER.error("Failed to create person sensors: %s", str(e))
    
    async_add_entities(entities, True)

class ImmichSensor(SensorEntity):
    """Representation of an Immich sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        hub: ImmichHub,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.hub = hub
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._state = None
        self._original_name = None

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            if self.entity_description.key == "total_images":
                stats = await self.hub.get_asset_statistics()
                self._state = stats.images
            elif self.entity_description.key == "total_videos":
                stats = await self.hub.get_asset_statistics()
                self._state = stats.videos
            elif self.entity_description.key == "total_assets":
                stats = await self.hub.get_asset_statistics()
                self._state = stats.total
            elif self.entity_description.key == "favorite_assets":
                stats = await self.hub.get_favorite_statistics()
                self._state = stats.get("total", 0)
            elif self.entity_description.key == "total_people":
                people_data = await self.hub.get_people()
                self._state = people_data.get("total", 0)
            elif self.entity_description.key == "hidden_people":
                people_data = await self.hub.get_people()
                self._state = people_data.get("hidden", 0)
            elif self.entity_description.key.startswith("person_"):
                if not hasattr(self, '_original_name'):
                    _LOGGER.warning("Original name not found for %s", self.entity_description.key)
                    self._state = None
                    return
                
                people_data = await self.hub.get_people()
                if not isinstance(people_data, dict) or "people" not in people_data:
                    _LOGGER.error("Invalid people data structure received")
                    self._state = None
                    return
                
                person = next((p for p in people_data["people"] if isinstance(p, dict) and p.get("name", "").lower() == self._original_name.lower()), None)
                if person:
                    stats = await self.hub.get_person_statistics(person["id"])
                    self._state = stats.get("assets", 0)
                else:
                    _LOGGER.warning("Could not find %s in people list", self._original_name)
                    self._state = None
                
        except (CannotConnect, InvalidAuth) as err:
            _LOGGER.error("Error updating %s: %s", self.entity_description.key, err)
            self._state = None
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error updating %s: %s", self.entity_description.key, err)
            self._state = None
