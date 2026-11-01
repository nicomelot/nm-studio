# Preparazione del repository GitHub NM Studio

Questo progetto è già organizzato come repository di app per Home Assistant:

- `repository.yaml` alla radice;
- `nm_bridge/config.yaml` con versione incrementale;
- `nm_bridge/Dockerfile` e sorgenti Python/HTML;
- `nm_bridge/CHANGELOG.md` e `DOCS.md`.

## Prima di pubblicare

1. Creare il repository `nicomelot/nm-studio` su GitHub e decidere se il sorgente può essere pubblico.
2. Il file `repository.yaml` punta già a `https://github.com/nicomelot/nm-studio`.
3. Verificare che il repository non contenga token, backup, file ETS clienti o configurazioni private.
4. Pubblicare solo codice, documentazione e i file dell'app. Escludere ZIP locali, `__pycache__` e file di test temporanei dalle release.
5. Aggiungere l'URL repository nell'App store dell'istanza laboratorio e verificare l'installazione.

## Migrazione locale una tantum

1. Eseguire prima un backup completo di Home Assistant.
2. Con NM Studio **locale 3.6.0** aprire **Avvio guidato → Scarica backup NM Studio**.
3. Verificare che il file JSON sia stato scaricato e custodirlo in modo sicuro.
4. Installare NM Studio dal nuovo repository GitHub **senza eliminare il vecchio add-on**.
5. Sulla nuova installazione, in **Avvio guidato**, selezionare il backup JSON e premere **Verifica e importa**.
6. L'importazione richiede conferma, verifica SHA-256 e schema ed è consentita da interfaccia solo su un archivio di destinazione vuoto.
7. Ricaricare l'interfaccia, confrontare i dati e provare le funzioni in sola lettura.
8. Conservare il vecchio add-on per un periodo di osservazione. Disinstallarlo solo dopo verifica completa e backup.

## Aggiornamenti successivi

Per ogni release modificare `nm_bridge/config.yaml` (versione diversa e crescente), aggiornare il changelog e pubblicare il commit sul repository GitHub. Home Assistant potrà rilevare l'aggiornamento dalla scheda App. Non c'è bisogno di Tailscale per scaricare il codice da GitHub.
