# NM Bridge — prototype 0.1

## NM Studio 3.5 — Preparazione KNX Panel ufficiale (read-only)

In **Genera HA** puoi verificare se l'API WebSocket del pannello KNX di Home Assistant è disponibile con gli attuali permessi dell'add-on e preparare un piano strutturato di chiamate `knx/create_entity` da dispositivi esplicitamente verificati. Il controllo usa esclusivamente `knx/get_base_data` e `knx/get_entities_by_group` (sole letture); il piano si limita a generare JSON, non esegue chiamate di creazione. Le API KNX Panel richiedono privilegi amministratore e un'integrazione KNX configurata; in laboratorio può risultare non disponibile. Le posizioni delle tapparelle non confermate non sono convertite in comandi. **Non vengono alzati i permessi dell'add-on, creati dispositivi, modificati file HA o inviati telegrammi KNX.**

## NM Studio 3.4 — Avvio guidato (beta)

Nuova pagina iniziale **Avvio guidato** con sei fasi: import ETS, edificio, widget, generazione entità HA, associazione entità e plance Lovelace. Le fasi mostrano lo stato dai dati già salvati e aprono i rispettivi strumenti senza nascondere controlli tecnici o sovrascrivere configurazioni. Il conteggio rappresenta la preparazione, non l'attivazione dell'impianto. Le schede nella revisione delle entità sono ora richiudibili, riducendo lo scorrimento. Il preflight distingue esplicitamente **assenza di blocchi rilevati** dalla **verifica manuale sempre necessaria** per gli indirizzi KNX che l'inventario HA non espone. Nessuna attivazione automatica o telegramma KNX.

## NM Studio 3.3 — Preflight di rilascio, senza attivazione

In **Genera HA** una bozza esplicitamente approvata può essere sottoposta al controllo **Controlla possibili conflitti**. Il backend confronta i GA di comando tra i widget approvati e quelli salvati, individua nomi HA simili nell'inventario corrente, distingue blocchi da avvisi e produce un piano JSON con YAML e checklist di backup, validazione e ripristino. Il controllo è invalidato se cambiano widget, selezione o YAML manualmente. L'inventario degli stati HA non permette di ispezionare tutti i GA eventualmente già configurati: perciò il sistema segnala sempre la necessità di una verifica manuale. **Non viene scritto alcun file di Home Assistant, non vengono create entità o inviate azioni KNX.**

## NM Studio 3.2 — Revisione visuale dei dispositivi KNX

Nel generatore **Genera HA → Genera solo mancanti** compare una revisione per dispositivo: nome e indirizzi gruppo modificabili, tipo visibile e spunta **Verificato in ETS**. Il pulsante **Genera YAML approvato** invia la sola selezione al generatore in lettura: verifica i dati tramite lo schema dei widget e produce una bozza che include esclusivamente i dispositivi spuntati. Lo stato salvato dei widget, la configurazione Home Assistant e il bus KNX non vengono modificati. Il riquadro YAML ora occupa tutta la larghezza disponibile. La procedura di applicazione sicura e guidata alle entità HA sarà una fase successiva.

## NM Studio 3.1 — Bozza automatica per entità KNX mancanti

Nella scheda **Genera HA** è disponibile **Genera solo mancanti**: usa i widget ETS confermati e genera YAML KNX per i widget senza associazioni HA. I widget con entità HA già associata, presente o non presente negli stati correnti, sono esclusi per evitare duplicazioni accidentali. Sono presentate le verifiche richieste sui GA/DPT. Poiché il solo inventario HA non rivela tutti gli indirizzi già configurati, il file deve essere controllato prima di essere importato nella configurazione KNX esistente. **Nessun file HA viene applicato, nessuna entità creata e nessun comando KNX inviato** in questa versione. È una fase intermedia verso una procedura guidata con anteprima e conferma esplicita.

## NM Studio 3.0 — Associazione intelligente

La nuova scheda **Associa entità** legge i widget ETS già confermati e l'inventario Home Assistant, confronta nomi e domini (luce, dimmer, tapparella) e propone collegamenti con indicazione della confidenza. L'installatore può scegliere un'entità dal menu o lasciare il collegamento vuoto, quindi deve confermare esplicitamente il salvataggio. Vengono conservati GA, stanze, struttura e impostazioni degli altri widget. Nessun servizio Home Assistant né telegramma KNX viene inviato. La plancia si aggiorna solo rigenerandone l'anteprima in **Plance HA**; le dashboard esistenti non vengono sovrascritte.

Read-only discovery app for Home Assistant OS. It provides an authenticated Ingress page listing current light, cover, switch, climate, sensor and binary_sensor states. It does **not** access the KNX bus directly, send commands, expose a host port, or send data to the hosted NM Studio website.

## Status

- Source prototype only: not yet tested inside Home Assistant OS.
- Supervisor API access is requested using the add-on's `SUPERVISOR_TOKEN`, never stored in a config file.
- Ingress controls access; the internal server only accepts the Supervisor ingress proxy at `172.30.32.2`.
- No external network connection is initiated except to the local Supervisor API.
- Do not install on any live customer system until the package has passed a staging installation and a backup exists.

## Planned installation

