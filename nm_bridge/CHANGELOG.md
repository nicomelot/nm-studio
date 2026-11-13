## 5.21.0-beta.5

- Configurazione delle funzioni KNX in righe compatte: dettagli apribili e anteprime ridotte, con confronto ETS e ricerca degli indirizzi richiudibili.
- Maniglia per riordinare le funzioni e spostarle nella stanza scelta. Disponibili anche selezione e pulsante, riordino da tastiera con Alt + freccia su/giù e annullamento dell’ultimo spostamento.
- Ordine e stanza restano modifiche in bozza fino al salvataggio; indirizzi KNX, associazioni HA e profili vengono conservati.
- Versione LAB: test automatici eseguiti; collaudo visivo e su impianto ancora da completare.

## 5.21.0-beta.4

- I gateway con gli stessi ruoli e indirizzi sono proposti come un unico gruppo clima. Il riepilogo esplicita che gli stati condivisi rappresentano l’ultimo telegramma ricevuto. Le condivisioni parziali fra zone rimangono da verificare.
- Riconoscimento degli oggetti Control_/Status_ con verifica DPT e direzione. I gruppi ventilanti con soli comandi restano visibili come bozze incomplete, indicando i feedback mancanti senza inventare collegamenti.
- La dashboard reale usa la scheda termostato nativa, con temperatura ambiente in primo piano, setpoint e modalità accessibili.
- Le funzioni clima accessorie sono raccolte per stanza in Opzioni e manutenzione. Il reset filtro mantiene la conferma e i nomi omettono il suffisso della stanza già aperta.
- Descrizione italiana e icona laboratorio distinguono il canale LAB nell’elenco applicazioni.

## 5.21.0-beta.3

- L’import distingue le zone clima dal nome del gruppo ETS del setpoint quando la stanza è univoca. Segnala i GA condivisi fra gateway e omette i controlli e feedback condivisi dalle proposte individuali.

- La reimportazione aggiunge le nuove stanze ETS alla gerarchia già salvata, rispettando rinomine, spostamenti e associazioni.
- L’import ETS riapre il percorso di simulazione virtuale in Home Assistant, con selezione diretta dei termostati.
- L’installazione KNX reale permette di selezionare i termostati e indica la funzione su cui si interrompe il gruppo. Il confronto iniziale legge l’indice degli indirizzi una volta e indica gli indirizzi già in uso.

## 5.21.0-beta.2

- L'import ETS propone stato e reset filtro, ventola automatica con la polarità del gateway, posizione lamelle, sospensione e ritardo quando gli oggetti sono verificabili.
- La scheda di installazione del clima apre il modello Home Assistant per la programmazione settimanale. Il modello supporta setpoint per fascia, spegnimento o risparmio fuori fascia e controllo manuale fino al prossimo cambio.

## 5.21.0-beta.1

- Import ETS con lettura progressiva dei cataloghi applicativi fino a 24 MiB ciascuno e 96 MiB complessivi. I cataloghi vengono letti una volta per applicativo.
- Il riconoscimento dei gateway con ruoli AC espliciti propone un unico widget clima con setpoint, temperatura, ON/OFF e i ruoli di modalità, ventola e swing disponibili. Il flusso di installazione prepara l’entità KNX clima nativa in Home Assistant.
- Widget manuali Pulsante e Interruttore con GA scelti da ETS o inseriti a mano. Il pulsante invia il valore 1 oppure 0 a ogni pressione. L’interruttore usa ON/OFF e un GA di stato facoltativo. Creazione, collaudo e plancia usano le entità KNX native di Home Assistant.
- Creazione della stanza direttamente dal widget, con scelta di edificio/piano e assegnazione immediata nella gerarchia condivisa. Stanze omonime nello stesso contenitore vengono riutilizzate; annullare conserva l’assegnazione precedente.
- Aggiunta widget sempre visibile; apertura della nuova scheda con ricerca azzerata e campi KNX espansi.
- Inserimento manuale di GA con verifica dei limiti KNX e conservazione nei selettori dopo salvataggio e riapertura. Le associazioni manuali non modificano il file ETS né programmano dispositivi.

## 5.20.2

- Serrande: riconoscimento di STOP, POSIZIONE e POSIZIONE STATO con verifica DPT; lo stato direzione non viene usato come posizione.
- Riconoscimento dei comandi generali OFF e ON/OFF con conferma dagli oggetti di commutazione; OFF resta solo spegnimento anche dopo la reimportazione.
- TAPPARELLE TUTTE riconosciuto come collettivo, senza attribuire un feedback di posizione comune non verificato.

## 5.20.1

- Riconoscimento dimmer tramite DPT, flag e oggetti collegati alla stessa istanza modulo, anche senza nomi convenzionali degli indirizzi di gruppo.
- Supporto delle diciture DIMMER, VALORE, VALORE STATO e STATO; distinzione dei feedback binari e percentuali tramite DPT.
- Lettura dei cataloghi applicativi con suffisso OEM e rispetto delle impostazioni degli oggetti nel progetto ETS.
- Associazioni ambigue e conflitti restano da verificare; nessuna installazione o scrittura sul bus automatica.

