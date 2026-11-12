# Standard NM ETS v1

Usa `Stanza - Codice Nome funzione - Ruolo` per i singoli circuiti.
Esempio: `Esposizione - L02 Faretti - Luminosità Comando`.

La convenzione è facoltativa. NM Control continua a riconoscere le diciture ETS già supportate e a usare i DPT e gli oggetti collegati. Puoi combinare le convenzioni nello stesso progetto e completare le associazioni manualmente nei widget.

1. Usa il nome della stanza presente in **Edificio ETS**. Se hai stanze omonime, aggiungi il piano nel primo campo oppure collega i GA alla funzione della stanza in ETS.
2. Scegli un codice stabile per ogni circuito, ad esempio `L01` per una luce, `T01` per una serranda o `Z01` per una zona clima. Ripeti lo stesso prefisso in tutti i GA della funzione.
3. Scegli il ruolo dalla tabella e imposta il DPT nell'apposito campo di ETS. Collega il GA all'oggetto di comunicazione corrispondente. Ogni ruolo deve avere un solo GA per circuito.

| Funzione | Ruolo da scrivere dopo l'ultimo trattino | DPT |
| --- | --- | --- |
| Luce e dimmer | `ON/OFF Comando` | `1.001` |
| Luce e dimmer | `ON/OFF Feedback` | `1.001` o `1.011`, secondo l'oggetto |
| Dimmer | `Luminosità Comando` | `5.001` |
| Dimmer | `Luminosità Feedback` | `5.001` |
| Dimmer | `Dimmer relativo` | `3.007` |
| Serranda | `Movimento Comando` | `1.008` |
| Serranda | `STOP` | `1.017` per stop dedicato o `1.007` per step/stop, secondo l'oggetto |
| Serranda | `Posizione Comando` | `5.001` |
| Serranda | `Posizione Feedback` | `5.001` |
| Clima | `Temperatura ambiente` | `9.001` |
| Clima | `Setpoint Comando` | `9.001` |
| Clima | `Setpoint Feedback` | `9.001` |

Per il dimmer indica ON/OFF e almeno una modalità di regolazione. Per la serranda usa movimento e STOP, poi aggiungi i ruoli posizione disponibili. Per la proposta clima servono i tre ruoli elencati. In anteprima controlla la direzione dei comandi e la stanza prima di procedere con la configurazione.

Per i comandi collettivi già riconosciuti mantieni le diciture esplicite, ad esempio `OFF GENERALE` per il solo spegnimento e `TAPPARELLE TUTTE SU/GIU` per il movimento collettivo. Un feedback emesso da più attuatori va verificato prima di usarlo come stato di gruppo.

Su un progetto esistente puoi applicare la convenzione un circuito alla volta. Per rinominare una funzione mantieni numeri dei GA, DPT e collegamenti già corretti. Riapri l'esportazione in NM Control e confronta l'anteprima con ETS.
