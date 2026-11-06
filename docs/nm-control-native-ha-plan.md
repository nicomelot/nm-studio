# NM Control: percorso unico per impianti reali

Revisione del 6 novembre 2026. Stato: analisi del codice e delle funzioni native
Home Assistant; architettura proposta, non ancora implementata o pubblicata.

## Obiettivo

NM Control configura e mantiene la supervisione. Home Assistant resta il motore
per entità, aree, piani, comandi, automazioni, stati e interfaccia cliente.
Un solo progetto installato; nessun percorso di simulazione nel prodotto.

## Riscontri nel codice attuale

- `ets_rooms.py`: riconosce associazioni Function/GroupAddressRef negli ambienti
  ETS e propone corrispondenze dai nomi. Non confonde intenzionalmente la posizione
  fisica dell'attuatore con il locale controllato. Questo principio va conservato.
- `widget_layout.py`: salva una struttura interna. Non sincronizza i registri
  delle aree e dei piani di HA: oggi una stanza nella dashboard non implica che
  quella stanza esista come area di Home Assistant.
- `knx_install.py`: crea una funzione e salva subito il collegamento all'entità;
  l'interfaccia 5.16.0 esegue questi passi in sequenza su una selezione multipla.
- `nm_link.py`: conserva bozze e interpreta esempi; rifiuta enabled=true. Il ponte
  tra KNX e le altre entità non è ancora operativo.
- `floorplan_lovelace.py`: produce già Picture Elements native. Si può mantenere
  l'editor delle coordinate e ampliare le entità e le azioni disponibili.
- `floorplan.py`: limita i domini selezionabili; per esempio scene, script,
  pulsanti e allarmi richiedono estensione esplicita del modello e delle azioni.
- `intelligence.py`: legge decisioni e telemetria simulate. Il risparmio energetico
  non è un controllore reale pronto; va separato dal laboratorio e collegato a
  misure e azioni reali con una configurazione dedicata.
- UI: progetto guidato, widget, associazioni, generazione dashboard e laboratorio
  rappresentano percorsi sovrapposti. I loro stati devono diventare un solo piano
  di installazione, non altrettante operazioni da ripetere.

## Riutilizzo di Home Assistant

1. Aree e piani nei registri nativi, con assegnazione alle singole entità quando
   un attuatore fisico serve più stanze. Le correzioni esplicite dell'installatore
   restano separate dalle informazioni importate e vengono preservate.
2. Dashboard Home, viste per area e raggruppamenti nativi per dominio. Il cliente
   non deve mantenere due classificazioni delle stesse luci e tapparelle.
3. Pannello KNX e relativo motore di comunicazione; nessun secondo tunnel aperto
   dall'add-on per inviare gli stessi comandi.
4. Lettura ETS: valutare come prima fonte il progetto già elaborato da HA
   (`knx/get_knx_project`, richiede amministratore). HA 2026.11.0 usa
   `xknxproject==3.10.0`: preferire questa libreria per l'importazione diretta,
   anziché espandere indefinitamente il parser XML proprietario.
5. Automazioni con trigger `knx.telegram` per KNX verso entità HA; esposizioni
   KNX native per stati e attributi nella direzione opposta.
6. Picture Elements e popup more-info nativi per mappe; storico, log e monitor
   KNX nativi come sorgenti della diagnostica. Evitare archivi duplicati quando
   le API della versione installata coprono il caso d'uso.

Le API KNX usate non vanno trattate come immutabili: adattatore per versione,
controllo capacità e prove contro le immagini HA supportate. Verificare i permessi
prima dell'installazione, mostrando un unico errore utile se insufficienti.

## Tre passaggi per l'installatore

### 1. Importa impianto

Un file ETS oppure il progetto già disponibile nel pannello KNX. Rilevare
struttura edificio, funzioni, GA, DPT, canali, collegamenti e configurazione HA
esistente. Nessun salvataggio ripetuto della stessa analisi in pagine differenti.

### 2. Controlla il riepilogo

Una tabella raggruppata per piano e stanza con nome, tipo, provenienza della
stanza e stato: pronta, già presente, da verificare, esclusa. Le funzioni pronte
sono preselezionate. Espandere i GA solo per verifiche o correzioni.

