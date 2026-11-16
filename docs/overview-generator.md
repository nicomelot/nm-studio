# Generare la Panoramica Home Assistant

Percorso consigliato: importa ETS, controlla le funzioni proposte, salva le associazioni HA, premi **Genera Panoramica Home Assistant**. Lo stesso comando è nella Panoramica di NM Control.

Il generatore legge le entità effettivamente presenti in HA, raggruppa i dispositivi negli ambienti salvati e propone quelli disponibili. La ricerca e la selezione per ambiente permettono di ridurre la selezione. Dispositivi temporaneamente indisponibili possono essere scelti esplicitamente; quelli assenti e i pulsanti momentanei non vengono pubblicati come comandi standard.

Planimetrie e sinottici sono facoltativi. Solo gli schemi salvati e pronti si possono scegliere. I loro collegamenti vengono creati insieme alle viste, mai come segnaposto. I punti tecnici senza entità rimangono documentazione, senza comandi. Sonde e altri dispositivi compatibili usano card HA standard; luci, tapparelle e clima usano i popup NM con le settimane esistenti.

L'anteprima indica viste risultanti, riferimenti mancanti, viste conservate e rimozioni. Non scrive configurazioni. Confermare crea o aggiorna la pagina senza inviare comandi né attivare programmi.

## Aggiornare senza perdere personalizzazioni

Il confronto è per vista: una vista ancora identica a quella generata può essere aggiornata. Una vista modificata, riorganizzata o eliminata dall'editor HA prevale sempre e viene segnalata nell'anteprima. Le nuove selezioni per una vista personalizzata non si applicano automaticamente: aggiungere le card manualmente o scegliere una nuova Panoramica. Le altre viste rimangono intatte. Prima di scrivere vengono salvati backup in `/data/nm_overview_backups`; un cambiamento concorrente annulla l'applicazione e richiede una nuova anteprima.

La pagina iniziale si sceglie da HA → Impostazioni → Plance → menu della pagina → Imposta come predefinito. Questo passaggio resta esplicito. Le dashboard esistenti non vengono sostituite implicitamente.

## Revisione del percorso ETS

- Riutilizzo del progetto salvato e dei nomi/ambienti ETS, senza reinserimento.
- Importazione delle funzioni riconosciute già automatica; casi ambigui rimangono da verificare.
- Associazioni reali e installazione KNX mantengono la verifica dell'installatore: un nome simile non prova che comando e feedback siano corretti.
- Dopo il salvataggio delle associazioni, il pulsante Continua apre il nuovo generatore.
- Avvio guidato mostra tre passaggi; connessione KNX, diagnostica, personalizzazione e pubblicazione precedente sono espandibili.
- L'automazione del percorso non invia comandi fisici e non cambia l'impianto durante la generazione grafica.