## 5.20.0
- Avvio guidato: verifica automatica in sola lettura della connessione KNX e collegamento alla configurazione nativa di Home Assistant quando necessaria. IP, interfaccia e credenziali vengono scelti nella procedura ufficiale; nessuna configurazione del bus viene inventata.
- Pulsanti di solo spegnimento: conversione delle luci esistenti, dashboard con azione OFF esplicita e collaudo senza ON/toggle. L’entità HA sottostante resta una luce utilizzabile da altre viste.
- Ricerca per nome o GA nelle funzioni e nei selettori; aggiunta o conversione di un pulsante senza duplicare la funzione.
- Aggiornamento della plancia con conservazione delle personalizzazioni, confronto a tre versioni e backup. Le plance precedenti senza riferimento conservano prioritariamente le schede esistenti; i conflitti manuali non vengono sovrascritti.
- Una conversione esplicita a solo spegnimento aggiorna anche le scorciatoie native già presenti, conservandone posizione, nome e icona. Le schede personalizzate di terze parti richiedono verifica manuale.

## 5.19.0

- Compact installer cards grouped by room with labelled readiness badges and collapsible KNX details.
- Sticky installation actions and responsive room grids for desktop and mobile.
- In-card commissioning for installed lights, dimmers and covers through explicit HA service calls.
- Commissioning is disabled on entry/reload, limited to saved verified entity bindings, and never activated by state reads or field changes.
- Distinguish HA service acknowledgement from observed state and physical commissioning result. No automatic retries.
- Validate command allowlists, percentages, capabilities, availability and current configuration before sending; stop remains available with an unknown cover state when supported.

## 5.18.0

- Unified room-by-room installation review: create, update, already aligned, or review required.
- Complete existing KNX UI entities through the official update API without changing entity IDs, names, options or existing GA assignments.
- Compare again before each write, validate with HA, and read back updates; conflicts and stale plans require renewed review.
- Skip synthetic floor navigation for rooms directly under a building and legacy "Altri ambienti" groups. Real floors and stable room URLs remain intact.
- Existing dashboards require regeneration and explicit update to adopt the simplified navigation.

## 5.17.2

- Resolve modular ETS communication objects without mixing module definitions.
- Recover DPT 1.008 stops only when the linked application object explicitly confirms writable one-bit stop semantics.
- Fill missing fields in previously saved functions on reimport while preserving installer overrides.

## 5.17.1

- Automatically add unambiguous linked ETS functions to the draft, including on reimport.
- Automatically complete recognized dimmers while preserving names, rooms and HA links.
- Stop scrolling to the last card after adding a function.
- Add per-function visibility for generated dashboards; hiding preserves entities and configuration.
- Retain explicit installation confirmation and manual review of ambiguous or incomplete functions.

## 5.17.0

- Import descriptive ETS dimmer and cover functions with typed, linked roles.
- Preserve rooms directly under buildings; synchronize native HA areas and entity assignments on request.
- Separate cover position command/state from legacy ambiguous fields.
- Recover dimmers in saved drafts without overwriting names, rooms or HA links.
- Three-step real installation flow; virtual wizard removed from the UI.
- NM Control visible branding. Existing IDs and data formats remain compatible.
- Conflicting stop DPTs require review; existing HA entities are not automatically reconfigured.

## 5.16.0 - Creazione multipla guidata

- Salva e continua porta direttamente alla creazione delle funzioni selezionate; associazioni esistenti e collaudo singolo restano disponibili.
- Una sola conferma per la sequenza, con salvataggio immediato delle associazioni HA e arresto al primo errore senza perdere i risultati precedenti.
- Funzioni incomplete visibili con motivazione; stanze e rifiniture completabili dopo.
- Riconoscimento dei dimmer senza richiedere feedback facoltativi e delle tapparelle con ruoli movimento/arresto e DPT coerenti, anche senza sigle T1/T2.
- Verifiche automatiche su Linux, Windows, immagine add-on e schemi HA 2026.10.4/2026.11.0. Verifica sul progetto cliente e collaudo fisico ancora da completare.

## 5.15.2 - Creazione entita KNX reali

- Corretto il formato delle richieste al pannello KNX: dati entity/knx e GA write/state, invece dei campi YAML.
- Correzione applicata a luci, dimmer e tapparelle; mantenuti conferma esplicita, verifica duplicati e validazione prima della creazione.
- Errori di validazione leggibili senza troncare il dettaglio principale.
- Collaudo automatico dei payload contro lo schema delle immagini ufficiali Home Assistant 2026.10.4 e 2026.11.0, senza accesso al bus.

## 5.15.1 - Importazione ETS protetta da password

