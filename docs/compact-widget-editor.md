# Configurazione compatta delle funzioni KNX

Disponibile in NM Control LAB 5.21.0-beta.5.

Ogni funzione è una riga con nome, stanza, indirizzo principale e avviso di
configurazione incompleta. Aprire la riga per modificare i campi; la sezione
«Verifica indirizzi KNX e anteprima» contiene l’anteprima ridotta e gli indirizzi.

- Trascinare la maniglia ↕ sopra o sotto un’altra funzione per riordinare.
- Per cambiare stanza, scegliere la destinazione e trascinare su «Sposta qui».
  In alternativa, selezionare la maniglia e premere «Sposta qui».
- Con la maniglia selezionata, Alt + freccia su/giù riordina le righe visibili.
- Escape annulla un trascinamento; «Annulla spostamento» ripristina l’ultimo
  ordine e assegnazione, conservando eventuali modifiche successive al nome.
- «Salva bozza» conserva ordine e assegnazioni. Spostare una funzione non crea
  entità Home Assistant e non invia comandi al bus.

Il riordino riguarda le funzioni, non la gerarchia di edifici/piani/stanze.
Le viste generate continuano a raggruppare le funzioni secondo le proprie sezioni.

## Verifica

Test automatici: `node --test tests/*.test.js`. I test di posizionamento verificano
riordino, assegnazione, annullamento, conservazione di GA/profili/entità e rifiuto
di annullamenti su una configurazione sostituita o con funzioni aggiunte/rimosse.

Il collaudo visivo e dei gesti in browser è ancora da completare. Nessun
collaudo su Home Assistant o dispositivi reali eseguito per questa modifica.
Nel canale LAB verificare trascinamento mouse e touch, annullamento, ricerca,
aggiunta manuale, salvataggio e riapertura, e layout a 390 px e 1280 px.
