# NM Studio 5.15.0 — verifica e punti aperti

## Implementato

- Percorso funzioni: barra salvataggio persistente, dettagli richiudibili, controllo campi e duplicati, avviso di uscita.
- Recupero ETS: pulsanti nominativi e apertura della scheda aggiunta; riepilogo delle proposte mancanti.
- Dashboard reale: aggiornamento del percorso canonico del progetto con confronto completo, backup persistente e scaricabile, verifica delle impronte e rilettura dopo scrittura.
- Diagnostica: migrazione del registro SQLite, finestra massima 48 ore dalla ricezione, cap di 10000 eventi, filtri GA/mittente/orari e paginazione a 500 eventi.

## Collaudo richiesto

Verificare in Home Assistant la barra a zoom 100% e su telefono, il recupero di L5/L6/L7, il salvataggio e la riapertura. Su una dashboard di prova, scaricare la copia precedente, aggiornare e verificare viste, nomi e collegamenti. La sostituzione conserva le personalizzazioni nel backup, senza unirle. Per ripristinare manualmente usare il JSON scaricato nell’editor della stessa dashboard HA.

L’API HA non offre qui un confronto atomico con la scrittura: viene riletto il contenuto immediatamente prima di salvare, ma resta una breve finestra di concorrenza con editor esterni. Evitare modifiche simultanee. Non viene eseguito rollback automatico.

## Obiettivo ancora aperto

- Collaudo fisico completo di luci DALI, tapparelle, comando e feedback; configurazione L11 da verificare.
- Verifica grafica in un browser controllabile: il tentativo headless locale non ha restituito un risultato utilizzabile.
- Diagnostica: ripresa automatica dopo disconnessione/riavvio, copertura garantita di 48 ore e segnalazioni dei cambi di modalità ancora da progettare/collaudare.
- Planimetrie: esiste la generazione Picture Elements; restano collaudo completo, aggiornamento e ripristino.
- Accesso remoto cliente/installatore: richiede configurazione e verifica della rete; nessuna porta o impostazione DNS modificata.
- Climatizzatore: marca, modello e protocollo non disponibili.
- Collegamenti KNX/Modbus/MQTT/Vimar: NM Link contiene ancora bozze simulate; non è un ponte operativo.
- Backup e ripristino complessivi, ruoli cliente/installatore e riavvio da collaudare.

CreateGoal non è esposto nella sessione: nessun goal automatico è stato attivato. Questo documento registra evidenze e lavoro residuo, non dichiara completato l’obiettivo.