- Campo password nelle due schermate di analisi ETS; svuotato dopo ogni richiesta.
- Lettura in memoria dei contenitori protetti ETS5 (ZIP) ed ETS6 (AES con derivazione KNX).
- Password e archivio originale non vengono salvati o inseriti nelle analisi esportate.
- Messaggi specifici per password mancante/errata e archivi danneggiati.
- Limiti di dimensione, numero di file e controlli XML mantenuti anche sui contenitori interni.
- Dipendenze di cifratura incluse nell'immagine: aggiornare e ricostruire l'add-on.

## 5.15.0 — Percorso reale, aggiornamento dashboard e diagnostica

- Barra persistente con Salva bozza e Salva e continua alle associazioni.
- Riepilogo delle modifiche non salvate e del primo campo da completare.
- Controllo di nomi, ambienti, GA essenziali e comandi duplicati prima di continuare.
- Dettagli KNX, anteprime e strumenti manuali richiudibili.
- Aggiunta ETS con nome esplicito e apertura della funzione appena aggiunta.
- Avviso di uscita con modifiche ai widget o alla struttura non salvate.
- Aggiornamento esplicito della dashboard reale del progetto: confronto completo prima/dopo, backup persistente prima della scrittura, copia scaricabile e rilettura di verifica. Le personalizzazioni manuali sono sostituite, non unite.
- Confronto delle impronte per bloccare modifiche alla sorgente o alla dashboard successive all’anteprima. Nessun rollback automatico che possa sovrascrivere modifiche concorrenti.
- Registro passivo: finestra massima di 48 ore dalla ricezione (limite 10000 eventi), ricerca per mittente/GA/intervallo, paginazione e esportazione della prima pagina filtrata.
- Il registro richiede ancora riattivazione dopo riavvio/disconnessione. Accesso remoto e nuovi adattatori di protocollo restano da completare e collaudare.

## 5.14.0

- Confronto del progetto ETS aperto con i widget salvati: recupero selettivo delle funzioni riconosciute ma mancanti, senza sostituire nomi, stanze o associazioni esistenti.
- Ricerca per nome e indirizzo di gruppo. Gli altri GA non rappresentati sono consultabili e permettono la preparazione manuale di una funzione, con tipo scelto dall'installatore.
- Proposte discordanti, indirizzi già utilizzati in campi ausiliari e GA senza collegamenti richiedono revisione manuale. I comandi assenti dalla nuova importazione vengono segnalati, mai eliminati.
- Barra di percorso reale fra importazione, funzioni, associazioni, creazione delle entità mancanti e pubblicazione. Pulsante Salva e continua alle associazioni.
- Il recupero prepara soltanto widget in bozza, senza duplicare entità HA né inviare comandi. Necessario aprire il progetto ETS corretto e salvare le funzioni prima di generare la dashboard.

## 5.13.0

- Percorso Dashboard reale visibile nel menu e nell'avvio guidato: verifica widget, associa in blocco le entità esistenti, genera e pubblica la nuova plancia. Non occorre rinominare ID o eliminare dashboard.
- Entità NM LAB escluse da suggerimenti, selettori widget e generazione delle plance reali. Associazioni LAB precedenti segnalate e proponibili per sostituzione; proposte ambigue da verificare.
- Dashboard reale con Home, Ambienti e Funzioni, navigazione piano → stanza e popup nativi. Stati e comandi provengono dalle entità HA associate. Nessuna creazione di dispositivi duplicati.
- Pubblicazione conserva le vecchie plance; navigazione adattata anche a un percorso personalizzato. Avvisi per tutte le funzioni non pubblicabili.
- Percorso simulazione esplicitamente etichettato LAB. Test su esclusione simulazioni, L5/L15, ambiguità, popup e navigazione della dashboard pubblicata.

## 5.12.1

- Rinomine e spostamenti nell'editor Edificio ETS aggiornano anche le stanze delle funzioni nel configuratore guidato. Percorsi completi distinti: nessuna fusione di stanze omonime su piani diversi.
- Salva struttura e assegnazioni conserva la corrispondenza fra vecchi e nuovi percorsi. Ripresa e reimportazione del progetto applicano i nomi salvati senza modificare il riferimento ETS originale o le selezioni delle funzioni.
- Per le rinomine precedenti senza corrispondenza storica, riallineamento solo quando un widget dello stesso progetto e dello stesso GA indica una stanza univoca. Associazioni già valide nel catalogo e casi ambigui sono preservati.
- Il selettore stanze del laboratorio usa la gerarchia modificabile e le assegnazioni correnti. Pulsanti per aprire l'editor dal percorso guidato e tornare alla configurazione. Le modifiche alla dashboard HA richiedono ancora l'aggiornamento esplicito con backup.
- Test di persistenza, reimportazione, isolamento progetto, omonimie, rinomine successive e validazione dei percorsi. Le corrispondenze fanno parte del layout KNX salvato; conservarlo nel backup NM Studio.

## 5.12.0

