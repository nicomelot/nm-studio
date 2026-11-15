# NM Studio – Home Assistant

## Luci e tapparelle nella dashboard esistente (5.35)

In **Dispositivi → Card nella dashboard HA**, seleziona una plancia e i dispositivi del progetto. L’anteprima elenca le aggiunte; **Conferma inserimento** aggiunge la vista **NM · Dispositivi**, conservando le altre viste e salvando una copia della configurazione precedente. Una seconda esecuzione non duplica le card già inserite. Le card si possono poi spostare nell’editor HA. La nuova Panoramica automatica di HA (/home) non ammette viste aggiuntive: scegli una normale plancia HA personalizzabile, che può contenere insieme card standard e card NM. La Panoramica classica (/lovelace), se ancora presente, deve essere già modificabile. NM non converte automaticamente le dashboard.

Clicca la card per aprire i comandi e **Programmazione settimanale**. Ogni fascia sceglie Orario, Alba o Tramonto, l’eventuale anticipo/ritardo in minuti e l’azione. Luminosità e posizione compaiono solo se supportate e associate. Copia il giorno sugli altri, salva in pausa e conferma l’attivazione. La posizione geografica e il fuso sono quelli di HA; i giorni delle fasce solari si riferiscono al giorno dell’alba/tramonto, anche quando uno scostamento attraversa mezzanotte. Programmi NM già attivi sul dispositivo hanno precedenza; l’avviso compare nella card. Il programma continua a browser chiuso, con HA e add-on accesi.

## Termostati e sinottici nelle plance Home Assistant (5.34)

In NM Control → Dispositivi → **Card HA termostato**, scegliere il termostato del progetto e creare la pagina. Per i termostati NM LAB, l’opzione simulazione aggiunge gli ingressi filtro, palette e ventola automatica. Anche le nuove plance autogenerate utilizzano la card NM Termostato. Le plance già esistenti richiedono il normale aggiornamento con confronto e conferma.

Il popup mostra solo modalità e preset esposti dal dispositivo. In modifica card di HA si possono associare allarme filtro, reset manutenzione, posizione palette e ventola automatica. La programmazione cambia il setpoint, non la modalità: un termostato spento resta spento. I comandi manuali valgono fino alla prossima fascia.

**Programmazione → aggiungi fasce → copia sugli altri giorni → Salva settimana in pausa → Verifica e attiva → Confermo.** Massimo otto fasce al giorno. Home Assistant conserva sette helper giornalieri e un indicatore di versione; NM esegue solo una settimana completamente salvata. Non modificare questi helper manualmente. Un programma NM già attivo sul medesimo termostato sospende l’esecuzione della settimana HA, con avviso. Add-on e Home Assistant devono restare accesi; le fasce passate non vengono recuperate all’attivazione. L’esito riporta l’orario dell’ultimo aggiornamento, non certifica una connessione continua.

In **Sinottici**, salvare lo schema e scegliere **Crea pagina HA**. Vengono pubblicati sfondo, simboli, collegamenti ai dispositivi e tubazioni, anche per schemi senza immagine. L’aggiornamento di una pagina esistente richiede confronto e conserva una copia precedente. L’utente finale usa la pagina HA; l’installatore modifica il disegno in NM Control e ripubblica.

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