1. Host this directory as a Home Assistant add-on repository, updating `repository.yaml` to the actual repository URL.
2. Add the repository in Home Assistant Settings → Apps → App store → Repositories.
3. Install **NM Bridge (read-only laboratory)**; inspect permissions before starting.
4. Start the app and open its Web UI through Home Assistant.
5. Verify the inventory; no credentials are entered into NM Bridge.

## Integration roadmap

1. Read-only live state inventory (this version, refresh button).
2. Server-side pairing against ETS import with an explicit approval step.
3. Event-stream changes, audit logs and diagnostics.
4. Scoped command execution after dedicated authorization and live tests.
5. Per-customer remote service with separate identity and tunnel protections.

## Development safety

Never put a long-lived Home Assistant token in the browser or the hosted static NM Studio app. Keep the bridge local and authenticated. Do not enable external access to the add-on's internal port.
# NM Bridge 2.9.0 — Pubblicazione guidata di nuove plance HA

La scheda Plance HA permette, dopo generazione di anteprima e conferma esplicita, di **creare una nuova dashboard Home Assistant** tramite il proxy WebSocket del Supervisor (`lovelace/dashboards/list`, `.../create`, `lovelace/config/save`). Non modifica dashboard esistenti e rifiuta percorsi già presenti. I percorsi ammessi iniziano per `nm-studio-`; la bozza deve avere un'impronta corrispondente all'anteprima appena verificata. Una lettura di controllo della configurazione è eseguita dopo il salvataggio. Il nuovo pacchetto richiede la libreria Alpine `py3-websocket-client`.

**Attenzione:** la pubblicazione modifica Home Assistant creando una dashboard. Non attiva NM Link, non crea entità né invia comandi KNX; tuttavia le schede Tile di entità reali restano interattive in HA. Testare nel laboratorio. Se Home Assistant rifiuta i permessi, la pubblicazione fallisce senza cambiare la configurazione dell'add-on. Se la creazione riesce ma il successivo salvataggio fallisce, la dashboard vuota potrebbe rimanere: l'app indica il percorso, senza cancellare o sovrascrivere automaticamente alcunché. È sempre disponibile l'esportazione manuale.

## Precedente 2.8.2 — Migliorie interfaccia Plance HA

Il riquadro della configurazione Lovelace usa ora tutta la larghezza disponibile. Il pulsante Copia prova anche il metodo di selezione/copia compatibile con i browser in contesto HTTP; quando la copia automatica è impedita dal browser lascia il testo selezionato e indica di premere Ctrl+C. L'esportazione JSON resta disponibile e consigliata come alternativa. Nessun cambiamento alle associazioni o all'accesso a HA/KNX.

## Precedente 2.8.1 — Correzione avvio generatore plance

Corretto il Dockerfile: include ora `lovelace_generator.py` nell'immagine dell'add-on. La 2.8.0 poteva terminare all'avvio con `ModuleNotFoundError` benché i test Python locali passassero. Nessuna migrazione dati e nessuna reinstallazione necessaria: aggiornare i file locali, ricostruire l'immagine e avviare l'app. Aggiunto un test che verifica tutte le dipendenze Python locali dichiarate negli import del bridge.

## Precedente 2.8.0 — Generatore plance Home Assistant

Nuova pagina **Plance HA**: genera una configurazione Lovelace nativa `sections` per una nuova dashboard gestita dall'interfaccia di Home Assistant. Utilizza soltanto la struttura e i widget KNX salvati in NM Studio, associati alle entità HA attualmente disponibili. Ogni widget con entità reale di dominio compatibile produce una scheda `tile`; ogni widget incompleto o non trovato produce un segnaposto `markdown` inattivo con motivo visibile. Sono disponibili anteprima, report associazioni mancanti, copia ed esportazione JSON (formato compatibile con la sintassi YAML della configurazione grezza Lovelace).

**Nessuna modifica viene applicata automaticamente a Home Assistant.** L'installatore deve creare una dashboard nuova, aprirne l'editor configurazione grezza e incollare la bozza. Dopo il salvataggio potrà personalizzare le schede native con l'editor visuale. Attenzione: le schede Tile che puntano a entità HA reali possono consentire azioni quando si apre la dashboard importata; verificare preventivamente le associazioni e non eseguire la prova su un impianto in produzione senza autorizzazione. La bozza non crea entità, non invia telegrammi e non sovrascrive plance esistenti.

## Precedente 2.7.0 — Comandi guidati e diagnostica NM Link

Il laboratorio virtuale ora propone valori selezionabili dal menu in base al DPT (ON/OFF, Su/Giù, passi di dimmerazione, scene 0–63 e modalità HVAC). Per i DPT numerici, testo e colori rimane un campo libero precompilato dove utile. I controlli per associazione mostrano avvisi, DPT e possibili entità HA coerenti con il dominio; si tratta di suggerimenti da verificare, mai di associazioni applicate automaticamente.

La simulazione delle due direzioni KNX ↔ HA resta esclusivamente ipotetica: nessun servizio Home Assistant e nessun telegramma KNX viene inviato. Tutte le bozze sono inattive e vanno confermate esplicitamente per essere salvate.

## Precedente 2.6.1 — Laboratorio virtuale NM Link