- Pagina Collaudo KNX reale: scelta di una sola luce, dimmer o tapparella dai widget salvati, verifica accesso KNX, revisione configurazione, controllo conflitti e creazione esplicita tramite API già disponibili. Nessun cambio dei permessi dell'add-on.
- Creazione disabilitata senza accesso KNX, connessione, supporto piattaforma e conferme ETS/backup. Progetto ETS aperto diverso dai widget salvati blocca il percorso. I dati si correggono nei widget prima della verifica per conservare la coerenza delle associazioni.
- Dimmer senza GA luminosità assoluta e tapparelle senza arresto bloccati anche nel backend. Clima escluso dalla creazione diretta. Posizione tapparella non interpretata automaticamente come comando percentuale.
- Dopo la creazione: lettura dello stato HA, istruzioni per il collaudo fisico e accessi ad associazione, dashboard e diagnostica. Il configuratore non invia comandi di prova al bus. La prova sull'impianto resta da eseguire dall'installatore.
- Inclusi test dei blocchi, cancellazione conferma, invio singolo, mapping GA e pacchetto JavaScript. Aspetto e accesso API da verificare nella reale installazione HA; con permessi insufficienti resta disponibile la preparazione YAML.

## 5.11.0

- Icone dedicate per Luci, Motorizzazioni, Clima, Scene e Sensori. Rimosse le viste e i pulsanti Storico 48 ore dalle stanze LAB; lo storico resta accessibile dai popup nativi HA. Nessuna modifica alla registrazione o alla diagnostica bus.
- Ingresso installatore semplificato: navigazione principale compatta, strumenti avanzati raccolti, percorso reale e moduli opzionali separati dal laboratorio. Dopo l'importazione si vede il configuratore; dettagli ETS e reimportazione sono richiudibili.
- Passaggi LAB con istruzioni contestuali, Indietro/Continua, filtro Da assegnare e collegamento alla dashboard pubblicata. I filtri e la navigazione non invalidano più una verifica; cambiare le funzioni sì. Restano le conferme per scritture e sostituzioni.
- Riconoscimento stanze: nomi ETS con piano ripetuto, abbreviazione INTERR., preposizioni nei nomi, nome stanza specifico e distinzione del piano quando esplicito. Sensori e scene di fallback usano le stesse evidenze. Conflitti restano Da assegnare; nessuna deduzione dai numeri dei termostati.
- Per applicare il riconoscimento aggiornato reimportare il progetto ETS e rivedere le proposte; le correzioni manuali salvate sono conservate. Per aggiornare la grafica rigenerare la dashboard LAB con backup, senza reinstallare le entità.

## 5.10.1

- Dashboard LAB: piano → zona → entità, nomi brevi, icone stanza e schede a larghezza intera. Percorsi completi conservati come identità: edifici e zone omonime restano distinti.
- Tocco su scheda o icona apre il popup nativo HA. Storico 48 ore su richiesta e valori simulati in Strumenti LAB; nessuna dipendenza da HACS. Il grafico clima usa il solo sensore temperatura, evitando serie duplicate.
- Categorie raggruppate per piano e zona senza colonna di filtri. Percorsi stanza stabili quando si aggiungono altre zone. Funzioni di piano in Generali; stanze senza gerarchia in Altre zone.
- Aggiornare la dashboard dal passaggio 3 del wizard dopo l'aggiornamento del componente: backup e controllo impronte restano attivi. Nessuna reinstallazione delle entità necessaria. Limite viste adeguato al massimo di 200 zone con storico.
- Aspetto finale e popup da collaudare nell'installazione Home Assistant.

## 5.10.0

- Archivio locale di massimo 10 progetti ETS analizzati, salvataggio esplicito delle revisioni LAB e ripresa da Avvio guidato anche dopo riavvio. Nessun file .knxproj originale o credenziale salvato; sono conservati i dati estratti del progetto.
- Reimportazione dello stesso progetto: confronto di GA/funzioni/evidenze, conservazione delle correzioni manuali di nome e ambiente, nuova selezione richiesta per aggiunte e modifiche. Progetti senza GUID stabile possono essere riconosciuti solo dalla stessa esportazione. Nessuna eliminazione o migrazione automatica delle entità HA.
- Wizard LAB in tre passaggi, ricerca per nome/stanza/GA, filtro categoria, nome funzione modificabile; percorso separato per la preparazione reale e accesso alle planimetrie. Revisioni LAB distinte dalle approvazioni KNX reali.
- Salvataggio atomico, controllo revisioni concorrenti, backup della revisione precedente ed esportazione JSON del progetto. Il vecchio backup migrazione non include questi archivi: usare anche il backup completo HA. Importazione dei backup progetto non ancora esposta nell'interfaccia.
- Dashboard LAB aggiornabile esplicitamente sul medesimo percorso v2, con verifica impronte e backup prima della scrittura. Eventuali personalizzazioni vengono sostituite solo dopo conferma. Il pubblicatore generale resta create-only.
- Storico nativo HA di 48 ore nelle pagine stanza LAB e pressione prolungata per dettagli nelle schede LAB/reali. Richiede Recorder e dati già registrati.
- Diagnostica: consultazione dello storico KNX HA tramite API 2026.10, intervalli di 48 ore, filtro GA/mittente, pagine da 500 eventi ed esportazione della pagina. Non abilita la conservazione né garantisce copertura; richiede permessi HA amministratore. Nessun aumento dei privilegi, nessun telegramma KNX.
- Da collaudare nell'installazione HA: aspetto delle viste, permessi API, continuità e copertura dello storico. Aree HA native, provisioning reale completamente guidato, accesso remoto e integrazione completa delle planimetrie restano da completare.

