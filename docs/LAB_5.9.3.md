# Collaudo NM Studio 5.9.3

## Percorso installatore

1. Installa la versione contenente questa modifica nell'istanza Home Assistant di laboratorio.
2. In **Importa ETS**, analizza il progetto `.knxproj`. Il pannello **Laboratorio virtuale** compare anche se non ci sono termostati.
3. Seleziona le funzioni da simulare e controlla tipo e stanza. Le proposte sono ipotesi per la simulazione, non approvazioni per l'impianto reale. I sensori e le scene senza DPT riconoscibile possono non essere proposti.
4. Premi **Verifica laboratorio**. Se necessario usa **Abilita pacchetti HA**, che salva prima un backup della configurazione. Configurazioni personalizzate non riconosciute richiedono verifica dell'installatore.
5. Premi **Installa entità virtuali**. Se esiste un laboratorio NM differente, il pulsante propone **Sostituisci laboratorio con backup** e una conferma separata. Il package precedente viene salvato in `/data/nm_lab_backups` nell'add-on.
6. Da Home Assistant verifica la configurazione e riavvia HA. NM Studio non esegue riavvii automatici.
7. Torna al pannello e premi **Verifica entità dopo riavvio HA**, poi **Crea NM Control LAB**. Se hai ricaricato la pagina, reimporta lo stesso ETS e ripristina la stessa selezione di funzioni e stanze.
8. Apri **NM Control LAB** nella barra laterale di HA. Prova luci, dimmer, posizione tapparelle, richiamo scene e valori dei sensori in Panoramica casa e Ambienti.

Non occorre inserire manualmente YAML nelle configurazioni standard supportate. La pubblicazione usa le API Lovelace di HA: permessi insufficienti vengono riportati come errore, senza modificare il ruolo amministrativo dell'add-on.

## Limiti verificabili

- Tapparelle: posizione immediata 0–100; stop conserva la posizione. Nessun tempo di corsa, finecorsa o interblocco fisico simulato.
- Scene: un pulsante registra il richiamo. Non ricostruisce le azioni memorizzate negli attuatori ETS.
- Sensori: ingresso numerico o binario regolabile manualmente; non sono misure dell'impianto e non viene indovinata l'unità di misura.
- Termostati: generic_thermostat con sensore e relè virtuali; nessun modello termico automatico.
- Una sola configurazione di laboratorio attiva nel package. Sostituendola, le entità precedenti non sono più fornite dal package dopo il riavvio. Le vecchie dashboard LAB non vengono eliminate automaticamente.
- Le dashboard esistenti non vengono sovrascritte. Per ripubblicare lo stesso progetto, eliminare consapevolmente da HA la precedente dashboard LAB oppure usare quella già pubblicata.
- Se sono stati rinominati gli entity_id da HA, la verifica segnala le entità mancanti; non associa automaticamente dispositivi reali con nomi simili.
- Il wizard non conserva ancora la selezione al ricaricamento della pagina.

## Separazione dal collaudo reale

Il package virtuale contiene solo input_boolean, input_number, input_button, template e generic_thermostat. Le azioni generate puntano esclusivamente agli helper NM Lab. Non contiene configurazione KNX, MQTT, Modbus o Vimar. Non modifica i widget KNX approvati.

La creazione reale KNX resta nel percorso esistente, con verifica ETS, backup confermato, anteprima aggiornata, controllo duplicati e conferma per dispositivo. Un test virtuale riuscito non verifica indirizzi di feedback, direzioni, DPT, cablaggi o comportamento del bus. Prima del cantiere servono backup HA e collaudo reale progressivo. Modbus/Vimar/MQTT non sono implementati da questa versione.

## Verifica sviluppo

```text
python -m unittest discover -s tests -v
node --test tests/lab_ui.test.js
python -m compileall -q nm_bridge tests
```

Il workflow GitHub esegue la suite su Linux e Windows e valida una configurazione con tutti i tipi virtuali tramite il comando check_config ufficiale di Home Assistant 2026.10.4. Tale verifica controlla lo schema, non sostituisce avvio, interazione visiva e prova dell'add-on su HA OS.

Riferimenti schema: https://www.home-assistant.io/integrations/template/ e https://www.home-assistant.io/integrations/input_button/.