Priorità per la stanza: collegamento funzionale esplicito nell'edificio ETS;
collegamento univoco del canale e della funzione; nome coerente come proposta.
Un attuatore nel quadro non assegna tutte le sue uscite al quadro. Un comando
generale non viene presentato come una lampada. I casi ambigui rimangono visibili
e non impediscono di installare le funzioni indipendenti già risolte.

Riconoscere una funzione completa: ON/OFF, livello e relativi feedback per un
dimmer; salita/discesa, arresto, posizione e feedback distinti per una tapparella.
Non derivare il tipo dal solo nome e non inventare GA mancanti.

### 3. Installa e apri la casa

Una conferma applica il piano: riusa/crea aree e piani, riusa le entità esistenti,
crea le mancanti, assegna le entità alle aree e apre la supervisione HA.
Mostrare il risultato di ogni funzione e consentire ripresa dopo errore.
Il collaudo fisico ON/OFF, dimmer, movimento/arresto segue sui controlli reali.
L'importazione e la creazione non devono comandare automaticamente i carichi.

Reimportare lo stesso progetto non deve produrre nuovi duplicati, perdere le
associazioni o annullare le correzioni. Conservare un manifesto ETS→HA con ID
stabili, risorse possedute, override e risultati applicati; non identificare le
funzioni solo tramite indice della lista o nome visualizzato.

## Moduli aggiuntivi

### Collegamenti KNX

L'utente sceglie l'entità reale già integrata in HA e la funzione desiderata.
Esempio: comando KNX ON/OFF → luce Hue; stato effettivo della Hue → GA feedback.
Analogamente, un Sonoff può comandare un'entità KNX tramite automazione HA.
Il sistema verifica capacità, DPT, direzione e conversioni; genera configurazioni
persistenti riapribili da HA, con ID stabili e gestione delle revisioni.

I trigger di comando ascoltano telegrammi in ingresso di scrittura, non letture
o risposte di stato. Separare comando e feedback, evitare eco e più mittenti sullo
stesso feedback. Stato non disponibile non equivale a spento. Per luminosità,
posizione, scene e clima servono profili specifici e conversioni verificate.
Al riavvio collegamenti ed esposizioni devono funzionare senza riaprire l'add-on.

### Mappe

Editor semplice: carica pianta, scegli entità HA, posiziona, scegli azione.
Supportare anche scene, script, sensori, climatizzazione, telecamere, allarmi e
multimedia secondo le capacità reali. Azioni sensibili esplicite, non toggle
generico. I popup devono essere quelli nativi dell'entità.

### Diagnostica

Una schermata con connessione, entità non disponibili, associazioni incomplete,
GA duplicati, ultimi telegrammi e filtri per stanza/dispositivo. Accesso diretto
al monitor KNX e ai log HA; separare osservazione e azioni di prova sul bus.

### Energia

Modulo facoltativo dopo il collaudo dell'impianto: selezione delle misure reali,
obiettivi, carichi controllabili, soglie e priorità. Riutilizzare Energy per la
visualizzazione. Le decisioni e l'esecuzione sono capacità diverse da sviluppare
e collaudare; non dichiarare operativo il vecchio prototipo simulato.

## Nomi e rimozione del laboratorio

Nome unico dell'applicazione: NM Control. Nomi di stanze, funzioni e dashboard
cliente descrittivi, per esempio Casa, Cucina e Luce tavolo, senza NM Studio.
Rinominare etichette e titoli; preservare gli ID esistenti di entità, risorse e
configurazioni per non rompere automazioni o collegamenti.

Eliminare dalla navigazione e dall'installazione i percorsi LAB e la generazione
di entità virtuali. Conservare i test sintetici di sviluppo. Non cancellare in
automatico dal cliente entità precedentemente create: mostrarle in una migrazione
separata con inventario preciso e dipendenze.

## Ordine di implementazione e criteri di accettazione

1. Leggere il vero progetto estratto e confrontare il riconoscimento con ETS:
   conteggi per tipo, stanza, GA e motivazione di ogni eccezione.
2. Normalizzare il modello dell'impianto e la sincronizzazione HA; testare che
   un secondo import non crei nulla e che le correzioni siano conservate.
3. Sostituire la navigazione con i tre passaggi, rimuovere LAB e uniformare i nomi.
   Un progetto pulito deve arrivare a entità reali e aree senza passaggi YAML.