## 5.9.6

- NM Control LAB: Home, indice Ambienti raggruppato per percorso edificio/piano, pagina dedicata a ogni stanza; Funzioni con Luci, Motorizzazioni, Clima, Scene e Sensori quando presenti, filtro per ambiente e ritorno alla pagina precedente.
- Home con luci accese, motorizzazioni aperte e clima. Le viste condividono le entità LAB esistenti. Crea una nuova dashboard sul percorso `-v2`, preservando la precedente; non reinstallare le entità per questa modifica.
- Diagnostica: registro KNX su richiesta per 1–32 GA, persistente (ultimi 10.000 eventi), consultazione/filtro/esportazione degli ultimi 500. Registra mittente, GA, direzione, tipo, data e valore decodificato se già disponibile. Nessuna lettura o scrittura di valori sul bus.
- L'avvio tenta la registrazione dei filtri locali `knx_event` in HA. Se mancano i permessi amministratore, ascolta gli eventi già configurati e indica come registrarli dall'interfaccia Azioni HA. Nessun aumento dei privilegi. I filtri non vengono rimossi per non interrompere altre automazioni.
- Registrazione da riattivare dopo riavvio/disconnessione; non è un monitor completo del bus e non certifica la consegna ai dispositivi. Conservazione a numero di eventi, non 48 ore garantite. Nessuna correzione automatica delle modalità climatiche.
- Test locali Python/JavaScript; collaudo visivo su HA e registrazione su impianto reale ancora necessari.

## 5.9.5

- LAB: ricostruisce la posizione comune dei dispositivi collegati dal ramo Edifici ETS; distingue la proposta fisica da un ambiente funzionale verificato. Include i piani nel menu.

## 5.9.4

- Laboratorio: applica le proposte ambiente ETS e mostra un menu esplicito delle stanze, con inserimento manuale sempre disponibile.

# NM Studio – Registro versioni

## 5.9.3

- Il laboratorio compare dopo ogni analisi ETS, anche senza termostati; mostra una diagnosi esplicita se non trova funzioni supportate.
- Selezione di fino a 200 funzioni, tipo virtuale e stanza modificabili prima della verifica: luci, dimmer, tapparelle, richiami scena, sensori numerici/binari e clima.
- Entità HA isolate per progetto (`nm_lab_<progetto>_*`), generate con helper e template moderni. Nessun indirizzo di gruppo viene configurato come destinazione KNX.
- Luci on/off, dimmer con luminosità, tapparelle con posizione istantanea e stop senza movimento, scene con registrazione del solo richiamo, sensori regolabili manualmente. Non viene simulata la fisica degli attuatori né ricostruito il contenuto delle scene ETS.
- Wizard per installazione e sostituzione di un precedente package NM Lab: conferme, impronte delle anteprime, backup del file sostituito e blocco delle modifiche concorrenti rilevate. File estranei e package KNX reali non vengono sovrascritti.
- Dopo il riavvio manuale di HA, verifica delle entità e pubblicazione separata di NM Control LAB con Panoramica casa e Ambienti. Nessuna modifica delle associazioni o dashboard KNX reali.
- Corretti riconoscimento dell'include packages sotto il blocco homeassistant, configurazione senza newline finale e installazione su Windows; rifiutata l'indentazione non standard per la modifica automatica.
- Test di regressione Python, handler HTTP, wizard JavaScript e workflow GitHub per Windows/Linux e validazione del package con Home Assistant 2026.10.4. Il collaudo su HA e impianto reale resta separato dai test locali.

## 5.9.2

- La procedura Laboratorio virtuale può attivare i pacchetti Home Assistant con un pulsante dedicato: propone l'aggiunta di `homeassistant.packages: !include_dir_named packages`, mostra l'anteprima e richiede conferma separata.
- Prima della modifica salva una copia di `configuration.yaml` nella cartella privata dell'add-on, quindi aggiorna il file in modo atomico; non riavvia Home Assistant automaticamente.
- Se `configuration.yaml` è stato modificato dopo l'anteprima, contiene già una direttiva `packages` diversa o presenta una struttura non standard, l'operazione viene rifiutata senza sovrascritture.
- Aggiunti test per backup, duplicazioni, configurazioni personalizzate e modifiche concorrenti. Il laboratorio resta virtuale e non interagisce con KNX.