La simulazione NM Link offre ora una **modalità virtuale esplicita** per provare collegamenti KNX → HA anche quando mancano le entità reali. Selezionando il laboratorio virtuale, `POST /nm-link/simulate` riceve `virtual_target: true` e costruisce un identificativo fittizio come `light.nm_virtual_test`: **non** crea un'entità in Home Assistant. Nella pagina viene visualizzato uno stato temporaneo del dispositivo (accensione, luminosità, posizione tapparella o scena). Lo stato è conservato soltanto nella sessione della pagina, non in Home Assistant.

La modalità virtuale mantiene i blocchi per possibili loop, duplicati e scrittori multipli. Non esegue servizi HA, non invia telegrammi KNX e non abilita alcun collegamento. La simulazione dei dimmer a passi è illustrativa, non una riproduzione completa del comportamento reale di pressione e rilascio. Per provarla: bozza KNX → HA, funzione `Dimmerazione relativa`, DPT `3.007`, entità HA vuota, `Simula e verifica`, laboratorio virtuale attivo, quindi campione `up:3`.

## Precedente 2.6.0 — Motore delle funzioni KNX

NM Link distingue finalmente **DPT**, **funzione interpretata** e **azione ipotetica**. Le prime funzioni esplicite per KNX → HA sono:

- Commutazione DPT 1.001 → `light/switch.turn_on` o `turn_off` (sempre e solo simulato).
- Movimento tapparella DPT 1.008 → `cover.open_cover` per UP=0 e `cover.close_cover` per DOWN=1; direzione/inversione da verificare in ETS.
- Dimmerazione relativa DPT 3.007 → stima di un singolo passo `light.turn_on` con `brightness_step_pct`; il rilascio/STOP non viene tradotto in un'azione ingannevole. Il comportamento di pressione prolungata necessita di un adattatore con stato e un collaudo reale.
- Richiamo scena DPT 17.001 → `scene.turn_on` **solo** quando il numero logico 0..63 corrisponde al numero esplicitamente configurato.

La nuova scelta di funzione e l'eventuale numero scena vengono salvati nelle bozze. Le versioni precedenti migrano a `function: auto` senza attivazione. DPT e domini HA incompatibili sono rifiutati. Queste azioni sono soltanto spiegazioni JSON dell'esito ipotetico e non vengono mai eseguite. Nessun messaggio sul bus, nessun listener KNX e nessuna modifica alla configurazione HA.

## Precedente 2.5.0 — Registro DPT estensibile

NM Link utilizza ora un registro di 19 DPT selezionabili, tra le famiglie 1, 5–9, 12–14, 16–17, 20, 232 e 251. Il motore valida esempi logici booleani, numerici, ASCII, scene e colori RGB/RGBW in entrambe le direzioni. Le bozze precedenti con il solo `value_type` vengono migrate in memoria al DPT equivalente e salvate con il nuovo campo `dpt` senza perdere le associazioni. Se un valore KNX non ha una corrispondenza sicura con un servizio HA, la simulazione produce solo una descrizione evento (`ha_event_only`), non una chiamata.

Non vengono codificati o trasmessi APDU KNX; intervalli e categorie del registro sono indicativi e **non sostituiscono** verifica del DPT reale in ETS, né conversioni di precisione della libreria KNX. I DPT complessi e quelli proprietari verranno estesi in modo verificabile nelle prossime iterazioni. Le bozze restano inattive.

## Precedente 2.4.0 — Motore di simulazione NM Link

La scheda NM Link consente ora di testare eventi fittizi sulle bozze validate. Il backend `POST /nm-link/simulate` riceve un collegamento e un valore di esempio, senza contattare né KNX né Home Assistant: per KNX → HA mostra il servizio `turn_on`/`turn_off` che sarebbe richiesto; per HA → KNX mostra GA, DPT atteso e valore logico che sarebbe inviato. Non produce telegrammi binari e non esegue azioni. Blocca simulazioni con entità mancanti, duplicati e potenziali cicli/mittenti multipli. Valida booleani, percentuali 0–100 e temperature -50..100; rifiuta valori non numerici, infiniti o fuori intervallo.

Il risultato è puramente illustrativo: la direzione effettiva degli oggetti ETS, il DPT preciso, i permessi delle entità HA e i feedback devono essere verificati prima di sviluppare un motore operativo. Le bozze rimangono sempre inattive e non è disponibile un comando di attivazione.

## Precedente 2.3.1 — Bozze NM Link senza entità HA

Nel laboratorio Home Assistant possono non esistere ancora entità `light` o `switch` (per esempio perché la configurazione KNX non è stata applicata). NM Link consente ora di lasciare l'`entity_id` **vuoto** e salvare una bozza incompleta, con avviso esplicito `missing_ha_target`. Non inventa entità HA, non abilita il collegamento e non crea servizi o automazioni. La scheda segnala l'assenza di luci/interruttori in inventario.

## Precedente 2.3.0 — NM Link, laboratorio bidirezionale

La nuova scheda **NM Link** salva bozze di collegamento fra indirizzi di gruppo KNX ed entità Home Assistant. Per ogni bozza l'installatore sceglie direzione, GA, entità e tipo di valore. L'anteprima effettua controlli di struttura, segnala duplicati, più mittenti sullo stesso GA, possibili loop bidirezionali e DPT attesi ancora da verificare.

