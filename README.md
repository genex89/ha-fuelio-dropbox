# Fuelio (Dropbox) per Home Assistant

Integrazione custom non ufficiale che legge i backup CSV generati da
[Fuelio](https://www.fuel.io) e sincronizzati automaticamente su Dropbox,
e li trasforma in sensori Home Assistant: costi, consumi, storico mensile,
distributore dell'ultimo rifornimento con link diretto a Google Maps.

Non serve nessuna app esterna, nessun cron, nessuno script: tutto avviene
dentro Home Assistant, con configurazione guidata dall'interfaccia.

## Indice

- [Funzionalità](#funzionalità)
- [Requisiti](#requisiti)
- [Installazione via HACS](#installazione-via-hacs)
- [Installazione manuale](#installazione-manuale)
- [Configurazione](#configurazione)
- [Sensori creati](#sensori-creati)
- [Pulsante di aggiornamento forzato](#pulsante-di-aggiornamento-forzato)
- [Dashboard e grafici](#dashboard-e-grafici)
- [Limitazioni note](#limitazioni-note)
- [Licenza e disclaimer](#licenza-e-disclaimer)

## Funzionalità

- **Config flow guidato**: inserisci solo App Key e App Secret Dropbox, poi
  apri un link, autorizzi ed incolli un codice — l'integrazione genera da
  sola il refresh token, niente `curl` o copia-incolla di JSON.
- **Estrazione automatica**: trova da sola il file `.zip` più recente nella
  cartella di sync Fuelio su Dropbox e lo estrae (nessuna dipendenza esterna,
  usa solo la libreria standard di Python).
- **Nome dispositivo configurabile**: scegli tu il prefisso di tutti i
  sensori (es. `sensor.captur_...` invece di un nome fisso).
- **14+ sensori**: ultimo rifornimento (data, km, litri, costo, prezzo/litro,
  consumo, distributore con link Maps), totali, medie e confronti mensili/annuali.
- **Storico 12 mesi** pronto per grafici a barre (costi e prezzo medio al litro).
- **Pulsante di aggiornamento forzato**, con notifica di conferma o errore.

## Requisiti

| Cosa | Obbligatorio? | Note |
|---|---|---|
| Home Assistant 2026.3 o superiore | Consigliato | Per le icone locali dell'integrazione. Con versioni precedenti funziona comunque, solo senza icona personalizzata. |
| Un'app Dropbox personale (gratuita) | **Sì** | Serve per leggere il file che Fuelio salva. Vedi guida di configurazione. |
| [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (via HACS → Frontend) | Solo per i grafici a barre | Le entità/sensori funzionano comunque senza; senza questa card non hai le card grafiche 1 e 2, ma il resto dell'integrazione è indipendente. |

## Installazione via HACS

1. Apri **HACS** → icona **⋮** in alto a destra → **Repository personalizzati**.
2. Incolla l'URL di questo repository GitHub.
3. Categoria: **Integrazione** → **Aggiungi**.
4. Cerca **"Fuelio"** dentro HACS → **Scarica/Installa**.
5. **Riavvia Home Assistant** (riavvio completo, non "ricarica").
6. Prosegui con la [Configurazione](#configurazione).

## Installazione manuale

1. Scarica questo repository (Code → Download ZIP, oppure `git clone`).
2. Copia la cartella `custom_components/fuelio` dentro
   `/config/custom_components/` della tua installazione Home Assistant.
3. **Riavvia Home Assistant**.
4. Prosegui con la [Configurazione](#configurazione).

## Configurazione

Riepilogo rapido (dettagli completi con screenshot testuali e troubleshooting
nella `GUIDA_installazione.md` allegata):

1. Crea un'app su https://www.dropbox.com/developers/apps con accesso
   **Full Dropbox** e permessi `files.metadata.read` + `files.content.read`.
2. In Home Assistant: **Impostazioni → Dispositivi e servizi → Aggiungi
   integrazione → Fuelio**.
3. Primo step: App Key, App Secret, nome dispositivo, cartella Dropbox
   (default `/Applicazioni/Fuelio/sync`), nome file specifico (opzionale),
   intervallo di aggiornamento.
4. Secondo step: apri il link mostrato, autorizza, incolla il codice.
5. Fatto — compaiono dispositivo e sensori.

## Sensori creati

| Entità (esempio con nome dispositivo "Captur") | Descrizione |
|---|---|
| `sensor.captur_data_ultimo_rifornimento` | Data ultimo rifornimento |
| `sensor.captur_ultimo_chilometraggio` | Km ultimo rifornimento |
| `sensor.captur_litri_ultimo_rifornimento` | Litri ultimo rifornimento |
| `sensor.captur_costo_ultimo_rifornimento` | Costo (€) ultimo rifornimento |
| `sensor.captur_prezzo_al_litro_ultimo_rifornimento` | Prezzo al litro (€/L) |
| `sensor.captur_consumo_ultimo_rifornimento` | Consumo (L/100km) |
| `sensor.captur_distributore_ultimo_rifornimento` | Nome distributore (attributi: città, lat/long, link Maps) |
| `sensor.captur_numero_rifornimenti_totali` | Numero totale rifornimenti nel backup |
| `sensor.captur_litri_totali` | Litri totali |
| `sensor.captur_spesa_totale_carburante` | Spesa totale carburante |
| `sensor.captur_costo_medio_rifornimenti_mensili` | Media della spesa mensile |
| `sensor.captur_costo_rifornimenti_mese_in_corso` | Spesa nel mese corrente |
| `sensor.captur_costo_rifornimenti_mese_precedente` | Spesa nel mese precedente |
| `sensor.captur_costo_rifornimenti_anno_in_corso` | Spesa nell'anno corrente |
| `sensor.captur_costo_rifornimenti_anno_precedente` | Spesa nell'anno precedente |
| `sensor.captur_andamento_costi_mensili_12_mesi` | Storico costi mensili (attributo `history`), per grafico |
| `sensor.captur_andamento_prezzo_al_litro_mensile_12_mesi` | Storico prezzo/litro mensile (attributo `history`), per grafico |
| `button.captur_aggiorna_dati` | Forza il refresh immediato, con notifica di esito |

## Pulsante di aggiornamento forzato

Il pulsante **"Aggiorna dati"** esegue un refresh immediato (non aspetta
l'intervallo configurato) e mostra una **notifica persistente** in Home
Assistant con l'esito:
- ✅ `Dati aggiornati con successo (file: ...)`
- ❌ `Aggiornamento fallito: <dettaglio errore>` — utile per capire subito se
  il problema è di autenticazione Dropbox, percorso file, o altro.

## Dashboard e grafici

I due grafici a barre (costo mensile e prezzo/litro mensile) **richiedono**
la card **ApexCharts Card**, non inclusa in Home Assistant di default:

1. **HACS → Frontend** → cerca **"ApexCharts Card"** → **Installa**.
2. Ricarica la pagina del browser (Ctrl/Cmd + Shift + R) perché HA carichi
   la nuova risorsa frontend.
3. Verifica che sia attiva: se in **Impostazioni → Dashboard → Risorse** non
   la vedi elencata automaticamente, aggiungila a mano con URL
   `/hacsfiles/apexcharts-card/apexcharts-card.js`, tipo **Modulo JavaScript**.

Il file `lovelace_cards.yaml` allegato contiene 4 card pronte:

| # | Card | Dipendenza |
|---|---|---|
| 1 | Grafico a barre — costo mensile (12 mesi) | ApexCharts Card |
| 2 | Grafico a barre — prezzo al litro mensile (12 mesi) | ApexCharts Card |
| 3 | Card statistiche (entities) | Nessuna (nativa) |
| 4 | Link Google Maps distributore (markdown) | Nessuna (nativa) |

Come usarle: apri una view in modalità **Modifica in YAML**, incolla il
contenuto di `lovelace_cards.yaml` dentro `cards:`, sostituisci `captur` con
lo slug del tuo dispositivo reale (Impostazioni → Dispositivi e servizi →
Fuelio → apri il dispositivo per vedere gli ID esatti).

I grafici funzionano leggendo l'attributo `history` dei due sensori dedicati
(non la cronologia realtime di Home Assistant), quindi mostrano subito tutti
i 12 mesi anche appena installata l'integrazione, senza dover aspettare che
HA accumuli dati nel tempo.

## Limitazioni note

- Un file `.zip` per veicolo: se sincronizzi più veicoli nella stessa
  cartella Dropbox, imposta il campo "Nome file specifico" nel config flow e
  crea un'integrazione separata per ciascun veicolo.
- I calcoli (medie, storico mensile) riflettono fedelmente i dati presenti
  nel CSV di Fuelio: eventuali errori di inserimento nell'app (es. virgola
  al posto del punto decimale) si propagano nei sensori. Usa il pulsante di
  aggiornamento dopo aver corretto un dato in Fuelio per vederlo subito
  riflesso.

## Licenza e disclaimer

Progetto personale/non ufficiale, nessuna affiliazione con Fuelio o Dropbox.
I rispettivi nomi e marchi appartengono ai legittimi proprietari. L'icona
inclusa è un disegno originale, non una riproduzione dei loghi ufficiali.
