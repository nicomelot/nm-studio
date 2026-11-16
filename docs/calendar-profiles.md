# Programma di oggi, ferie e festivi

Nei popup NM per luci, tapparelle e termostati, **Oggi** mostra le fasce salvate e la prossima azione prevista. Gli orari sono calcolati dal programmatore NM Control usando fuso e posizione di Home Assistant, anche per alba e tramonto. In pausa vengono mostrate come previsioni non attive. Se il programmatore non aggiorna il riepilogo per 90 secondi, il popup segnala che l'esecuzione non è verificabile.

## Impostare un'eccezione

1. Aprire il dispositivo nella dashboard HA e premere **Ferie e festivi**.
2. Scegliere **Ferie** (inizio e fine inclusi) oppure **Festivi** (fino a 10 date esplicite, nel formato AAAA-MM-GG, separate da virgola). Le festività nazionali non vengono inserite automaticamente.
3. Aggiungere fino a 8 fasce: temperature per il clima, azioni e percentuali supportate per luci/tapparelle. Alba/tramonto mantengono lo scostamento massimo di 180 minuti.
4. **Salva profilo disabilitato**, poi **Verifica e abilita profilo** e confermare. La settimana principale deve essere attiva perché vengano eseguiti comandi; abilitare un profilo non riattiva un programma in pausa.

Ordine di precedenza: **Ferie → Festivi → Settimana abituale**. Il profilo sostituisce l'intera giornata, non si somma alla settimana. Un profilo attivo vuoto non esegue comandi in quelle date. Alla fine dell'intervallo o disabilitando il profilo tornano applicabili gli altri profili e la settimana.

La settimana resta nei suoi sette helper, senza essere riscritta dal salvataggio dei profili. Le fasce clima modificano il setpoint: non accendono un termostato spento. I giorni delle azioni solari si riferiscono alla data dell'evento, prima dello scostamento, come per la settimana.

## Aggiornamento delle card esistenti

All'avvio, la versione 5.38 prepara gli helper dei profili e aggiorna le risorse delle card già pubblicate. Non modifica né attiva le settimane salvate e non riscrive le dashboard. Dopo l'aggiornamento ricaricare la dashboard. Gli helper ausiliari `NM index`, `NM today`, `NM next` servono per collegare le card esistenti: non rinominarli manualmente.

L'anteprima considera i successivi 31 giorni; oltre questo intervallo viene indicata l'assenza di fasce nella finestra esaminata. Un salvataggio incompleto di un profilo attivo sospende il programma invece di eseguire una settimana diversa da quella attesa. Le modifiche ai profili non recuperano comandi già trascorsi.

## Verifica

Test automatici: priorità ferie/festivi, ritorno alla settimana, profilo vuoto, pausa globale, scrittura incompleta, modifiche concorrenti durante conferma, assenza di recuperi retroattivi, data non valida, cambio ora e corrispondenza fra anteprima solare ed esecuzione.

Simulatore locale: `tests/calendar_preview.html`, con termostato e tapparella; i servizi scrivono soltanto helper in memoria. Il collaudo HA usa i dispositivi NM LAB e al termine lascia il programma in pausa.

## Ferie su più dispositivi (5.39)

Dal popup scegliere **Ferie su più dispositivi**, impostare le date comuni e selezionare i dispositivi dello stesso progetto. La ricerca non cancella le selezioni. Sono elencate le card predisposte da NM Control anche se non presenti nella pagina corrente; dispositivi indisponibili non selezionabili.

Aggiungere fino a 8 fasce distinte per luci, tapparelle e termostati. Ogni dispositivo selezionato riceve le fasce del proprio tipo. Nessuna fascia significa nessun comando durante le ferie. Orari solari disponibili per luci e tapparelle; capacità e limiti temperatura vengono verificati per ogni destinatario.

Scegliere salvataggio disabilitato oppure salvataggio e abilitazione, leggere **Anteprima ferie di gruppo** e confermare. I profili ferie precedenti selezionati vengono sostituiti. Le sette giornate, i festivi e l’attivazione del programma principale rimangono invariati: un programma in pausa non viene riattivato. Alla fine delle ferie torna applicabile la settimana (o un festivo abilitato).

Il salvataggio è sequenziale, non una transazione HA: prima vengono salvati tutti i profili disabilitati, poi eventualmente abilitati. Un errore interrompe il gruppo e indica quanti profili sono stati salvati e quali abilitati. Non ripetere alla cieca: controllare gli esiti indicati e rifare l’anteprima. Nessun comando fisico immediato viene inviato dal pulsante.