Per KNX → HA la prima bozza ammette soltanto valori booleani destinati a `light` o `switch`. Per HA → KNX sono ammessi booleano, percentuale e temperatura, ma il mapping dei valori **non viene eseguito**. Il backend rifiuta sempre `enabled: true`: nessun motore di automazione, nessuna chiamata a servizi HA, nessun invio o ascolto telegrammi KNX. Un futuro rilascio richiederà collaudo, protezione dai cicli e autorizzazione esplicita per le scritture.

Endpoint: `GET /nm-link`, `POST /nm-link/preview` (analisi senza persistenza), `POST /nm-link` (salvataggio solo con `confirm:true`); file atomico `/data/nm_link_drafts.json`, incluso nel backup locale. Non sostituisce ETS né modifica altri file HA.

## Precedente 2.2.3 — Analisi dimensioni oggetti KNX

Il generatore può ora confrontare la dimensione degli oggetti KNX **effettivamente collegati** esposti dall'importatore ETS con quella attesa dall'associazione (`1 bit` per on/off e movimento/stop, `1 byte` per luminosità assoluta). Se il DPT del GA non è dichiarato ma gli oggetti decodificati sono coerenti, la verifica risulta **compatibile** (azzurro), non **verificata** (verde). Dimensioni discordanti producono un avviso esplicito. Oggetti senza dimensione decodificata non costituiscono prova. Resta necessario verificare il significato funzionale, il DPT esatto e i flag in ETS.

L'importazione ETS è temporanea e i dati oggetti vengono passati all'endpoint di anteprima con limiti su numero e lunghezza. Nessun file HA viene scritto e non partono telegrammi KNX.

## Precedente 2.2.2 — Verifica ETS nel generatore

In **Genera HA**, quando il progetto ETS è stato importato nella sessione corrente, la verifica incrocia in memoria i GA dei widget salvati con l'elenco degli indirizzi ETS, il DPT dichiarato e la presenza di collegamenti agli oggetti. Le conferme DPT esplicite `DPST-1-1` e `DPST-5-1` (o equivalenti) diventano verdi; i DPT non assegnati restano da verificare. I GA esplicitamente scollegati vengono esclusi dalla bozza. I dati ETS non vengono salvati e non attestano da soli la direzione o il comportamento elettrico reale.

Il confronto avviene su `POST /knx/ha-preview`, con verifica del fingerprint di progetto e limiti di dimensione. Senza un import ETS valido nella sessione resta disponibile la precedente anteprima `GET /knx/ha-preview` senza conferme DPT automatiche. La bozza **non viene applicata** a Home Assistant o al bus KNX.

## Precedente 2.2.0 — Generatore KNX → Home Assistant

La scheda **Genera HA** crea una bozza YAML per l'integrazione KNX di Home Assistant partendo dai widget KNX *salvati* in NM Studio.

- Il backend `GET /knx/ha-preview` costruisce un documento JSON con la bozza YAML, il conteggio dei dispositivi e gli avvisi specifici. Non modifica alcun file Home Assistant.
- Luci e dimmer: associazione `address` e, se configurati, `state_address`, `brightness_address` e `brightness_state_address`; la regolazione relativa viene segnalata ma non convertita automaticamente.
- Tapparelle: `move_long_address` e, se presente, `stop_address`. I campi generici `position` e `feedback` restano **esclusi** finché ruolo, collegamento ETS e DPT 5.001 non siano verificati; questo evita di trasformare erroneamente un comando o un indirizzo scollegato in feedback posizione.
- Comandi mancanti e duplicati escludono il widget corrispondente dall'anteprima; il file generato mantiene note e avvisi nella schermata.
- La bozza può essere **modificata nell'interfaccia e scaricata** come `.yaml`. Il download non convalida il risultato modificato e non abilita nulla: l'installatore deve verificare il contenuto prima di inserirlo nella configurazione HA esistente.
- Il generatore è preparatorio a NM Link: nessuna creazione di entità, nessuna installazione automatica e nessun accesso al bus KNX.

## Precedente 2.1.0

La 2.1 aggiunge due endpoint di **sola lettura**, accessibili esclusivamente tramite Home Assistant Ingress:

- `GET /knx/preflight`: verifica dei widget KNX salvati, con segnalazioni distinte per problemi bloccanti, avvisi e informazioni. Evidenzia comandi mancanti, GA comando riutilizzati, feedback assenti, campo posizione tapparella da verificare, entità HA non collegate e stanze non assegnate. Non deduce DPT dal nome di un GA. L'esistenza delle entità HA non viene verificata da questo endpoint: `ha_entity_check` è `not_performed`.
- `GET /backup`: esportazione diagnostica legacy di quattro configurazioni locali. Per migrare tra installazioni usare invece il nuovo backup completo di NM Studio 3.6.0: `GET /migration/export` e `POST /migration/restore`, disponibili nell'Avvio guidato. Contiene cinque sezioni (incluse le associazioni NM Link), un checksum SHA-256 e richiede conferma per il ripristino. Il ripristino dall'interfaccia rifiuta la sovrascrittura di dati esistenti. Conservare il JSON in luogo sicuro: può contenere nomi e indirizzi dell'impianto.

Questi endpoint costituiscono le fondamenta per una futura pagina Diagnostica e per un generatore di configurazioni HA sottoposto a conferma. **Nessuna attivazione automatica di entità KNX è stata implementata.**