## 5.9.1

- Primo laboratorio virtuale installabile dall'analisi ETS: dopo anteprima e conferma, crea un package Home Assistant con termostati `generic_thermostat`, sensori e interruttori virtuali; nessun collegamento al bus KNX.
- L'add-on richiede l'accesso alla configurazione HA ma può creare esclusivamente `packages/nm_lab_virtual.yaml`, senza modificare `configuration.yaml`, avviare riavvii o sovrascrivere un file differente.
- Se Home Assistant non ha già abilitato `packages: !include_dir_named packages`, l'installazione resta bloccata e mostra l'istruzione necessaria.
- Conferma obbligatoria e impronta SHA-256 dell'anteprima; test di idempotenza, duplicati, percorsi simbolici e separazione dei dati reali.

## 5.9.0

- Nuovo generatore Lovelace **NM Control** con schermata iniziale Panoramica casa, navigazione per Illuminazione, Climatizzazione, Schermature, Ventilazione, Sensori, Altri carichi e vista Ambienti.
- Le pagine di funzione raggruppano le schede reali per piano e zona, utilizzando esclusivamente i widget collegati a entità presenti nell'inventario Home Assistant.
- Ogni entità è una sola entità HA, riutilizzata in viste diverse; nessun valore di stato o dispositivo dimostrativo viene inventato. Widget incompleti e incompatibili rimangono nel report anomalie.
- Pubblicazione protetta: conferma esplicita, impronta della bozza, dashboard nuova e mai sovrascritta. Supportate fino a otto viste anziché una.
- Il progetto ETS di Beppe può guidare il futuro mapping degli ambienti, ma senza entità HA reali non vengono creati controlli operativi.

## 5.8.4

- Importer ETS: rilevamento prudente dei termostati organizzati per gruppo intermedio KNX, anche quando i nomi non indicano l'ambiente.
- Richiesti temperatura ambiente, setpoint manuale, setpoint corrente e comandi/stati HVAC univoci con DPT coerenti; caldo/freddo associato soltanto se il relativo GA è realmente collegato.
- Sul progetto reale `BEPPE VELLO` l'anteprima passa da 108 a 123 proposte, comprendendo 15 zone `climate`; le stanze senza evidenza rimangono da assegnare.
- Nessuna approvazione automatica, modifica Home Assistant o trasmissione KNX. Aggiunto test di regressione per ambiguità e DPT errati.

## 5.8.3

- Aumentato da 8 a 16 MB il limite di caricamento dei progetti `.knxproj` sia nell'importatore ETS sia nel confronto con i widget; controllo coerente anche sul server.
- Riconoscimento preliminare di circuiti ETS strutturati sulla base di ruoli e DPT verificabili, senza dipendere da mnemonici specifici L/T/Z: comandi e feedback sono raggruppati solo se univoci.
- Provati i file reali `LOSINE - NM CONTROL LAB` (34 GA) e `O.I.P.` (96 GA, archivio da circa 9,6 MB). Le proposte restano in anteprima e richiedono conferma dell'installatore.
- I cataloghi prodotto compressi molto grandi non vengono espansi nella lettura dei GA: la dimensione del file compresso non equivale alla dimensione massima dei singoli XML estraibili.

## 5.8.2

- Nel report di importazione ETS aggiunto un inventario preliminare HVAC/VMC dei GA con indizi di temperatura, setpoint, ventole, flap, modalità, umidità e ventilazione.
- Il riconoscimento si basa solo sui nomi ETS e sugli oggetti collegati, senza attribuire automaticamente la codifica dei valori proprietari di Zennio, Daikin o Intesis.
- Le proposte HVAC/VMC sono soltanto diagnostiche: nessuna entità, configurazione o telegramma viene creato o modificato.
- Aggiunti test di regressione per il riconoscimento HVAC e la presenza di tutti i moduli Python nell'immagine.

## 5.8.1

- Corretto il crash all'avvio dell'app: il Dockerfile ora include `recognition.py`, necessario per l'analisi ETS introdotta nella 5.8.0.
- Nessuna modifica ai dati salvati, ai comandi KNX o alle configurazioni Home Assistant.

## 5.8.0

- Avviato il motore di riconoscimento universale con un catalogo di funzioni e requisiti DPT (luce, dimmer, tapparella, climate).
- Ogni proposta riceve una revisione spiegabile: DPT confermato, dimensione compatibile, DPT mancante, conflitto oppure GA scollegato; le domande mirate vengono mostrate nel report ETS.
- Supportata la convenzione ETS per canale (`CH-2 - Dimming : OnOff`), indipendente dai nomi L1/T1: il progetto demo ufficiale KNX Virtual v2.5 passa da 0 a 6 proposte, senza creare o comandare entità automaticamente.
- Test reale su due progetti dimostrativi KNX Association: la demo luci/dimmer/tapparelle è leggibile; la demo HVAC ha XML interno cifrato e richiederà una futura importazione con password.
- Gli indicatori di attendibilità sono evidenze preliminari e non autorizzano mai comandi sul bus o creazioni HA.