4. Collaudare una luce, un dimmer e una tapparella; verificare separatamente
   comandi e feedback, anche dopo riavvio e interruzione dell'installazione.
5. Attivare i profili KNX↔HA iniziando da ON/OFF e feedback; poi luminosità,
   tapparelle, scene e clima, con prove contro loop e stati non disponibili.
6. Ampliare mappe e diagnostica, poi integrare il modulo energetico reale.

## Verifica su progetto ETS estratto

L'analisi locale di un progetto reale estratto e non cifrato ha riprodotto il
problema: nessuna proposta dimmer o tapparella, pur essendo presenti i relativi
GA e collegamenti. I dati del cliente restano esclusi dal repository pubblico.

Requisiti aggiuntivi confermati:

- Riconoscere nomi descrittivi senza sigle L/T numeriche né separatori obbligatori.
- Aggregare ON/OFF, DIMMING RELATIVO, DIMMING ASSOLUTO, stato ON/OFF e stato
  valore nella stessa funzione; distinguere comando posizione da stato posizione.
- Gestire errori lessicali nei nomi (es. SATO al posto di STATO) con evidenza DPT
  e collegamenti; non convertire automaticamente un DPT incoerente in verificato.
- Separare comandi singoli, gruppi e generali analizzando gli oggetti collegati.
  Un indirizzo collegato soltanto a un pulsante non prova che raggiunga un attuatore.
- Non creare automaticamente funzioni da indirizzi senza collegamenti.
- Non inventare piani se ETS contiene stanze direttamente sotto l'edificio.
- Non usare il locale del quadro come stanza di tutte le uscite multicanale.
- Una Function ETS priva di riferimenti GA non costituisce un'associazione certa.
- Mostrare nella revisione soltanto ambiguità, dati mancanti e incompatibilità;
  conservare i dettagli completi nella diagnostica.

Questa verifica definisce i requisiti del nuovo importatore; non costituisce una
correzione già distribuita né un collaudo sul bus. Servono fixture anonimizzate
che coprano questi casi prima di sostituire il percorso esistente.

## Fonti tecniche consultate

- https://www.home-assistant.io/docs/organizing/areas/
- https://www.home-assistant.io/docs/organizing/floors/
- https://www.home-assistant.io/dashboards/dashboards/
- https://www.home-assistant.io/dashboards/picture-elements/
- https://www.home-assistant.io/integrations/knx/
- https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/knx/project.py
- https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/knx/websocket.py
- https://www.ekinex.com/delego-software/ambiente-di-configurazione.html
- https://www.domoticalabs.com/article/nuovo-motore-di-import-ets

Delégo e IKON sono stati confrontati tramite documentazione pubblica; in questa
revisione non è stata riaperta una sessione sui server privati del cliente.

## Implementazione: primo incremento

Implementati e verificati con test locali:

- riconoscimento dei suffissi descrittivi dimmer/tapparella, con DPT e collegamenti;
- campi distinti comando/stato posizione, mantenendo isolati i campi legacy;
- recupero esplicito dei dimmer già salvati come luci, conservando personalizzazioni;
- stanze direttamente sotto l'edificio, senza un piano artificiale;
- percorso principale Importa / Controlla / Installa e salvataggio progetto senza LAB;
- rimozione del caricamento del wizard virtuale dall'interfaccia;
- sincronizzazione esplicita con registri area/floor/entity HA, con mappa persistente
  per progetto/nodo e conservazione delle assegnazioni HA già presenti;
- aggiornamento del marchio visibile, mantenendo identificatori e formati compatibili.

La sincronizzazione delle stanze è ripetibile e non rinomina né elimina aree HA.
Le entità già create come luci non vengono trasformate automaticamente in dimmer:
il recupero aggiorna la bozza; la configurazione HA esistente richiede una modifica
separata. I DPT di stop incoerenti restano da verificare, senza assegnazione automatica.

Ancora da implementare: risoluzione completa degli oggetti modulari/cataloghi ETS,
classificazione certa gruppi/singoli, migrazione delle entità HA esistenti, ponte
KNX–HA operativo, estensioni mappe e modulo energetico reale. I backend LAB restano
per compatibilità e test, ma il percorso principale non li carica.