## Precedente 2.0.0

Novità 2.0 — **collegamento di sola lettura a entità Home Assistant esistenti**:

- In **Edificio ETS → Dispositivi nelle stanze** ogni widget KNX può essere associato a un'entità HA selezionata manualmente. Il medesimo campo è presente anche nel configuratore Widget KNX.
- Il collegamento `entity_id` è facoltativo, validato e persistito insieme ai widget; i layout precedenti rimangono validi con collegamento vuoto.
- La dashboard gerarchica visualizza gli stati delle entità HA collegate (e alcuni attributi selezionati) dal preesistente endpoint read-only, aggiornati ogni 15 secondi quando la pagina è attiva.
- Quando manca il collegamento, l'entità non esiste, lo stato è `unknown/unavailable` o HA è irraggiungibile, la dashboard ne indica il limite senza inventare un valore KNX.
- Nessuna creazione di entità HA, nessuna chiamata ai servizi, nessuna scrittura su bus KNX e nessuna variazione ai GA approvati. Il collegamento manuale non prova che l'entità selezionata corrisponda fisicamente al dispositivo KNX.

## Precedente 1.9

Novità 1.9 — **editor gerarchico della supervisione**:

- In **Edificio ETS** compare l'editor indipendente **Edificio → Piano → Stanza**; consente di creare nuovi elementi, rinominare quelli importati, spostare una stanza su un altro piano e spostare un piano su un altro edificio.
- Tutti gli elementi possono essere attivati o nascosti. Una stanza disattivata e i suoi widget restano salvati, ma non sono visualizzati nella dashboard cliente.
- La sezione **Dispositivi nelle stanze** permette di cambiare l'ambiente di ciascun widget, anche senza reimportare ETS quando esiste un archivio KNX già salvato.
- Salvataggio esplicito di `structure` assieme a stanze e widget nello stesso file locale `/data/nm_knx_widget_layout.json`, senza modificare l'originale ETS né gli ambienti HA.
- La dashboard cliente presenta edifici, piani e stanze visibili. Gli stati KNX rimangono dichiaratamente non disponibili, senza azioni interattive sul bus.
- L'editor originale delle posizioni fisiche ETS viene mostrato come riferimento in sola lettura, senza checkbox che sembrino inattive.
- Le vecchie configurazioni 1.8 restano leggibili (migrazione progressiva al salvataggio); non disinstallare l'app.

## Precedente 1.8

Novità 1.8 — **analisi combinata delle funzioni ETS e delle parole nei GA**:

- Interpreta la gerarchia `Locations/Space/Function/GroupAddressRef` per trovare collegamenti funzione → indirizzo di gruppo → ambiente, quando configurati in ETS.
- Se non ci sono collegamenti espliciti, cerca corrispondenze complete e univoche fra nomi e descrizioni delle funzioni/GA e nomi degli ambienti. Le corrispondenze multiple o deboli non vengono assegnate.
- La pagina Edificio ETS mostra un report distinto per funzioni ETS, corrispondenze testuali e indirizzi privi di evidenza, con motivo per ogni proposta.
- La pagina Widget KNX espone **Suggerisci stanze da ETS**: applica solo proposte univoche ai widget ancora da assegnare, senza modificare quelli già approvati/salvati e senza persistere nulla prima della conferma.
- Se un progetto ETS non contiene funzioni edificio collegate né nomi sufficienti per identificare le stanze, le proposte restano non assegnate e richiedono una scelta manuale.
- Nessun comando bus, chiamata di servizio HA o scrittura nel file ETS.

## Precedente 1.7.1

Correzione 1.7.1 — **assegnazione ambienti visibile e guidata**:

- Selezionando o deselezionando un ambiente ETS viene aggiornato subito il conteggio degli ambienti scelti.
- Ogni widget ha un vero menu a tendina per l'ambiente, con stato di assegnazione e contatori aggiornati in tempo reale, più la possibilità di scrivere un ambiente personalizzato.
- Nuova assegnazione rapida per i soli widget ancora "Da assegnare". I widget già associati non vengono spostati in blocco.
- I cambiamenti si consolidano con il pulsante **Salva dashboard KNX**; rimangono assenti comandi sul bus e modifiche alla configurazione Home Assistant.

## Precedente 1.7

Novità 1.7 — **struttura edificio ETS**:

- Analizza i nodi `Locations/Space` del `.knxproj` senza estrarre file né inviare telegrammi; distingue edificio, piani, stanze, scala e quadro.
- Nuova scheda **Edificio ETS**: visualizza la gerarchia e il conteggio dei dispositivi fisicamente collocati; permette di selezionare gli ambienti da usare nella supervisione.
- La selezione degli ambienti viene proposta nella scheda **Widget KNX**, dove ogni widget può essere assegnato a un ambiente ETS tramite scelta guidata o testo libero.
- Il salvataggio esplicito conserva anche gli ambienti vuoti e la vista cliente li mostra come ambienti da configurare. I dati persistono separati dalle configurazioni HA.
- **Attenzione:** nel progetto di prova sono presenti `Space` e `DeviceInstanceRef`, ma non `Function` di edificio. Non sono quindi ricavabili associazioni certe dei comandi alle stanze. Le ubicazioni dei dispositivi non sono usate per indovinare i GA funzionali.

