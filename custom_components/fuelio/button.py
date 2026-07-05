"""Pulsante per forzare l'aggiornamento dei dati Fuelio."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DOMAIN
from .coordinator import FuelioCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Crea il pulsante di aggiornamento forzato."""
    coordinator: FuelioCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FuelioRefreshButton(coordinator, entry)])


class FuelioRefreshButton(CoordinatorEntity[FuelioCoordinator], ButtonEntity):
    """Forza il download e il ricalcolo immediato dei dati Fuelio."""

    _attr_has_entity_name = True
    _attr_name = "Aggiorna dati"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: FuelioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_refresh_button"
        device_name = entry.data.get(CONF_DEVICE_NAME) or "Fuelio"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Fuelio",
            model="Backup CSV via Dropbox",
        )

    async def async_press(self) -> None:
        """Forza un refresh immediato (NON debounced) e mostra un esito visibile."""
        # A differenza di async_request_refresh(), async_refresh() esegue
        # subito, ogni volta, senza attese/debounce: comportamento prevedibile
        # per un pulsante premuto manualmente.
        await self.coordinator.async_refresh()

        if self.coordinator.last_update_success:
            file_name = (self.coordinator.data or {}).get("file_name", "?")
            message = f"Dati aggiornati con successo (file: {file_name})."
        else:
            message = f"Aggiornamento fallito: {self.coordinator.last_exception}"

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Fuelio",
                "message": message,
                "notification_id": f"fuelio_refresh_{self._entry_id}",
            },
        )
