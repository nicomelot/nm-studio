# NM Studio / NM Control — obiettivo condiviso, 3 novembre 2026

NM Studio è il configuratore dell'installatore. NM Control è la supervisione del cliente. Home Assistant è il motore locale. Il funzionamento ordinario non deve dipendere dalla connessione Internet.

## Stato della 5.9.6

- Importazione ETS con estrazione della struttura edificio e proposte di funzioni/ambienti. Le deduzioni da posizione fisica sono proposte da verificare: un attuatore nel quadro non localizza necessariamente il carico.
- Laboratorio con entità virtuali e dashboard Home / Ambienti / Funzioni; pagina per stanza e filtri per ambiente. Non equivale a un impianto reale collaudato.
- Registro iniziale di eventi KNX su GA selezionati: 10.000 eventi, ultimi 500 consultabili/esportabili, riattivazione dopo disconnessione/riavvio. Non garantisce 48 ore né copertura completa del bus.
- Planimetrie: editor e generatore Picture Elements già presenti, associazione dei punti alle entità. Collaudo end-to-end ancora necessario.
- Pubblicazione 5.9.6: test automatici locali; rendering HA e monitor su bus reale da collaudare.

## Prodotto atteso e criteri di completamento

| Area | Risultato atteso | Lavoro restante |
| --- | --- | --- |
| Importazione | Importo `.knxproj`, ritrovo edificio, piani, stanze e funzioni nelle posizioni corrette | Gerarchia canonica, revisione delle ambiguità e assegnazione alle Aree HA; feedback e comandi distinti |
| Configuratore | Procedura guidata senza modificare YAML | Importa → verifica edificio → verifica funzioni/GA → scegli LAB o impianto → anteprima → backup/applica → collaudo → consegna |
| Navigazione | Home compatta, Ambienti e Funzioni sulle stesse entità; interfaccia chiara su telefono e tablet | Consolidare grafica, preferiti e passaggio verificato dal LAB alle entità reali |
| Diagnostica | Ultime 48 ore ricercabili per ora, GA, mittente, tipo, valore e funzione | Integrare lo storico KNX nativo HA, conservazione temporale, continuità e segnalazione dei buchi; esportazione dell'intervallo |
| Storico entità | Luce: linea temporale; termostato: temperatura, setpoint, modalità; sensore: grafico | Collegare Recorder/History alle schede NM Control; nessuna misura di consumo dedotta dal solo stato ON/OFF |
| Remoto cliente | Accesso semplice tramite app/link e account personale | Onboarding remoto, permessi cliente, autenticazione e revoca |
| Remoto installatore | ETS tramite VPN e interfaccia KNX/IP | Collaudo con Tailscale/subnet routing e tunneling ETS; separazione accessi tra cantieri |
| Planimetria | Sfondo per piano, punti luce e altri dispositivi posizionabili, stato e comando | Integrare l'editor nel wizard e verificarlo su HA e dispositivi mobili |

## Ordine di lavoro proposto

1. Wizard e modello stabile edificio/funzione/entità, verificati con Beppe Vello e Nuova FR. Reimportazione senza duplicati e senza perdere correzioni manuali.
2. Consolidamento delle viste e dello storico; collaudo di una luce, dimmer, tapparella, termostato e sensore reali.
3. Diagnostica di 48 ore con controllo della copertura e confronto modalità impianto/termostati; segnalazioni prima di eventuali correzioni automatiche.
4. Accessi remoti distinti per cliente/installatore, planimetrie e procedura di consegna.
5. Integrazioni Modbus, Vimar e MQTT tramite HA, previa verifica dei gateway effettivi del cliente.

## Idee utili alla prima consegna

- Reimportazione differenziale con anteprima di aggiunte, modifiche e rimozioni.
- Verifica disponibilità, feedback assenti e discrepanze tra comando e stato.
- Backup prima di ogni applicazione e ripristino guidato.
- Rapporto di collaudo con esito per funzione e anomalie ancora aperte.
- Profilo cliente semplificato e profilo installatore con diagnostica.

Le sezioni di lavoro restante sono obiettivi, non funzionalità dichiarate come già completate.
