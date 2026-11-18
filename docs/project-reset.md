# Azzeramento del progetto NM

In NM Control, modalità installatore, usare **Azzera progetto NM**. Occorre un accesso amministratore Home Assistant tramite Ingress.

1. Leggere l’anteprima degli archivi, aiutanti e pagine interessati. Le vecchie pagine NM senza identificativo certo richiedono una selezione esplicita e una nuova anteprima.
2. Creare il backup: viene verificato e conservato in `/data/nm_reset_backups`.
3. Scaricare lo ZIP, spuntare la conferma e digitare la frase specifica del progetto.
4. Confermare l’azzeramento. Se i dati sono cambiati dopo l’anteprima, ripetere anteprima e backup.

Il reset elimina i dati attribuiti al progetto attivo: importazione, associazioni, configurazioni NM, scenari e programmi, planimetrie e sinottici, aiutanti per settimane/ferie/preferiti, storico operativo e pagine NM individuate nell’anteprima. Nelle pagine condivise rimuove soltanto gli elementi NM attribuiti al progetto. Il package dei simulati viene eliminato solo quando ne è verificata la proprietà esclusiva; per scaricarne le entità occorre poi riavviare manualmente Home Assistant.

Restano integrazioni, dispositivi fisici, aree HA, risorse frontend condivise e backup precedenti. Le vecchie entità KNX prive di un registro di provenienza non vengono cancellate automaticamente. Configurazioni globali non separabili tra più progetti bloccano il reset: l’anteprima ne indica il motivo. Non vengono inviati comandi ai dispositivi.

In caso di errore, il registro di avanzamento rimane su disco e sospende programmi e modifiche NM. Riaprire il pulsante, scaricare il backup e confermare **Riprendi azzeramento**. Ogni operazione viene riconciliata con lo stato effettivo, comprese quelle già completate. Eventuali modifiche concorrenti richiedono verifica prima di continuare.

Il backup NM è destinato al ripristino assistito e non sostituisce il backup completo di Home Assistant. Lo ZIP contiene un manifesto con i file precedenti, configurazioni delle pagine e degli aiutanti e, se presente, il database operativo. Per ripristinare occorre fermare NM, ricostruire i file e le risorse HA dal manifesto e verificarne i collegamenti; non è previsto un pulsante di ripristino automatico. Conservare lo ZIP come configurazione riservata dell’impianto.

Il collaudo automatico usa directory temporanee e un simulatore delle API HA: verifica anteprima, autorizzazioni, download, conferma, conservazione delle risorse esterne, dati cambiati, errore e ripresa. Non richiede né modifica Rezzato.