## Precedente 1.6

Novità 1.6 — **dashboard KNX persistente, in sola lettura**:

- Assegna un ambiente a ogni widget creato nella pagina **Widget KNX** e salva con conferma esplicita.
- Salva i soli nomi, ambienti, tipi e indirizzi KNX in `/data/nm_knx_widget_layout.json`, separatamente dalla dashboard HA e dalle associazioni KNX approvate.
- Riaprendo il medesimo progetto ETS, recupera le assegnazioni salvate invece di rigenerare e sovrascrivere i widget.
- Mostra le schede raggruppate per ambiente nella dashboard di NM Studio e nella vista cliente, anche senza reimportare ETS, con la dicitura **Stato non disponibile**: nessun dato sul bus è ancora interrogato.
- Non crea entità Home Assistant, non chiama servizi e non scrive telegrammi KNX. Installare con aggiornamento dell'app, evitando la disinstallazione che può cancellare i dati persistenti.

## Precedente 1.5

Novità 1.5 — **configuratore widget-first in anteprima**:

- Nuova pagina **Widget KNX** dopo l'importazione ETS; genera proposte visive per luce, dimmer e tapparella prima della scelta dei GA.
- I campi funzionali espongono i DPT attesi dal widget, ma senza presentarli come verificati nel progetto; le associazioni automatiche usano esclusivamente GA con collegamenti ETS e proposte riconosciute.
- Feedback e altri campi non affidabili rimangono vuoti ed evidenziati. L'installatore può cambiare ogni associazione o aggiungere manualmente widget, mentre un GA scollegato viene segnalato.
- Esportazione JSON locale dell'anteprima, senza salvare i nuovi widget in `/data`, senza modificare associazioni approvate, senza creare entità HA e senza comandare il bus.

## Precedente 1.4

Novità 1.4 — **oggetti non collegati e possibilità applicative ETS**:

- Distingue tre livelli di evidenza: oggetti istanziati con collegamenti, oggetti istanziati con `Links` vuoto, e oggetti presenti soltanto nel catalogo del produttore.
- Per ciascun dispositivo visualizza gli oggetti senza `Links` e le ulteriori voci di catalogo non istanziate, con numero, nome, funzione e dimensione quando disponibili.
- Gli oggetti di catalogo possono essere disabilitati dai parametri ETS: **non vengono presentati come attivi o come feedback verificati**. Nell'attuatore GW90856 gli oggetti di posizione compaiono nel catalogo, mentre nel file progetto sono istanziati solo i quattro comandi collegati.
- Limiti di sicurezza: massimo 150 istanze senza link e 120 possibili oggetti di catalogo mostrati per dispositivo, con contatori e avvisi. Nessuna alterazione delle associazioni precedenti e nessun comando al bus.

## Precedente 1.3

Novità 1.3 — **schede tecniche dei dispositivi ETS**:

- Esplora i dispositivi fisici importati con un selettore dedicato e mostra indirizzi di gruppo, nomi degli oggetti, funzione, dimensione, DPT del gruppo e flag C/R/W/T/U quando decodificati.
- Assegna un identificatore locale per importazione ai dispositivi per distinguere componenti che hanno descrizioni uguali.
- Mostra il conteggio degli oggetti con collegamenti e avvisa se parte dei dettagli è stata troncata dai limiti di sicurezza dell'analizzatore.
- Il file di progetto resta in memoria e le associazioni salvate in versioni precedenti non vengono alterate. Nessun comando KNX o Home Assistant.

## Precedente 1.2.1

Correzione 1.2.1: include `audit_notes.py` nel Dockerfile dell'app; risolve l'errore di avvio `ModuleNotFoundError` della 1.2.0.

Novità 1.2 — **registro verifiche ETS per progetto**:

- Mostra gli indirizzi di gruppo senza collegamenti in una lista di revisione; consente di marcarli «Da controllare», «Previsto dal progetto», «Da correggere» o «Verificato» e aggiungere una nota.
- Salva le verifiche separatamente in `/data/nm_ets_review.json`, associate a un identificatore non reversibile calcolato dal GUID del progetto ETS (o dal file quando assente).
- Ricaricando lo stesso progetto ETS le verifiche vengono recuperate, se il GUID è invariato. Sono richieste conferma e salvataggio esplicito; l'importazione non salva mai il file di progetto.
- I giudizi sono annotazioni dell'installatore, non una convalida automatica delle connessioni fisiche. Nessun comando al bus.

## Precedente 1.1

Novità 1.1 — **report e filtri per l'installatore**:

- Riepilogo degli indirizzi senza collegamenti, cataloghi applicativi non decodificati e funzioni proposte. Gli indirizzi liberi sono solo elementi da verificare, non necessariamente errori.
- Ricerca istantanea per indirizzo, dispositivo e oggetto nella tabella dei collegamenti.
- Filtro tutti/collegati/non collegati e contatore dei risultati.
- Esportazione di un report JSON locale con segnalazioni e proposte, senza salvare il progetto nel dispositivo HAOS o sul sito remoto.
- Mantiene inalterati il modello dei dispositivi approvati e la modalità read-only.

Novità 1.0 — **oggetti e flag dei programmi applicativi ETS**:

