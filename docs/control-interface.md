# NM Control 5.21.0

La pagina iniziale dell'add-on usa i widget e gli ambienti già salvati nel progetto NM Studio. `advanced` conserva importazione ETS, associazioni HA, collaudo, mappe, dashboard, diagnostica e recupero. Nessuna migrazione del layout è richiesta. La vista utente è una semplificazione visiva, non un ruolo di autorizzazione.

## Utilizzo

Da Dispositivi si può aprire un dettaglio, inviare un comando verificato o creare un programma. Ambienti permette di creare stanze e assegnare le funzioni esistenti conservandone indirizzi e associazioni. Le nuove funzioni ETS si gestiscono negli strumenti avanzati.

Scenari combina fino a 50 azioni. Programmazioni usa le stesse azioni per luci, dimmer, tapparelle e termostati, con fino a 64 fasce e giorni selezionabili. Un programma può quindi comandare più dispositivi insieme. Per un termostato selezionare una singola azione Temperatura e usare il modello settimanale modificabile: ogni fascia può avere un setpoint diverso. Il setpoint rimane fino al comando successivo; la modalità riscaldamento/raffrescamento si imposta separatamente sul termostato o in uno scenario.

Ogni salvataggio mette il programma in pausa, anche quando si modifica un programma attivo. Anteprima mostra destinatari, valori e le prossime occorrenze; Attiva abilita l'esecuzione. Pausa la interrompe. Il registro distingue accettazione da parte di HA, errore ed esito non confermato: l'accettazione non prova il movimento o lo stato fisico del dispositivo.

## Orari e disponibilità

- Il motore gira nell'add-on anche a browser chiuso; Home Assistant e l'add-on devono restare accesi. Verificare Avvio all'accensione nelle installazioni già esistenti; il valore predefinito delle nuove installazioni è automatico.
- Fuso, latitudine, longitudine e quota provengono dalla configurazione HA. Alba/tramonto sono calcolati con Astral; scostamenti da -180 a +180 minuti. Il giorno selezionato è quello dell'evento solare prima dello scostamento.
- Controllo ogni 10 secondi, tolleranza 60 secondi. Nessun recupero degli orari più vecchi o precedenti all'attivazione. Dopo un'interruzione il termostato mantiene il valore corrente fino alla fascia successiva.
- Al cambio d'ora, gli orari inesistenti sono saltati e quelli ripetuti eseguiti una sola volta. Nei giorni senza alba/tramonto non si esegue quell'evento.
- Anteprima e attivazione bloccano comandi diversi contemporanei sui medesimi dispositivi nei prossimi 8 giorni. Non rilevano automazioni esterne HA né garantiscono l'assenza di coincidenze solari oltre tale finestra.
- Supportati solo comandi compatibili con le capacità dell'entità. I generali OFF restano solo spegnimento; i comandi KNX di luci e tapparelle conservano il controllo di allineamento con l'installazione.

## Dati e recupero

Scenari e programmi sono isolati per progetto in `/data/nm_control_automations.json`; il registro persistente è `/data/nm_control_runs.sqlite`. Rinominare o spostare una funzione mantiene i collegamenti, cambiarne indirizzi o entità li invalida e richiede revisione. Cambiando progetto vengono eseguiti solo i suoi programmi.

Il registro viene scritto prima dell'invio: riavvii e richieste duplicate non reinviano lo stesso evento. Una perdita di connessione durante l'invio può lasciare un esito incerto; non viene ritentata automaticamente. Gli eventi conservati coprono 90 giorni, con le ultime 100 righe visibili.

Il backup completo dell'add-on include entrambi i file. L'esportazione diagnostica include la configurazione delle automazioni, ma il vecchio pacchetto portabile di migrazione non le ripristina: per trasferire anche programmi e registro usare il backup completo HA dell'add-on. Non ripristinare configurazioni attive su un impianto diverso senza riesaminarle.

## Verifica

`python -m unittest discover -s tests` e `node --test tests/*.test.js` verificano il progetto. `python tests/control_preview.py --port 8766` apre un laboratorio locale con dati sintetici e servizi simulati, senza programmatore in esecuzione. Non è un server di produzione. Il collaudo su HA con dispositivi fisici resta distinto dai test simulati.


## Sinottici, planimetrie e widget aggiuntivi (5.24)

Nella nuova interfaccia aprire Sinottici o Planimetrie, creare uno schema e scegliere Modifica. Caricare un PDF (pagina selezionabile, massimo 12 MB) oppure PNG/JPG; lo sfondo viene rasterizzato fino a 2000 px e conservato nel progetto. Aggiungere componenti, trascinarli oppure inserire X/Y, collegarli ai dispositivi e salvare. Uso apre i dettagli/comandi del dispositivo; Modifica non invia comandi. Le planimetrie precedenti si importano come copie, senza modificare gli originali.

Dispositivi → Aggiungi widget collega sonde HA di classe temperatura e pulsanti momentanei a entità light/switch/input_boolean dedicate. Il comando 1 corrisponde a turn_on, 0 a turn_off; non invia telegrammi KNX arbitrari. Per un impianto KNX occorre prima una corretta entità HA associata. Sonde e pulsanti sono salvati separatamente dalle funzioni ETS e compaiono anche nel selettore dei componenti.

Il pulsante richiede abilitazione esplicita per ogni apertura. Pointer-up/cancel, perdita del fuoco, tastiera e chiusura della finestra richiedono il reset. Un registro SQLite conserva il reset prima dell’accensione. L’add-on tenta OFF entro 10 secondi e recupera i reset dopo riavvio; se HA/rete/add-on non sono operativi, il rilascio fisico non è garantito. Non è un dispositivo di sicurezza. Le richieste duplicate e i rilasci arrivati prima delle pressioni non riaccendono il comando.

Gli schemi sono separati per progetto e verificano una versione dell’archivio al salvataggio. Lo sfondo conserva il rapporto d’aspetto; zoom e scorrimento restano nel riquadro, il pannello di modifica passa sotto lo schema su tablet/telefono. I simboli usano coordinate percentuali e una legenda leggibile anche su display piccoli.
