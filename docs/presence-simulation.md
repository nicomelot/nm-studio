# Presenza simulata

In **NM Control → Programmazioni → Presenza simulata**, scegliere le luci del progetto, la finestra oraria e le durate minime/massime di accensione e pausa. L’anteprima e la conferma abilitano l’esecuzione dal prossimo controllo (circa 10 secondi), se le condizioni sono valide. Funziona con pagina chiusa, Home Assistant e add-on accesi.

- **Manuale:** lavora nella finestra scelta finché non viene fermata.
- **Automatico con antifurto:** lavora nella finestra scelta solo se l’entità `alarm_control_panel` selezionata è `armed_away`. `armed_home`, disinserito, allarme non disponibile o altri stati interrompono le nuove accensioni e rilasciano la luce gestita. Non invia mai comandi all’antifurto.
- **Ferma presenza simulata:** disabilita entrambe le modalità e richiede il rilascio della luce gestita. Per riabilitarla usare una nuova anteprima e conferma.

La simulazione accende una sola luce inizialmente spenta alla volta, con durate e pause estratte casualmente entro i limiti scelti. Quando possibile alterna i destinatari. Non modifica le luci già accese. Spegne al termine soltanto la luce di cui riconosce ancora lo stato inviato; una variazione manuale riconosciuta fa rinunciare al ripristino. Con stato incerto non effettua un ripristino alla cieca. L’uscita per dispositivo offline resta in attesa del collegamento; controllare il messaggio prima di considerare completato l’arresto.

Lo stato di gestione viene conservato per i riavvii: prima di riprendere, l’add-on rilascia un’eventuale luce ancora gestita. Non recupera accensioni saltate. Le settimane e le ferie non sono riscritte; per evitare comandi in conflitto, le luci con programmi attivi devono prima essere messe in pausa. Se un programma viene attivato successivamente, la simulazione si sospende. Modificare il progetto richiede una nuova verifica della configurazione presenza.

## Collaudo senza impianto

**Crea ingresso antifurto simulato** prepara un `input_boolean.nm_presence_sim_…`. Il suo stato acceso equivale a fuori casa, spento equivale al rientro. Scegliere esclusivamente luci SIM. È un ingresso di test, non un’integrazione con un antifurto reale. Al termine spegnere l’ingresso e fermare la simulazione.

Questa prima versione è una simulazione basata su intervalli variabili; non registra né riproduce le abitudini degli occupanti. La finestra può attraversare mezzanotte. Luci, orari e durate richiedono selezione esplicita.