## 5.7.0

- Dimmer KNX: l'analisi ETS propone anche regolazione relativa a 4 bit, luminosità assoluta e feedback della luminosità quando sono presenti collegamenti univoci al circuito; tutti i DPT restano da verificare.
- Le schede del generatore mostrano e salvano questi indirizzi aggiuntivi; anche i widget KNX li ricevono in automatico.
- Prima bozza termostati KNX/HVAC: temperatura ambiente, setpoint e feedback, scelta caldo/freddo e modalità operativa. Proposte automatiche soltanto da nomi ETS strutturati e univoci, altrimenti inserimento manuale.
- La bozza YAML Home Assistant include `knx.climate` solo con temperatura ambiente e feedback setpoint; non applica configurazioni e non invia telegrammi. Verificare DPT 9.001, 1.100 e 20.102, direzione e limiti del dispositivo.
- L'importazione Nuova FR non inventa termostati da semplici indirizzi di temperatura.

## 5.6.1

- Corretto l'abbinamento tra `ON/OFF L5` e feedback `STATO LED L5` (analogamente L6/L7) quando il feedback appartiene a un canale luce numerato. La variante di nome ETS non impedisce più la proposta del circuito.
- La regola rimane circoscritta a `LED L` seguito da un numero, senza accorpare indiscriminatamente le segnalazioni LED di altre funzioni.
- I circuiti sono sempre bozze da verificare; nessuna entità HA viene creata o comandata automaticamente.

## 5.6.0

- Nell'analisi del vecchio YAML aggiunta «Ricostruzione circuiti · anteprima»: raggruppa le voci che utilizzano lo stesso GA di comando e le confronta con i widget ETS già salvati.
- Evidenzia separatamente i nomi compatibili con feedback, i possibili conflitti tra indirizzi di stato e l'assenza di una funzione ETS corrispondente.
- Distingue il caricamento ETS, necessario alla creazione da zero, dall'audit facoltativo del vecchio YAML, utile nelle migrazioni. Nessuna entità viene modificata.

## 5.5.0

- Analisi in sola lettura di una copia YAML KNX caricata dall'installatore: gruppi di indirizzi ripetuti e possibili feedback erroneamente configurati come luci separate.
- Il file viene analizzato in memoria e non viene applicato alla configurazione Home Assistant.

## 5.4.1

- Corretto il formato dell'indice restituito da `knx/get_entities_by_group`: Home Assistant fornisce record con `platform`, `unique_id`, `ui` e `disabled`, non una lista di stringhe `entity_id`.
- Consultazione aggiuntiva, in sola lettura, del registro entità Home Assistant per collegare gli identificatori interni KNX agli `entity_id` reali, quando accessibile.
- Se il registro non è accessibile, l'interfaccia indica che il GA è in uso, senza inventare un'associazione certa. I record disabilitati e quelli provenienti da YAML restano visibili.
- Risolve i falsi «collegamenti non interpretabili» osservati su Nuova FR. Nessuna modifica al KNX o alle entità HA.

## 5.4.0

- Prima funzione di inventario operativo nell'area «Genera HA»: confronto in sola lettura dei GA di comando/feedback dei widget ETS con l'indice delle entità registrate nel pannello KNX ufficiale di Home Assistant.
- Classificazione prudente di funzioni coerenti, associazioni sospette, funzioni da associare, da verificare o senza entità rilevata sul GA di comando; elenco dei nomi delle entità KNX effettivamente collegate al GA.
- Analisi utilizzabile anche quando il progetto ETS non è ricaricato nel browser, poiché si basa sui widget salvati e sull'indice KNX corrente.
- Se l'API KNX è negata all'add-on, la schermata mostra un limite di permessi e non inventa risultati.
- Nessuna modifica ai GA o alle entità, nessun telegramma, nessuna installazione automatica. La procedura già esistente di creazione controllata delle sole entità mancanti resta separata e richiede conferme e backup.

## 5.3.0

- Prima riconciliazione tra nome del GA di comando ETS e inventario Home Assistant, con identificatori circuito (es. L11) e distinzione esplicita dei nomi compatibili con feedback.
- La pagina «Associa entità» mostra candidati a un comando e avvisa quando l'associazione attuale sembra riferirsi al feedback.
- «Proponi … (solo bozza)» applica la selezione **soltanto al modulo aperto**, senza salvataggio né comandi e senza modificare le associazioni di altri widget. Il normale pulsante «Conferma e salva» resta l'unico punto di persistenza.
- Si evita di proporre automaticamente candidati con nomi fisici ambigui (es. pulsantiera/scatola), identificatori diversi o punteggio non univoco.
- I nomi HA non dimostrano la configurazione KNX sottostante: prima della conferma è ancora richiesta la verifica dell'indirizzo di comando nell'entità Home Assistant.

