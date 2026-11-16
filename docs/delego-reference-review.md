# Spunti Delego per NM Studio

Analisi del 16 novembre 2026 dei 16 manuali V2.8.0 forniti in `C:\3klife\NM STUDIO\delego manuali`. Esaminati gli indici dell'intera raccolta, approfondite le sezioni pertinenti al progetto e verificate visivamente quattro pagine di riferimento. Questa è una revisione funzionale, non una certificazione delle integrazioni descritte dai manuali.

Le proposte sotto non sono funzioni già implementate. La documentazione descrive Delego: non dimostra la compatibilità di un dispositivo con Home Assistant o NM Studio.

## Priorità per il nostro flusso

1. **Importazione ETS con sole eccezioni da correggere.** Proporre automaticamente ambiente, funzione, comando e feedback; mostrare regola usata, dati di partenza e motivazione. Le ambiguità restano esplicite. Riepilogo di nuovi elementi, aggiornamenti, elementi conservati e riferimenti mancanti prima di applicare. Una nuova importazione non deve cancellare le personalizzazioni.
2. **Programmazione immediatamente leggibile.** Nel popup mostrare la linea delle azioni di oggi e la prossima azione con orario effettivo, compreso lo scostamento da alba/tramonto. La pagina settimanale e il popup devono leggere lo stesso programma. Esplicitare programma sospeso, comando manuale e stato non disponibile.
3. **Ferie ed eccezioni per data.** Aggiungere profili riutilizzabili feriale/festivo/vacanze, con precedenza dichiarata rispetto alla settimana. Consentire sospensione senza cancellazione. Il termostato oggi comunica che il comando manuale vale fino alla prossima fascia; una sospensione fino a un'ora/data richiede un'estensione distinta del motore, non soltanto un pulsante.
4. **Collaudo guidato prima della consegna.** Una traccia spiega evento, condizioni, azione prevista ed esito. Nel simulatore cambiare sensori/orologio senza trasmettere comandi reali. Il Decision Model può presentare motivazioni e conflitti; l'attivazione resta distinta dall'anteprima.
5. **Sinottico energetico.** Modello rete, fotovoltaico, batteria, casa, pompa di calore e wallbox. Associare le misure per funzione e unità; distinguere potenza istantanea, energia e carica. Iniziare dalla visualizzazione, poi introdurre controllo carichi con priorità, soglie separate, ritardi e stato manuale/automatico.

## Come adattarlo senza allungare la configurazione

Percorso proposto: **Importa ETS → controlla i casi dubbi → associa HA → anteprima Panoramica → pubblica**. Ambienti, nomi e capacità già disponibili vengono riutilizzati. Indirizzi, codifiche, soglie e personalizzazioni rimangono nei dettagli avanzati.

NM Control resta lo strumento dell'installatore; l'utente usa le card di Home Assistant. La generazione deve poter conservare le modifiche fatte dall'editor HA. Il generatore 5.37 usa un confronto conservativo per vista: una vista personalizzata viene mantenuta intera, quindi non riceve automaticamente le nuove selezioni.

Per la visibilità distinguere tre condizioni:

- **Funzione non configurata:** nessun pulsante corrispondente.
- **Entità configurata ma temporaneamente indisponibile:** elemento riconoscibile, stato spiegato e comandi disabilitati; non farlo sparire.
- **Punto puramente documentale:** scheda tecnica apribile, nessun comando fittizio.

La pressione lunga non deve essere l'unico modo per scoprire la programmazione: mantenere un pulsante visibile e coerente su PC e telefono. Preferire ricerca, selezione multipla e modelli riutilizzabili a operazioni ripetute di trascinamento.

## Raccolta esaminata e riferimenti

I numeri sono le pagine PDF; in alcuni manuali indice e numerazione interna non coincidono perfettamente. Tutti i nomi sotto si riferiscono ai PDF originali della cartella fornita.