- Risolve in modo limitato e selettivo le applicazioni `M-*` incluse nel progetto, per i dispositivi presenti nell'installazione.
- Usa l'override `ComObjectRef` quando presente: nomi, funzioni e dimensioni del riferimento parametrizzato prevalgono sui valori generici di `ComObject`.
- Espone nome, funzione, dimensione e flag C/R/W/T/U degli oggetti collegati; aggiunge un inventario dei prodotti con identificatori tecnici.
- Alcuni cataloghi applicativi oltre le soglie di dimensione restano non decodificati. I risultati vanno confrontati con il progetto ETS originale.
- Il DPT del singolo oggetto non viene inventato dalla dimensione: `1 bit` non equivale automaticamente a DPT 1.008; il funzionamento bus richiede verifica separata.

Novità 0.9 — **ETS Smart Import: verifica dei collegamenti dal solo `.knxproj`**:

- Legge i `ComObjectInstanceRef` e i relativi `Links` nel file di installazione ETS, senza SDK, MCP o software ETS installato.
- Inventario di indirizzi collegati/non collegati, con elenco dei dispositivi e riferimenti oggetto in sola lettura.
- Le tapparelle con indirizzo di posizione NON collegato vengono proposte lasciando vuoto il campo di posizione, con motivazione esplicita. Analogamente, il comando movimento deve risultare collegato per generare la proposta.
- Per esempio, un indirizzo di posizione tapparella senza collegamenti deve rimanere non assegnato. Nessun file progetto viene salvato dall'add-on, né vengono inviati comandi sul bus.
- Limitazione: i riferimenti oggetto sono ancora identificatori XML; la decodifica completa di nomi, flag e DPT oggetto dai cataloghi dei produttori sarà una fase successiva. I collegamenti provano la configurazione nel file, non l'operatività fisica.

Correzione 0.8.1: riconoscimento dei gruppi tapparella con sigle `T1`, `T2` e indirizzi distinti `MOVIMENTO SU/GIU`, `ARRESTO`, `POSIZIONE`. Il generatore offre campi separati per tali oggetti, approvazione esplicita e selezione manuale di qualsiasi indirizzo importato. La funzione e il DPT di `POSIZIONE` devono essere verificati in ETS: il campo non viene trattato automaticamente come feedback live.

Novità 0.8 — **modello KNX indipendente e anteprima di supervisione**:

- Ambienti suggeriti dai termini espliciti presenti nei nomi o nelle descrizioni ETS (altrimenti `Da assegnare`); modificabili nella revisione installatore.
- Ambiente salvato insieme al dispositivo KNX verificato, preservando i vecchi dispositivi senza ambiente (`Da assegnare`).
- Nuova pagina **Progetto KNX** con schede raggruppate per ambiente, sia approvate sia in anteprima temporanea; nessuno stato fittizio e nessun comando bus.
- La dashboard Home Assistant esistente resta intatta; nessuna creazione automatica di entità HA né accesso a KNX.

Novità 0.7 — **importazione ETS più automatica, sempre in sola lettura**:

- Abbinamento delle coppie tramite normalizzazione dei nomi (anche `NOTIFICA STATO DIMMER ON/OFF L11` con `DIMMER ON/OFF L11`).
- Riconoscimento proposto di `L1`, `L15` ecc. come luci *probabili* se esistono un comando ON/OFF e un feedback coerente. Le sigle da sole non certificano l'uso reale.
- Motivazione e attendibilità della classificazione in anteprima, tipi precompilati nel generatore, suggerimenti già approvati esclusi dalla nuova lista.
- Nessuna creazione automatica di entità Home Assistant, nessun telegramma KNX, nessuna approvazione senza verifica esplicita.

Aggiornamento: conservare `/data` e usare `ha apps update local_nm_bridge` dal Terminal & SSH di Home Assistant dopo aver sostituito i file locali e verificato gli aggiornamenti del repository.

Novità 0.6 — **Generatore di dispositivi KNX**:

- Dopo l'importazione ETS, le coppie comando/feedback suggerite diventano righe modificabili. Nome, tipo, indirizzo comando e feedback possono essere verificati e corretti dall'installatore.
- Ogni riga parte **non selezionata**: la casella `Verificato` e una conferma esplicita sono necessarie per salvarla.
- Puoi aggiungere dispositivi manuali usando gli indirizzi già importati.
- Le associazioni approvate vengono aggiunte in `/data/nm_knx_approved.json`, separate dal layout HA e non vengono modificate da importazioni ETS successive.
- Un indirizzo comando già approvato non può essere inserito due volte. Nessun telegramma, nessun comando, nessuna creazione di entità Home Assistant o widget cliente.
- L'analisi ETS originale rimane solo in memoria e non è salvata: dopo il riavvio puoi ricaricare il file; le associazioni approvate rimangono.

Aggiorna senza disinstallare tramite il terminale HAOS: `ha apps update local_nm_bridge` dopo aver estratto i file in `/addons/nm_bridge` e aggiornato lo store locale. Conserva prima un backup.

## Versioni precedenti

Correzione 0.5.2: il parser ETS considera soltanto i documenti XML `P-*` del progetto, ignorando i cataloghi dei produttori `M-*`, che possono contenere grandi XML non necessari per gli indirizzi di gruppo. I limiti di dimensione rimangono applicati ai documenti analizzati. Nessun cambiamento alla configurazione salvata.

