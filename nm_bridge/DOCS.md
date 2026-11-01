# NM Studio – Home Assistant

## Aggiornamenti da repository

Una volta pubblicato questo progetto in un repository GitHub accessibile al Supervisor:

1. Home Assistant → Impostazioni → App → Installa app → menu **Repository**.
2. Inserisci l'URL HTTPS del repository GitHub effettivo.
3. Installa **NM Bridge (read-only laboratory)** dal nuovo repository.
4. In seguito gli aggiornamenti verranno rilevati da Home Assistant quando la versione in `config.yaml` aumenta. Premi **Aggiorna** dalla scheda dell'app.

Il vecchio add-on locale (`local_nm_bridge`) e quello del repository avranno ID diversi e dati separati. **Prima di disinstallare il vecchio add-on**, scarica il backup nella nuova pagina **Avvio guidato → Backup e migrazione** e verificalo sul computer. Installa il nuovo add-on, poi importa il backup nella nuova installazione. Controlla che stanze, widget, associazioni e NM Link siano presenti. Conserva sia il backup di Home Assistant sia il file JSON prima di eliminare il vecchio add-on.

Non installare sull'impianto in produzione prima di avere completato il collaudo in laboratorio. Nessuna operazione di migrazione invia telegrammi KNX.
