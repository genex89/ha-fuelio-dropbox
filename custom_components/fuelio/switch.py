"""Switch per abilitare/disabilitare le notifiche del pulsante 'Aggiorna dati'."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_DEVICE_NAME, DOMAIN
from .coordinator import FuelioCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Crea lo switch delle notifiche."""
    coordinator: FuelioCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FuelioNotifyToggle(coordinator, entry)])


class FuelioNotifyToggle(SwitchEntity, RestoreEntity):
    """Attiva/disattiva la notifica persistente mostrata dal pulsante 'Aggiorna dati'."""

    _attr_has_entity_name = True
    _attr_name = "Notifiche aggiornamento"
    _attr_icon = "mdi:bell-outline"

    def __init__(self, coordinator: FuelioCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_notify_toggle"
        device_name = entry.data.get(CONF_DEVICE_NAME) or "Fuelio"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Fuelio",
            model="Backup CSV via Dropbox",
        )
        self._attr_is_on = True  # default: notifiche attive

    async def async_added_to_hass(self) -> None:
        """Ripristina lo stato salvato (persiste tra i riavvii)."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        self.coordinator.notifications_enabled = self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.coordinator.notifications_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.coordinator.notifications_enabled = False
        self.async_write_ha_state()