## 5.2.0

- Nella pagina «Associa entità» aggiunto il caricamento opzionale del progetto ETS in sola lettura, senza alterare le bozze widget o la programmazione.
- Confronto vincolato alla stessa impronta del progetto ETS usato per salvare i widget, per evitare di mostrare associazioni tra impianti diversi.
- Dettagli espandibili per widget con i GA di comando, feedback, dimmer e tapparelle già salvati; dalla lettura ETS vengono mostrati nomi, DPT, dispositivi, oggetti e flag disponibili.
- Segnalazione di GA non trovati, indirizzi senza oggetti collegati e DPT mancanti. La direzione assegnata al GA nel widget resta un'ipotesi da confermare, e non è possibile dimostrare l'associazione entità HA↔GA dalla sola API degli stati.
- Nessuna modifica automatica alle entità HA e nessun invio telegrammi KNX.

## 5.1.0

- Prima analisi conservativa delle entità HA per riconciliazione con le funzioni ETS: nomi con «notifica/feedback» segnalati come probabili oggetti di stato, etichette «pulsantiera/scatola di derivazione» marcate come ambigue.
- Le entità sospette non sono più suggerite automaticamente come comandi, ma rimangono selezionabili dall'installatore, con avvisi visibili e senza modificare le associazioni già salvate.
- La pagina «Associa entità» presenta il conteggio delle entità che richiedono verifica, la motivazione per ciascuna scelta e l'avviso aggiornato cambiando selezione.
- La planimetria propone inizialmente le entità già associate ai widget ETS, con opzione per mostrare tutte le entità HA e mantenendo la possibilità di ripetere una luce sulla pianta.
- Classificazione solo euristica basata sui nomi: non equivale a verifica automatica di GA, DPT, direzione o flag di comunicazione. Nessun comando né modifica KNX/HA.

## 5.0.0

- Generazione di dashboard HA `picture-elements` a partire dalle planimetrie salvate: ogni punto con entità HA presente viene rappresentato mediante un `state-icon` nativo nella posizione originale.
- Più faretti possono condividere una sola entità ed essere mostrati in punti differenti; luci/switch usano l'azione nativa `toggle`, gli altri domini aprono i dettagli nativi `more-info`.
- Anteprima e audit dei punti senza entità, esportazione JSON, pubblicazione esplicita in una dashboard **nuova** senza sovrascrivere dashboard esistenti.
- Immagine incorporata nel JSON come data URL per evitare interventi manuali su `/config/www`; compatibilità con il frontend Home Assistant reale ancora da verificare. Non sono previste modifiche a file di configurazione HA.
- Nessun comando dal configuratore NM Studio; cliccare gli elementi sulla dashboard pubblicata può inviare comandi reali Home Assistant/KNX.

## 4.9.0

- Corretto il caricamento della planimetria in browser: la Content Security Policy ora consente le immagini locali `data:` e `blob:` necessarie all'editor.
- L'importazione converte automaticamente PNG/JPEG/SVG in un raster compatibile e prova la compressione JPEG quando il PNG supera il limite di 2 MB.
- Elenco ricercabile delle entità Home Assistant già presenti, con inserimento rapido di simboli sulla planimetria.
- Più simboli possono riferirsi alla stessa entità HA, per rappresentare ad esempio quattro faretti comandati dallo stesso circuito KNX.
- Simboli personalizzabili (faretto, downlight, striscia LED, lampadina, sospensione, applique, tapparella, sensore e altri); le posizioni restano indipendenti dal legame entità.
- Evidenziazione dei simboli collegati a entità HA attualmente accese/aperte, basata sull'ultimo stato letto. Nessun comando emesso dalla planimetria.
- I vecchi archivi delle planimetrie sono compatibili: ai punti senza icona o entità si applicano valori predefiniti.

## 4.8.0

- Prima attivazione reale dal pannello «Genera HA»: dopo revisione ETS, piano di creazione e backup confermato, l'installatore può creare una singola entità KNX tramite le API ufficiali `knx/validate_entity` e `knx/create_entity`.
- Controllo in tempo reale degli indirizzi già presenti nell'indice KNX Home Assistant, conferma esplicita del contenuto della richiesta e arresto sui conflitti noti. Creazione una entità alla volta, senza modificare quelle esistenti.
- Se il token dell'add-on non ha permessi amministrativi, la creazione viene rifiutata e rimane utilizzabile il piano di esportazione; nessuna elevazione automatica dei privilegi.
- La creazione può inizializzare letture KNX; le successive prove di comando richiedono un collaudo esplicito sul sistema reale.
- Non è ancora prevista la creazione in massa o l'attivazione NM Link. I GA definiti in YAML non sono sempre censiti dall'indice KNX: permane la verifica ETS/HA manuale.

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
