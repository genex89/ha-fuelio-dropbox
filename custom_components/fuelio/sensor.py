"""Sensori Fuelio (Dropbox)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DOMAIN
from .coordinator import FuelioCoordinator

# (chiave in stats, nome sensore, unita', icona, device_class)
SENSOR_DESCRIPTIONS: list[tuple[str, str, str | None, str, SensorDeviceClass | None]] = [
    ("last_fillup_date", "Data ultimo rifornimento", None, "mdi:calendar", None),
    ("last_odometer", "Ultimo chilometraggio", "km", "mdi:counter", None),
    ("last_liters", "Litri ultimo rifornimento", "L", "mdi:gas-station", None),
    ("last_cost", "Costo ultimo rifornimento", "EUR", "mdi:cash", SensorDeviceClass.MONETARY),
    ("last_price_per_liter", "Prezzo al litro ultimo rifornimento", "EUR/L", "mdi:currency-eur", None),
    ("last_consumption", "Consumo ultimo rifornimento", "L/100km", "mdi:gauge", None),
    ("total_fillups", "Numero rifornimenti totali", None, "mdi:counter", None),
    ("total_liters", "Litri totali", "L", "mdi:gas-station", None),
    ("total_cost", "Spesa totale carburante", "EUR", "mdi:cash-multiple", SensorDeviceClass.MONETARY),
    ("avg_monthly_cost", "Costo medio rifornimenti mensili", "EUR", "mdi:calendar-month", SensorDeviceClass.MONETARY),
    ("current_month_cost", "Costo rifornimenti mese in corso", "EUR", "mdi:calendar-today", SensorDeviceClass.MONETARY),
    ("previous_month_cost", "Costo rifornimenti mese precedente", "EUR", "mdi:calendar-arrow-left", SensorDeviceClass.MONETARY),
    ("current_year_cost", "Costo rifornimenti anno in corso", "EUR", "mdi:calendar-star", SensorDeviceClass.MONETARY),
    ("previous_year_cost", "Costo rifornimenti anno precedente", "EUR", "mdi:calendar-arrow-left", SensorDeviceClass.MONETARY),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Crea tutte le entità sensore Fuelio."""
    coordinator: FuelioCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        FuelioSensor(coordinator, entry, key, name, unit, icon, device_class)
        for key, name, unit, icon, device_class in SENSOR_DESCRIPTIONS
    ]

    entities.append(
        FuelioStationSensor(
            coordinator,
            entry,
            "last_station_name",
            "Distributore ultimo rifornimento",
            None,
            "mdi:map-marker",
            None,
        )
    )
    entities.append(
        FuelioMonthlyCostSensor(
            coordinator,
            entry,
            "monthly_cost_chart",
            "Andamento costi mensili (12 mesi)",
            "EUR",
            "mdi:chart-bar",
            SensorDeviceClass.MONETARY,
        )
    )
    entities.append(
        FuelioMonthlyPriceSensor(
            coordinator,
            entry,
            "monthly_price_chart",
            "Andamento prezzo al litro mensile (12 mesi)",
            "EUR/L",
            "mdi:chart-bar",
            None,
        )
    )

    async_add_entities(entities)


class FuelioSensor(CoordinatorEntity[FuelioCoordinator], SensorEntity):
    """Rappresenta un singolo dato Fuelio come sensore."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FuelioCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str | None,
        icon: str,
        device_class: SensorDeviceClass | None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_unique_id = f"{entry.entry_id}_{key}"

        device_name = entry.data.get(CONF_DEVICE_NAME) or "Fuelio"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Fuelio",
            model="Backup CSV via Dropbox",
        )

    @property
    def native_value(self):
        stats = (self.coordinator.data or {}).get("stats", {})
        return stats.get(self._key)


class FuelioStationSensor(FuelioSensor):
    """Distributore dell'ultimo rifornimento, con link Google Maps come attributo."""

    @property
    def extra_state_attributes(self) -> dict:
        stats = (self.coordinator.data or {}).get("stats", {})
        return {
            "city": stats.get("last_station_city"),
            "latitude": stats.get("last_latitude"),
            "longitude": stats.get("last_longitude"),
            "maps_url": stats.get("last_maps_url"),
        }


class FuelioMonthlyCostSensor(FuelioSensor):
    """Storico dei costi totali degli ultimi 12 mesi, per grafico a barre."""

    @property
    def native_value(self):
        stats = (self.coordinator.data or {}).get("stats", {})
        values = stats.get("monthly_cost_values", [])
        return round(sum(values), 2) if values else None

    @property
    def extra_state_attributes(self) -> dict:
        stats = (self.coordinator.data or {}).get("stats", {})
        return {
            "history": stats.get("monthly_cost_history", []),
            "labels": stats.get("monthly_cost_labels", []),
            "values": stats.get("monthly_cost_values", []),
        }


class FuelioMonthlyPriceSensor(FuelioSensor):
    """Storico del prezzo medio al litro degli ultimi 12 mesi, per grafico a barre."""

    @property
    def native_value(self):
        stats = (self.coordinator.data or {}).get("stats", {})
        values = [v for v in stats.get("monthly_price_values", []) if v is not None]
        return values[-1] if values else None

    @property
    def extra_state_attributes(self) -> dict:
        stats = (self.coordinator.data or {}).get("stats", {})
        return {
            "history": stats.get("monthly_price_history", []),
            "labels": stats.get("monthly_price_labels", []),
            "values": stats.get("monthly_price_values", []),
        }
