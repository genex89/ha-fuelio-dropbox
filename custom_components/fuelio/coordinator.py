"""DataUpdateCoordinator per l'integrazione Fuelio (Dropbox)."""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_REFRESH_TOKEN,
    CONF_FOLDER,
    CONF_FILE_NAME,
    DROPBOX_TOKEN_URL,
    DROPBOX_LIST_FOLDER_URL,
    DROPBOX_DOWNLOAD_URL,
)

_LOGGER = logging.getLogger(__name__)

# Se la cartella "Apps" di Dropbox non viene trovata con il nome localizzato
# (es. "Applicazioni"), riproviamo con il nome interno inglese "Apps", che è
# quello usato a volte dall'API indipendentemente dalla lingua del client.
_APPS_FOLDER_ALIASES = {"applicazioni": "apps", "applications": "apps", "aplicaciones": "apps"}


class FuelioCoordinator(DataUpdateCoordinator):
    """Coordina il download periodico e il parsing del backup Fuelio."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, scan_interval_minutes: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Fuelio",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.entry = entry
        self._session = async_get_clientsession(hass)
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None
        # Controllato dallo switch "Notifiche aggiornamento"
        self.notifications_enabled: bool = True

    async def _async_get_access_token(self) -> str:
        if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._access_token

        data = self.entry.data
        async with self._session.post(
            DROPBOX_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": data[CONF_REFRESH_TOKEN],
                "client_id": data[CONF_APP_KEY],
                "client_secret": data[CONF_APP_SECRET],
            },
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise UpdateFailed(f"Autenticazione Dropbox fallita ({resp.status}): {text}")
            payload = await resp.json()

        self._access_token = payload["access_token"]
        expires_in = payload.get("expires_in", 14400)
        self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 120)
        return self._access_token

    async def _async_list_folder(self, token: str, folder: str) -> list[dict]:
        async with self._session.post(
            DROPBOX_LIST_FOLDER_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"path": folder},
        ) as resp:
            if resp.status == 409:
                # Percorso non trovato: potrebbe essere il problema del nome
                # localizzato della cartella "Apps" -> proviamo l'alias.
                return []
            if resp.status != 200:
                text = await resp.text()
                raise UpdateFailed(f"Errore lettura cartella Dropbox ({resp.status}): {text}")
            payload = await resp.json()
        return payload.get("entries", [])

    async def _async_find_target_file(self, token: str) -> dict:
        folder = self.entry.data.get(CONF_FOLDER, "").rstrip("/")
        file_name = self.entry.data.get(CONF_FILE_NAME, "").strip()

        entries = await self._async_list_folder(token, folder)

        if not entries:
            # Fallback: prova a sostituire il primo segmento localizzato
            # (es. "Applicazioni") con "Apps".
            parts = folder.strip("/").split("/")
            if parts and parts[0].lower() in _APPS_FOLDER_ALIASES:
                alt_folder = "/" + "/".join([_APPS_FOLDER_ALIASES[parts[0].lower()]] + parts[1:])
                entries = await self._async_list_folder(token, alt_folder)

        if not entries:
            raise UpdateFailed(
                f"Nessun file trovato nella cartella Dropbox '{folder}'. "
                "Verifica il percorso nella configurazione dell'integrazione."
            )

        zip_files = [e for e in entries if e.get("name", "").lower().endswith(".zip")]
        if not zip_files:
            raise UpdateFailed(f"Nessun file .zip trovato nella cartella '{folder}'")

        if file_name:
            matches = [e for e in zip_files if e.get("name") == file_name]
            if not matches:
                raise UpdateFailed(
                    f"File '{file_name}' non trovato nella cartella '{folder}'"
                )
            return matches[0]

        zip_files.sort(key=lambda e: e.get("server_modified", ""), reverse=True)
        return zip_files[0]

    async def _async_download(self, token: str, path_lower: str) -> bytes:
        async with self._session.post(
            DROPBOX_DOWNLOAD_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Dropbox-API-Arg": f'{{"path": "{path_lower}"}}',
            },
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise UpdateFailed(f"Errore download file Dropbox ({resp.status}): {text}")
            return await resp.read()

    async def _async_update_data(self) -> dict:
        token = await self._async_get_access_token()
        target = await self._async_find_target_file(token)
        raw_zip = await self._async_download(token, target["path_lower"])

        content = await self.hass.async_add_executor_job(_extract_csv_from_zip, raw_zip)
        vehicle_info, fillups = await self.hass.async_add_executor_job(_parse_fuelio_csv, content)

        if not fillups:
            raise UpdateFailed("Il backup Fuelio non contiene rifornimenti")

        stats = await self.hass.async_add_executor_job(_compute_stats, fillups)
        stats["last_update_timestamp"] = datetime.now(timezone.utc)
        return {
            "vehicle": vehicle_info,
            "fillups": fillups,
            "stats": stats,
            "file_name": target["name"],
        }


def _extract_csv_from_zip(raw_zip: bytes) -> str:
    """Estrae il primo CSV contenuto nello zip scaricato da Dropbox."""
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise UpdateFailed("Lo zip di Fuelio non contiene nessun file .csv")
        with archive.open(csv_names[0]) as fh:
            return fh.read().decode("utf-8-sig")


def _to_float(value) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _parse_fuelio_csv(content: str) -> tuple[dict, list[dict]]:
    """Interpreta un backup Fuelio (sezioni '## Vehicle' e '## Log')."""
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    vehicle_header: list[str] = []
    vehicle_data: list[str] = []
    log_header: list[str] = []
    log_rows: list[list[str]] = []
    section = None

    for row in rows:
        if not row:
            continue
        first = row[0].strip()
        if first == "## Vehicle":
            section = "vehicle_header"
            continue
        if first == "## Log":
            section = "log_header"
            continue
        if section == "vehicle_header":
            vehicle_header = row
            section = "vehicle_data"
            continue
        if section == "vehicle_data":
            vehicle_data = row
            section = None
            continue
        if section == "log_header":
            log_header = row
            section = "log_data"
            continue
        if section == "log_data":
            log_rows.append(row)

    vehicle_info = dict(zip(vehicle_header, vehicle_data))

    fillups: list[dict] = []
    for row in log_rows:
        if len(row) != len(log_header):
            continue
        raw = dict(zip(log_header, row))
        date_str = raw.get("Data")
        date = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                date = datetime.strptime(date_str, fmt)
                break
            except (TypeError, ValueError):
                continue
        if date is None:
            continue

        raw_city = raw.get("City (optional)") or ""
        if " - " in raw_city:
            city_part, station_part = raw_city.split(" - ", 1)
        else:
            city_part, station_part = raw_city, raw_city

        fillups.append(
            {
                "date": date,
                "odometer": _to_float(raw.get("Odo (km)")),
                "liters": _to_float(raw.get("Fuel (litres)")),
                "full": raw.get("Full") == "1",
                # "Price (optional)" e' il costo TOTALE del rifornimento
                "cost": _to_float(raw.get("Price (optional)")),
                "consumption": _to_float(raw.get("l/100km (optional)")),
                # "VolumePrice" e' il prezzo al litro
                "price_per_liter": _to_float(raw.get("VolumePrice")),
                "city": city_part.strip(),
                "station_name": station_part.strip() or None,
                "latitude": _to_float(raw.get("latitude (optional)")),
                "longitude": _to_float(raw.get("longitude (optional)")),
                "station_id": raw.get("StationID (optional)"),
            }
        )

    fillups.sort(key=lambda f: f["date"])
    return vehicle_info, fillups


_MONTH_LABELS_IT = [
    "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
    "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
]


def _last_12_months(reference: datetime) -> list[tuple[int, int]]:
    """Restituisce le ultime 12 coppie (anno, mese), dalla piu' vecchia alla piu' recente."""
    months: list[tuple[int, int]] = []
    year, month = reference.year, reference.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def _compute_stats(fillups: list[dict]) -> dict:
    """Calcola le statistiche derivate, incluse quelle mensili/annuali."""
    now = datetime.now()
    cur_year, cur_month = now.year, now.month
    if cur_month == 1:
        prev_month_year, prev_month = cur_year - 1, 12
    else:
        prev_month_year, prev_month = cur_year, cur_month - 1

    monthly_totals: dict[tuple[int, int], float] = {}
    monthly_liters: dict[tuple[int, int], float] = {}
    total_cost = 0.0
    total_liters = 0.0

    for f in fillups:
        cost = f["cost"] or 0.0
        liters = f["liters"] or 0.0
        total_cost += cost
        total_liters += liters
        key = (f["date"].year, f["date"].month)
        monthly_totals[key] = monthly_totals.get(key, 0.0) + cost
        monthly_liters[key] = monthly_liters.get(key, 0.0) + liters

    avg_monthly_cost = (
        round(sum(monthly_totals.values()) / len(monthly_totals), 2) if monthly_totals else None
    )

    current_month_cost = round(monthly_totals.get((cur_year, cur_month), 0.0), 2)
    previous_month_cost = round(monthly_totals.get((prev_month_year, prev_month), 0.0), 2)

    current_year_cost = round(
        sum(cost for (y, _m), cost in monthly_totals.items() if y == cur_year), 2
    )
    previous_year_cost = round(
        sum(cost for (y, _m), cost in monthly_totals.items() if y == cur_year - 1), 2
    )

    # Storico 12 mesi per i grafici a barre (costo totale e prezzo medio al litro)
    last_12 = _last_12_months(now)
    monthly_cost_history = []
    monthly_price_history = []
    for (year, month) in last_12:
        key = (year, month)
        month_cost = round(monthly_totals.get(key, 0.0), 2)
        month_liters = monthly_liters.get(key, 0.0)
        month_avg_price = round(month_cost / month_liters, 3) if month_liters > 0 else None
        month_label = f"{_MONTH_LABELS_IT[month - 1]} {year}"
        iso_month = f"{year:04d}-{month:02d}"

        monthly_cost_history.append({"month": iso_month, "label": month_label, "cost": month_cost})
        monthly_price_history.append(
            {"month": iso_month, "label": month_label, "price_per_liter": month_avg_price}
        )

    last = fillups[-1]

    maps_url = None
    if last.get("latitude") is not None and last.get("longitude") is not None:
        maps_url = (
            f"https://www.google.com/maps/search/?api=1"
            f"&query={last['latitude']},{last['longitude']}"
        )

    return {
        "last_fillup_date": last["date"].strftime("%Y-%m-%d %H:%M"),
        "last_odometer": last["odometer"],
        "last_liters": last["liters"],
        "last_cost": last["cost"],
        "last_price_per_liter": last["price_per_liter"],
        "last_consumption": last["consumption"],
        "last_station_name": last.get("station_name") or "Sconosciuto",
        "last_station_city": last.get("city"),
        "last_latitude": last.get("latitude"),
        "last_longitude": last.get("longitude"),
        "last_maps_url": maps_url,
        "total_fillups": len(fillups),
        "total_liters": round(total_liters, 2),
        "total_cost": round(total_cost, 2),
        "avg_monthly_cost": avg_monthly_cost,
        "current_month_cost": current_month_cost,
        "previous_month_cost": previous_month_cost,
        "current_year_cost": current_year_cost,
        "previous_year_cost": previous_year_cost,
        "monthly_cost_history": monthly_cost_history,
        "monthly_cost_labels": [m["label"] for m in monthly_cost_history],
        "monthly_cost_values": [m["cost"] for m in monthly_cost_history],
        "monthly_price_history": monthly_price_history,
        "monthly_price_labels": [m["label"] for m in monthly_price_history],
        "monthly_price_values": [m["price_per_liter"] for m in monthly_price_history],
    }
