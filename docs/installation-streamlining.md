# Creazione multipla delle funzioni KNX

La pagina di creazione carica automaticamente le funzioni salvate e mostra un
riepilogo selezionabile. Una conferma avvia la creazione sequenziale delle funzioni
pronte. Ogni risposta positiva di Home Assistant viene subito associata e salvata
nel widget originale. Il collaudo di una singola funzione rimane negli strumenti
avanzati della stessa pagina.

Salva e continua porta direttamente alla creazione; le associazioni con entità già
esistenti restano disponibili come percorso alternativo. Le stanze possono essere
rifinite dopo il primo collaudo. Le funzioni incomplete rimangono visibili con la
ragione per cui non sono selezionabili.

Il processo non invia comandi di accensione o movimento. La creazione tramite HA
può provocare letture di stato KNX. Ogni passo verifica il progetto salvato, la
configurazione approvata, i duplicati GA e lo schema ufficiale KNX. Un errore ferma
la sequenza; le associazioni già salvate restano disponibili. Una risposta persa
richiede il controllo dell'entità esistente prima di ripetere la creazione.

## Riconoscimento e limiti della verifica

I circuiti con ruoli e DPT coerenti possono essere riconosciuti senza feedback
facoltativi. Un dimmer con sola regolazione relativa rimane un dimmer e richiede
il completamento della luminosità assoluta prima della creazione. Movimento e
arresto con DPT coerenti riconoscono tapparelle anche senza sigle T1/T2 nei nomi.
Ruoli ambigui non vengono risolti usando la vicinanza numerica degli indirizzi.

Queste modifiche sono coperte da progetti sintetici e prove senza bus. La verifica
del progetto cliente protetto è ancora aperta: il trasferimento dell'allegato non
è riuscito. Non sono disponibili risultati di riconoscimento su quel file e non
è stato eseguito un collaudo fisico. Nessun progetto cliente o password è incluso
nel repository.
