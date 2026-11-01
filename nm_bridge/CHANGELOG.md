# NM Studio – Registro versioni

## 4.7.1

- Le nuove plance HA contengono solo Tile native collegate a entità effettivamente presenti: i widget ancora non associati compaiono nel rapporto di configurazione, non come card fittizie.
- Comandi apri/chiudi nativi per tapparelle collegate a `cover.*`; supporto Tile per sensori e clima nei widget compatibili.
- Vietata la pubblicazione di una dashboard con zero entità operative. Restano obbligatorie conferma esplicita e protezione delle dashboard esistenti.
- La creazione delle entità KNX e l'attivazione dei collegamenti NM Link non sono ancora automatiche: richiedono il prossimo collaudo con istanza HA dotata dell'integrazione pertinente.

## 4.7.0

- Nuova area installatore «Mappe impianto»: più planimetrie, livelli tecnici KNX, DALI, prese dati, Wi-Fi, video, clima e rack.
- Caricamento locale di immagini PNG/JPEG e SVG rasterizzato nel browser prima del salvataggio; backend accetta solo PNG/JPEG verificando firma e dimensione (2 MB per sfondo).
- Punti posizionabili trascinandoli, etichette, zoom e filtro livelli con coordinate percentuali indipendenti dal disegno.
- Archivio JSON separato in `/data`, validato e salvato esplicitamente; nessuna associazione live, modifica HA, comando bus o accesso alla rete UniFi.
- L'archivio delle mappe non è ancora incluso nel vecchio backup di migrazione: migrazione da aggiornare prima del rilascio operativo.

## 4.6.0

- Ruoli di sensori logici associati alle entità Home Assistant, con conferma manuale distinta dalla semplice selezione.
- Compatibilità con i piani esistenti; la verifica viene revocata nella UI quando cambia l'entità selezionata.
- Ricerca dei suggerimenti già all'apertura del wizard e anteprima in sola lettura dei valori delle associazioni salvate.
- Indicazione prudente «SIM probabile» dai nomi e origine da verificare: non vengono inferiti dati reali da valori simulati.
- Nessuna creazione di entità, applicazione di YAML, comando su HA o telegramma KNX.

## 4.5.1

- Suggerimenti HA meno restrittivi: un sensore con nome e dominio compatibili ma unità non dichiarata viene mostrato come candidato da verificare.
- Unità esplicitamente incompatibili (ad esempio kWh per una misura in W) continuano a essere escluse.
- Il wizard indica quante entità sono state esaminate e ricorda che le unità mancanti richiedono verifica manuale.

## 4.5.0

- Ricerca assistita dei candidati Home Assistant per KNX, FV, scambio rete, batteria e climatizzazione.
- Suggerimenti basati esclusivamente su dominio, nome, unità di misura e disponibilità dello stato: non equivalgono a verifica dell'integrazione o dell'impianto.
- Selezione manuale da menu a tendina e salvataggio esplicito degli `entity_id` nel piano moduli locale; mantiene compatibilità con i piani 4.4.
- Nessuna entità creata, nessuna spunta automatica, nessuna chiamata di servizio Home Assistant o comando KNX.

## 4.4.0

- Catalogo guidato per i moduli KNX/ETS, fotovoltaico e climatizzazione direttamente nell'Avvio guidato.
- Checklist e note per l'installatore, persistenti in un file JSON locale con validazione e salvataggio esplicito.
- Consigli sui requisiti (Functions ETS, GA/DPT, integrazione HA, dati FV/accumulo, stati PDC); nessun controllo dell'impianto né attivazione automatica.
- Il piano moduli è una nuova sezione locale: l'esportazione/migrazione esistente non lo include ancora.

## 4.3.0

- Storico Recorder adattivo: prova 24, 6 e 1 ora, riducendo la finestra soltanto se la risposta supera 2 MB.
- Mantiene il limite di lettura per richiesta, segnala l'intervallo effettivo e non usa credenziali aggiuntive.
- Lettura opzionale e nessun effetto sull'impianto KNX o sulle automazioni Home Assistant.

## 4.2.2

- Diagnostica di lettura Recorder: distingue HTTP, risposta oltre 2 MB, JSON non valido e formato inatteso senza esporre token o dati grezzi.
- Il dettaglio appare nell'interfaccia Intelligence; nessun cambiamento ai sistemi esterni.

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
