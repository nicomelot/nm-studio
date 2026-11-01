# NM Studio – Registro versioni

## 4.2.1

- Corretto il percorso dell'API storico quando Home Assistant è raggiunto attraverso il proxy Supervisor `/core`.
- Test per URL Home Assistant diretto e URL con prefisso Supervisor. Nessuna modifica ai dati o al bus.

## 4.2.0

- Lettura opzionale delle ultime 24 ore di decisioni simulate da Home Assistant Recorder (solo GET sulla singola entità identificata).
- Normalizzazione e deduplicazione degli eventi storici per `decision_id`, senza esporre azioni eseguibili o collegarsi direttamente al Decision Engine.
- Risposta limitata in dimensione e numero di eventi, fallback se Recorder non conserva gli attributi o non è disponibile.
- Interfaccia con storico HA separato dallo storico temporaneo della sessione; nessuna modifica ai dispositivi o ai servizi HA.

## 4.1.0

- Primo contratto dati stabile per NM Intelligence (`contract_version: 1`) con capacità dichiarate e rilevamento del motore dalle sole entità Home Assistant.
- La UI distingue installazione con sola supervisione HA da installazione con Decision Engine simulato, senza richiedere Proxmox o un accesso remoto.
- Storico remoto e comandi dichiarati non disponibili; nessun cambiamento operativo sul bus o sui servizi Home Assistant.

## 4.0.1

- Corretto il numero di versione mostrato nell'intestazione: non rimane più fermo alla 3.9.

## 4.0.0

- Diagnostica dei sei sensori simulati con età dell'ultimo aggiornamento e distinzione fra dato recente, vecchio e timestamp assente.
- Distinzione esplicita fra `last_changed` e `last_updated`: un valore costante non è automaticamente una disconnessione.
- Contesto numerico FV meno consumi (solo con entrambi i dati recenti) e batteria; nessuna inferenza sulle ragioni interne del motore.
- La scheda spiega i limiti della decisione, mantiene il solo storico di sessione e non richiede Proxmox, MQTT diretto o credenziali aggiuntive.
- Invariata la garanzia di sola lettura: nessun comando HA, MQTT o KNX.

## 3.9.0

- Dashboard Intelligence più leggibile: nomi proposte e stati tradotti in italiano, date locali e priorità.
- Lettura opzionale da stati Home Assistant di sei sensori MQTT di simulazione (FV, consumi, batteria, temperatura, umidità e CO₂), con segnalazione dei dati non recenti.
- Storico temporaneo, limitato a otto decisioni viste durante la sessione della pagina; nessun database nuovo e nessuna modifica al Decision Engine.
- Rimangono esclusivamente letture degli stati Home Assistant: niente comandi KNX, MQTT o servizi.

## 3.8.0

- Nuova scheda Intelligence in sola lettura, con stato, proposte, motivazioni e scadenza delle decisioni simulate di un motore esterno.
- Endpoint GET `/intelligence/summary` che usa esclusivamente gli stati dell'istanza Home Assistant già collegata; nessun accesso diretto MQTT.
- Proposte scadute, schemi non validi o decisioni con esecuzione abilitata non vengono mostrate come attive.
- Nessun comando KNX, servizio HA, scrittura su MQTT o modifica ai dati salvati.

## 3.7.0

- Primo rilascio incrementale dal repository GitHub ufficiale.
- Indicatore di versione e canale GitHub visibile nell'interfaccia, per verificare l'aggiornamento da Home Assistant.
- Nessuna modifica ai dati salvati, ai permessi o ai comportamenti KNX/HA: rilascio di collaudo degli aggiornamenti.

## 3.6.0

- Backup esportabile delle cinque configurazioni locali (stanze, widget KNX, dispositivi approvati, note ETS, NM Link).
- Importazione guidata con checksum, validazione e rifiuto di sovrascrivere dati presenti.
- Preparazione al repository GitHub per aggiornamenti nativi di Home Assistant.

## 3.5.0

- Probe sola lettura delle API ufficiali KNX Panel e piano di creazione entità non eseguito.

## 3.4.0

- Wizard di avvio con stato delle sei fasi e revisione dispositivi richiudibile.

## 3.3.0

- Preflight di rilascio e rilevazione di conflitti tra indirizzi KNX.