| Manuale | Sezioni esaminate | Spunto per NM Studio |
|---|---|---|
| `1.1_MAEKDELSRV_DOCPLAN_IT_V2.8.0.pdf` | Indice della documentazione | Separare guida installatore, guida utente e riferimenti delle integrazioni. |
| `2.1_MAEKDELSRV_GENERAL_IT_V2.8.0.pdf` | Indice; pianificazioni pp. 51–56; simulazione presenza p. 80; popup p. 53 anche visivamente | Anteprima giornaliera, profili per più giorni, eccezioni per data e sospensione dei profili. |
| `2.3_MAEKDELSRV_AUTOMATIONS_IT_V2.8.0.pdf` | Indice; simulazione pp. 15–16; libreria p. 17 | Simulazione continua o per passi con messaggi di esecuzione. Riprenderne la diagnostica, non duplicare necessariamente l'editor logico. |
| `2.4_MAEKDELSRV_LUA_SCRIPTING_EN_V2.8.0.pdf` | Indice; debugging p. 19; modelli p. 20 | Modelli con ingressi/uscite nominati, riutilizzabili fra progetti; log leggibili. Non serve introdurre Lua per ottenere questo risultato. |
| `3.1_MAEKDELSRV_KNX_IT_V2.8.0.pdf` | Regole/importazione pp. 19–21; tabella indirizzi p. 26 anche visivamente; duplicazione p. 28 | Regole per nomi/offset, report finale, correzione dei soli non riconosciuti; separazione comando/feedback; copia con controllo indirizzi. |
| `3.2_MAEKDELSRV_MODBUS_IT_V2.8.0.pdf` | Indice; registri pp. 11–12 | Modelli che dichiarano lettura/scrittura, tipo e unità. Evitare che il solo nome di un registro determini un comando. |
| `3.4_MAEKDELSRV_MQTT_IT_V2.8.0.pdf` | Indice; connessione e associazione pp. 10–11 | Diagnostica distinta fra collegamento, comando e ritorno di stato. Usare le entità già integrate in HA quando disponibili. |
| `3.5_MAEKDELSRV_MATTER_IT_V2.8.0.pdf` | Indice; widget p. 11; bridge p. 17 | Catalogo delle capacità effettive e stato di sincronizzazione. Importare da HA non equivale a implementare un bridge Matter. |
| `4.1_MAEKDELSRV_ENERGY_DATALOG_IT_V2.8.0.pdf` | Indice; misure/categorie pp. 12–13, p. 13 anche visivamente; controllo carichi pp. 16, 19 | Sinottico energia per ruolo dei contatori; sgancio e ripristino con soglie e attese differenti. |
| `4.2_MAEKDELSRV_ACCEDO_IT_V2.8.0.pdf` | Indice; presenza virtuale pp. 65–66 | Modelli di occupazione stanza con segnali e timeout espliciti. Modulo per ricettivo da tenere separato dal percorso residenziale. |
| `5.1_MAEKDELSRV_INTRUSION_PROTECTION_IT_V2.8.0.pdf` | Indice; funzioni/stati e visualizzazione pp. 7–8 | Distinguere stato centrale, aree, sensori e registro eventi; sezioni separate su telefono. Compatibilità da verificare per ogni centrale. |
| `5.2_MAEKDELSRV_IPCAMERA_IT_V2.8.0.pdf` | Indice; configurazione p. 7; visualizzazione p. 11 | Popup della telecamera associata all'ambiente; verificare separatamente riproduzione su browser e telefono. |
| `5.3_MAEKDELSRV_VOIP_INTERCOM_IT_V2.8.0.pdf` | Indice; gruppi di chiamata p. 19 | Associazione chiara tra ingresso e destinatari. Citofonia/audio bidirezionale richiedono una verifica dedicata, non basta una card video. |
| `5.4_MAEKDELSRV_COOLMASTER_IT_V2.8.0.pdf` | Indice; modelli p. 13; visualizzazione pp. 15–16, p. 16 anche visivamente | Un popup clima compatto che raggruppa modalità, temperatura, ventilazione e programma. Capacità derivate dal dispositivo collegato. |
| `5.5_MAEKDELSRV_PHILIPS_HUE_IT_V2.8.0.pdf` | Indice; discovery p. 7 | Distinguere luce dimmerabile, colore e temperatura del bianco; assegnazione all'ambiente subito dopo l'importazione. |
| `5.6_MAEKDELSRV_PMS_CHANNEL_MGR_IT_V2.8.0.pdf` | Indice; operazioni PMS p. 6; mappatura server p. 13 | Futuro modulo ricettivo: camere e periodi di validità espliciti. Non assumere che il supporto Delego sia disponibile in NM. |

## Cosa verificare nei prossimi incrementi

- Importare due volte un progetto ETS modificato: nessun duplicato o perdita silenziosa di associazioni.
- Una funzione non supportata non compare; una funzione offline rimane distinguibile da una non configurata.
- Programma di oggi coerente con settimana, eccezioni e prossima esecuzione; verifica del cambio data e dell'ora legale.
- Un comando manuale mostra quando il programma riprenderà.
- Simulazione e anteprima non devono attivare dispositivi fisici.
- Sinottico energetico con unità e segni coerenti; nessun intervento automatico sui carichi durante il solo collaudo grafico.

Prima scelta consigliata: completare e collaudare il generatore Panoramica già in sviluppo; quindi anteprima del programma di oggi ed eccezioni. Energia e moduli ricettivi sono incrementi separati.
