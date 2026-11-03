# NM Studio 5.10.0 — configurazione riprendibile

## Primo utilizzo

1. Aggiornare NM Bridge e ricaricare l'interfaccia web.
2. In Avvio guidato scegliere **Importa / aggiorna ETS** e analizzare il progetto.
3. Nel percorso LAB controllare nomi, categorie, stanze e selezioni; ricerca e filtro non cambiano la selezione.
4. Dare un nome al progetto e premere **Salva progetto e revisione**. Questa operazione salva dati nell'add-on, senza modificare HA o il bus.
5. Usare il menu Passaggio: **Ambienti e funzioni → Installazione LAB → Verifica e dashboard**.
6. Se il package è già installato e non è cambiata la selezione/tipologia delle funzioni, passare alla verifica delle entità. Modifiche ai nomi possono invece richiedere l'aggiornamento del package se si vuole cambiarli anche nelle entità HA.
7. Creare la dashboard o aggiornarla con conferma e backup. Una personalizzazione manuale della dashboard viene sostituita dal nuovo contenuto generato; il backup viene salvato prima della scrittura.

Il pulsante **Preparazione impianto reale** apre il percorso tecnico esistente. Le revisioni LAB non approvano gli indirizzi KNX, non creano automaticamente le Aree native HA e non sostituiscono il collaudo dei feedback.

## Ripresa e reimportazione

- Avvio guidato elenca fino a 10 progetti salvati; **Riprendi** ricarica il progetto e le revisioni LAB dopo la chiusura del browser o il riavvio dell'add-on.
- Analizzare una nuova esportazione dello stesso progetto produce un confronto con la revisione salvata. Il confronto non scrive nulla finché non si salva.
- L'identità ETS, quando disponibile, mantiene il collegamento tra esportazioni. Senza GUID stabile il riconoscimento si limita alla stessa esportazione; non si fondono automaticamente progetti diversi.
- Le correzioni manuali a nome e stanza restano proposte. Una funzione modificata nelle evidenze o appena aggiunta richiede una nuova selezione. Le funzioni rimosse vengono segnalate ma non cancellate da HA.
- Se un altro browser ha salvato nel frattempo, il salvataggio è rifiutato: riprendere il progetto prima di procedere.
- Il salvataggio conserva la revisione precedente in `.bak`. Il JSON scaricabile contiene i dati estratti ETS e le revisioni; non include token. Il ripristino di questi JSON non ha ancora un pulsante nell'interfaccia.
- Il precedente backup migrazione non comprende questo nuovo archivio né le mappe: conservare anche un backup completo HA che includa l'add-on.

## Storico e diagnostica

Le pagine stanza della dashboard LAB includono grafici nativi delle ultime 48 ore. Il termostato include anche la temperatura simulata. La pressione prolungata su una scheda apre i dettagli HA. Servono Recorder attivo e dati già raccolti: i periodi mancanti non vengono inventati.

In Diagnostica, **Storico KNX di Home Assistant** consulta un intervallo di 48 ore, con fine intervallo selezionabile negli ultimi 30 giorni, filtro GA e mittente. Le pagine contengono al massimo 500 telegrammi; l'esportazione riguarda la pagina visualizzata, non l'intero intervallo.

Il backend usa solo `knx/get_base_data` e `knx/query_telegrams`, verificati sul sorgente HA 2026.10.4. Queste API richiedono privilegi amministratore. La release non aumenta il ruolo dell'add-on: se l'accesso è negato, mostra un messaggio e resta disponibile il pannello KNX nativo di HA o il registro locale della 5.9.6.

La conservazione dei telegrammi va impostata nell'integrazione KNX HA. Un intervallo richiesto di 48 ore non prova che l'archivio sia completo: contano la retention, il limite di eventi, lo stato dell'archivio e le interruzioni di connessione. Questa versione non certifica ancora la continuità delle 48 ore.

## Verifica prima della consegna

- Riaprire un progetto salvato e confrontare nomi, stanze e selezioni.
- Reimportare un'esportazione modificata e verificare aggiunte, modifiche e rimozioni senza duplicati.
- Verificare la dashboard LAB su telefono e desktop, navigazione e storico.
- Verificare un aggiornamento della dashboard e l'esistenza del backup.
- Sul laboratorio con KNX, verificare accesso allo storico, filtro mittente, paginazione e conservazione; assenza di permessi deve produrre un messaggio esplicito.

Restano da completare: assegnazione alle Aree native HA, wizard unico per il provisioning reale, remoto ETS/cliente, integrazione completa delle planimetrie e diagnostica di continuità. Il codice presente non equivale a un collaudo effettuato nell'impianto del cliente.