## Versione 0.5.1

Correzioni 0.5.1: la lettura automatica degli stati Home Assistant non ridisegna più la pagina Importa ETS mentre si sceglie o si carica un file; il messaggio dell'analisi rimane visibile. Gli errori di formato restituiscono un motivo più leggibile invece del solo codice HTTP 400. Formato delle configurazioni, importazione read-only e limiti di dimensione invariati.

## Versione 0.5

Novità 0.5: **Importa ETS** in NM Studio. Accetta un progetto `.knxproj` non cifrato e fino a 8 MB, analizza gli XML in memoria, propone una tabella di indirizzi di gruppo con nomi, descrizioni e DPT disponibili, e suggerisce coppie comando/feedback solo quando i nomi rendono l'abbinamento univoco. È disponibile l'esportazione locale dell'analisi JSON. **Non salva il progetto sul mini PC, non crea automaticamente widget o entità HA e non invia alcun telegramma KNX.** L'analisi è preliminare e deve essere verificata dall'installatore, specialmente con DPT mancanti o descrizioni incoerenti.

Il parser iniziale rappresenta gli indirizzi in formato KNX a tre livelli; progetti con stile a due livelli o libero potranno richiedere una presentazione corretta in una futura versione. Per progetti protetti da password o archivi particolarmente grandi utilizzare inizialmente un'esportazione XML degli indirizzi di gruppo (il supporto diretto XML sarà aggiunto successivamente).

Per aggiornare, copia i file nella cartella dell'app, aggiorna l'indice dello store locale ed esegui `ha apps update local_nm_bridge` nel Terminal & SSH di HAOS. Non disinstallare l'app: il formato della configurazione salvata dalla 0.2 rimane invariato.

## Note sulle versioni precedenti

Novità 0.4:

- **Vista cliente**: dashboard senza menu di configurazione o diagnostica, attivabile da `Apri vista cliente` o con `?view=client` nell'URL sotto Home Assistant Ingress.
- **NM Studio**: navigazione tecnica, configuratore, inventario e diagnostica nella stessa app. La distinzione è **solo di presentazione**: chi accede all'add-on tramite Home Assistant può tornare a NM Studio. Non è un sistema di ruoli o di autorizzazioni pronto per i clienti.
- Lettura periodica delle entità ogni 15 secondi con pagina visibile; lettura immediata al ritorno alla scheda. Nessun comando verso HA/KNX.
- Migliorata la gestione degli identificativi entità lunghi nei widget.
- Configuratore: il pulsante `Suggerisci entità HA` propone fino a 15 entità non ancora associate (luci, tapparelle, interruttori, clima e sensori binari) per ambiente; richiede conferma e salvataggio esplicito.
- File della configurazione invariato e compatibile con la 0.2 e la 0.3.

Aggiornamento su HAOS: carica i file sotto `/addons/nm_bridge`, aggiorna lo store locale e usa `ha apps update local_nm_bridge` dal Terminal & SSH di Home Assistant. Verifica la versione 0.4.0 e la persistenza dell'ambiente `test`. Non disinstallare l'app.

## Note sulle versioni precedenti

La versione 0.3 conserva il modello dati v1 della 0.2 e aggiunge una dashboard orientata al cliente: selettore ambienti, card responsive, icone e colori di stato, dettagli per luci/dimmer, tapparelle, clima e sensori. Gli stati vengono aggiornati all'apertura e con il pulsante **Aggiorna stati** (non in streaming).

L'upgrade non richiede di eliminare `/data/nm_control_layout.json`. Dopo aver copiato i file aggiornati in `/addons/nm_bridge`, prova **Ricostruisci** dall'app e poi riavviala. Verifica il titolo `NM Control 0.3`: la notifica di aggiornamento del repository locale può restare non allineata anche se il codice è nuovo. **Non disinstallare** l'app per risolvere una semplice notifica; conserva un backup prima di qualsiasi reinstallazione.

## Funzioni introdotte nella 0.2

Questa versione legge gli stati delle entità tramite l'API interna di Home Assistant e offre quattro viste: Dashboard, Configuratore, Entità HA e Diagnostica.

- La Dashboard presenta dispositivi raggruppati per ambiente.
- Nel Configuratore puoi creare fino a 50 ambienti e associare entità Home Assistant a widget di sola lettura.
- Gli ambienti vengono salvati in `/data/nm_control_layout.json` all'interno dell'app, separatamente da `configuration.yaml`.
- Nessuna richiesta invoca servizi Home Assistant, scrive stati o invia telegrammi KNX.
- L'app è accessibile solo tramite Home Assistant Ingress e non espone porte host.

## Aggiornamento sul laboratorio HAOS

In Studio Code Server, copia i file della cartella `nm_bridge` dentro `/addons/nm_bridge`, mantenendo la struttura piatta (`config.yaml`, `Dockerfile`, `bridge.py`, `index.html`, `build.yaml`). Da Impostazioni → App → App Store, controlla gli aggiornamenti del repository locale e aggiorna NM Bridge alla versione **0.2.0**. Non eliminare l'add-on già installato: il volume `/data` contiene la configurazione.

Questa è una build di test, non ancora una soluzione pronta per clienti o per accesso pubblico. Effettua un backup dell'add-on prima di aggiornare la prossima volta.

