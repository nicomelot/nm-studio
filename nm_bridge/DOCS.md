# NM Studio – Home Assistant

## Aggiornamenti da repository

Una volta pubblicato questo progetto in un repository GitHub accessibile al Supervisor:

1. Home Assistant → Impostazioni → App → Installa app → menu **Repository**.
2. Inserisci l'URL HTTPS del repository GitHub effettivo.
3. Installa **NM Bridge (read-only laboratory)** dal nuovo repository.
4. In seguito gli aggiornamenti verranno rilevati da Home Assistant quando la versione in `config.yaml` aumenta. Premi **Aggiorna** dalla scheda dell'app.

Il vecchio add-on locale (`local_nm_bridge`) e quello del repository avranno ID diversi e dati separati. **Prima di disinstallare il vecchio add-on**, scarica il backup nella nuova pagina **Avvio guidato → Backup e migrazione** e verificalo sul computer. Installa il nuovo add-on, poi importa il backup nella nuova installazione. Controlla che stanze, widget, associazioni e NM Link siano presenti. Conserva sia il backup di Home Assistant sia il file JSON prima di eliminare il vecchio add-on.

Non installare sull'impianto in produzione prima di avere completato il collaudo in laboratorio. Nessuna operazione di migrazione invia telegrammi KNX.


### Rete, UniFi e prese (5.33)

In **Rete → Esempio simulato** si crea uno schema da salvare con tre prese (collegata, scollegata, non disponibile). Nessuna chiamata UniFi o comando PoE viene inviato. I dati simulati sono sempre etichettati.

Per l'impianto reale, configura UniFi Network in Home Assistant. In **Planimetrie → Modifica schema**, seleziona una presa dati, compila rack, patch panel, porta patch, switch e porta switch, quindi **Associa sensore UniFi**. Scegli il dispositivo e il sensore della porta corretta; per un sensore di velocità seleziona **Velocità porta** (zero = scollegata). Non usare traffico RX/TX né stato PoE come stato link. Sensori disabilitati devono essere abilitati in HA. Se il modello/integrazione non espone lo stato, rimane non disponibile: non è inventato. Salva lo schema.

La vista Rete mostra solo le porte documentate, con ricerca, avviso duplicati e collegamento alla presa. Il popup della presa torna allo switch. In NM Control la ricerca comprende tutte le planimetrie del progetto; nella pagina HA pubblicata mostra le prese della singola planimetria. Aggiorna esplicitamente la pagina HA dopo modifiche ai riferimenti.

L'utente finale può usare NM Control, una dashboard HA nativa o entrambe: condividono le entità. Le programmazioni NM continuano nell'add-on e non diventano automaticamente automazioni native HA. La vista utente NM semplifica la grafica, non è un confine di autorizzazione: i permessi vanno gestiti in HA.
