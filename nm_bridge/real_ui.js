let pilotBusy=false;
function bulkInstallPage(){return `<section class="card" id="bulk-install"><div class="workspace-label">Impianto reale</div><h2>Controlla e applica le funzioni</h2><p>Riepilogo per stanza: crea le funzioni mancanti e completa le entità KNX esistenti con una sola conferma. Gli indirizzi discordanti restano da verificare.</p><div class="bar"><button id="install-load">Aggiorna elenco</button><button id="install-edit">Correggi funzioni e stanze</button></div><p id="install-status" role="status"></p><div id="install-list"></div><label class="row"><input type="checkbox" id="install-verified" style="width:auto"> Ho verificato indirizzi e tipi in ETS e il backup HA</label><div class="bar" style="position:sticky;bottom:0;background:var(--panel,#10203b);padding:12px;z-index:2"><button id="install-create" class="primary" disabled>Crea selezionate</button><button id="install-areas">Sincronizza stanze in Home Assistant</button><button id="install-next" hidden>Continua alla dashboard</button></div><pre id="install-results" style="white-space:pre-wrap" aria-live="polite"></pre></section>`;}

function installBlocker(device){
 if(!['light','dimmer','cover'].includes(device.type))return 'Tipo da configurare negli strumenti avanzati';
 if(!device.fields.command)return 'Manca il comando';
 if(device.type==='dimmer'&&!device.fields.brightness)return 'Manca il comando luminosità assoluta';
 if(device.type==='cover'&&!device.fields.stop)return 'Manca il comando arresto';
 return '';
}

function syncCreatedAssociation(project,device,entityId){
 if(typeof savedWidgetLayout!=='undefined'&&savedWidgetLayout.project===project){
  const matches=savedWidgetLayout.widgets.filter(w=>w.type===device.type&&w.fields.command===device.fields.command);
  if(matches.length===1)matches[0].entity_id=entityId;
 }
 if(etsData?.project_key===project&&typeof widgetDrafts!=='undefined'){
  const matches=widgetDrafts.filter(w=>w.kind===device.type&&w.fields.command===device.fields.command);
  if(matches.length===1)matches[0].entity_id=entityId;
 }
 if(typeof nmDashboardDraft!=='undefined')nmDashboardDraft=null;
}

function wireBulkInstall(){
 let source=null,capability=null,busy=false,rows=[];
 const status=message=>$('install-status').textContent=message;
 const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const selected=()=>rows.filter(r=>r.checked&&r.dataset.blocked!=='true').map(r=>source.devices.find(d=>d.index===Number(r.dataset.installIndex)));
 function gate(){const n=source?selected().length:0;$('install-create').textContent=`Applica ${n} modifiche`;$('install-create').disabled=busy||!n||!$('install-verified').checked||!capability?.available||!capability?.connected;}
 async function run(work){if(busy||pilotBusy)return;busy=true;pilotBusy=true;gate();document.querySelectorAll('#bulk-install input,#bulk-install button').forEach(el=>el.disabled=true);try{await work();}catch(e){status('Interrotto: '+e.message+' Le operazioni già confermate restano salvate. Aggiorna elenco prima di riprovare.');source=null;}finally{busy=false;pilotBusy=false;document.querySelectorAll('#bulk-install button').forEach(el=>el.disabled=false);$('install-verified').disabled=false;rows.forEach(r=>r.disabled=!source||r.dataset.blocked==='true');gate();}}
 if($('install-areas'))$('install-areas').onclick=()=>run(async()=>{
  if(widgetDirty||structureDirty)throw Error('Salva prima funzioni e stanze.');
  const current=await api('dashboard/missing-ha');
  if(etsData?.project_key&&current.project!==etsData.project_key)throw Error('Salva prima il progetto aperto.');
  if(!confirm('Sincronizzare stanze e piani in HA conservando le assegnazioni esistenti?'))return;
  const result=await post('native/areas-sync',{confirm:true,source_fingerprint:current.source_fingerprint});
  status(`${result.rooms} stanze HA, ${result.assigned} nuove assegnazioni. ${result.notices.join(' · ')}`);
 });
 $('install-edit').onclick=()=>{if(!busy)setPage('widgets');};
 $('install-next').onclick=()=>{if(!busy)setPage('dashboard-export');};
 $('install-verified').onchange=gate;
 $('install-load').onclick=()=>run(async()=>{
  source=null;rows=[];$('install-list').innerHTML='';$('install-verified').checked=false;status('Confronto con la configurazione KNX di Home Assistant.');
  const [data,access]=await Promise.all([api('knx/installation-review'),api('knx/panel-capability')]);
  if(etsData?.project_key&&data.project!==etsData.project_key)throw Error('Salva prima le funzioni del progetto aperto.');
  source=data;capability=access;
  const groups=new Map();for(const d of data.devices){const room=d.room||'Da assegnare';if(!groups.has(room))groups.set(room,[]);groups.get(room).push(d);}
  const labels={create:'Pronta da creare',update:'Da aggiornare',present:'Già presente',review:'Da verificare'};
  $('install-list').innerHTML=[...groups].map(([room,devices])=>`<section><h3>${escapeHTML(room)}</h3>${devices.map(d=>{
   const reason=installBlocker(d)||(!access.supported_platforms?.includes(d.type==='cover'?'cover':'light')?'Piattaforma non disponibile':'');
   const blocked=!!reason||!['create','update'].includes(d.status);
   return `<label class="card row"><input type="checkbox" data-install-index="${d.index}" data-blocked="${blocked}" style="width:auto" ${blocked?'disabled':'checked'}><span><strong>${escapeHTML(d.name)}</strong> · ${escapeHTML(labels[d.status]||'Da verificare')}<br>${escapeHTML(reason||d.reason)}${d.entity_id?'<br>'+escapeHTML(d.entity_id):''}</span></label>`;
  }).join('')}</section>`).join('');
  rows=[...document.querySelectorAll('[data-install-index]')];rows.forEach(r=>r.onchange=gate);
  status(Object.entries(labels).map(([key,label])=>`${data.devices.filter(d=>d.status===key).length} ${label.toLowerCase()}`).join(' · '));
  $('install-next').hidden=false;
 });
 $('install-create').onclick=()=>run(async()=>{
  const devices=source?selected():[];
  if(!devices.length||!$('install-verified').checked||!capability?.connected)throw Error('Completa selezione e verifica.');
  if(typeof widgetDirty!=='undefined'&&(widgetDirty||structureDirty))throw Error('Salva prima le modifiche alle funzioni.');
  if(!confirm(`Applicare ${devices.length} modifiche?\n${devices.map(d=>(d.status==='update'?'Aggiorna: ':'Crea: ')+d.name).join('\n')}\nGli aggiornamenti mantengono ID e nomi HA. Possono avviare letture KNX.`))return;
  let fingerprint=source.source_fingerprint;
  for(let i=0;i<devices.length;i++){
   const d=devices[i];status(`Applicazione ${i+1}/${devices.length}: ${d.name}`);
   const done=await post('knx/installation-apply',{confirm:true,backup_confirmed:true,ets_confirmed:true,source_fingerprint:fingerprint,index:d.index,expected:d});
   $('install-results').textContent+=`${d.name}: ${done.entity_id} · ${done.updated?'aggiornata':'creata e associata'}\n`;
   if(!done.linked||done.stop)throw Error(done.message||'Verifica la funzione in HA.');
   syncCreatedAssociation(source.project,d,done.entity_id);fingerprint=done.source_fingerprint;
   const row=rows.find(r=>Number(r.dataset.installIndex)===d.index);row.checked=false;row.dataset.blocked='true';
  }
  source.source_fingerprint=fingerprint;$('install-verified').checked=false;$('install-next').hidden=false;
  status(`${devices.length} modifiche applicate. Aggiorna elenco per rileggere il risultato, poi apri la dashboard per il collaudo.`);
 });
 return $('install-load').onclick();
}
// Installer-led pilot. Preparation and status reads never send device commands.
function pilotPage(){
 return bulkInstallPage()+`<details class="card"><summary>Collaudo avanzato di una singola funzione</summary><section class="card" id="real-pilot"><div class="workspace-label">Impianto reale · primo collaudo</div><h2>Una funzione alla volta</h2><p>Parti da una luce, poi prova un dimmer e una tapparella. Usa i widget KNX salvati e verificati in ETS; le entità LAB non vengono convertite.</p><div class="installer-steps"><span>1 · Scegli</span><span>2 · Verifica GA</span><span>3 · Crea in HA</span><span>4 · Collauda</span></div><div class="bar"><button id="pilot-load" class="primary">Carica dispositivi e verifica accesso KNX</button><button data-pilot-go="widgets">Prepara / salva widget KNX</button></div><p id="pilot-status" aria-live="polite">Nessuna operazione avviata.</p><p id="pilot-access"></p><div id="pilot-selection" hidden><label>Dispositivo<select id="pilot-device"></select></label><div id="pilot-fields"></div><p class="small">I dati provengono dai widget salvati. Per correggerli usa “Prepara / salva widget KNX”, poi ricarica questa pagina.</p><button id="pilot-prepare" class="primary">Verifica e prepara questo dispositivo</button></div><div id="pilot-review" hidden><h3>Configurazione che verrà inviata</h3><pre id="pilot-plan" style="white-space:pre-wrap"></pre><p id="pilot-findings"></p><label class="row"><input id="pilot-backup" type="checkbox" style="width:auto"> Backup HA eseguito e verificato</label><label class="row"><input id="pilot-ets" type="checkbox" style="width:auto"> GA, DPT e direzione verificati in ETS; controllati i duplicati in HA</label><div class="bar"><button id="pilot-create" class="primary" disabled>Crea solo questa entità reale</button><button data-pilot-go="ha-preview">Apri preparazione YAML / strumenti avanzati</button></div><p>La creazione modifica la configurazione HA e può avviare letture sul bus. Nessun comando di accensione o movimento viene inviato dal configuratore.</p></div><div id="pilot-result" hidden><h3>Collaudo fisico</h3><p id="pilot-created"></p><button id="pilot-state">Leggi stato da Home Assistant</button><p id="pilot-observed" aria-live="polite"></p><ol><li>Aziona il comando locale e verifica che lo stato in HA segua il dispositivo.</li><li>Dal pannello KNX di HA prova il comando e verifica il risultato fisico.</li><li>Per il dimmer controlla accensione e luminosità. Per la tapparella controlla direzione e arresto.</li></ol><p>Uno stato disponibile non dimostra da solo che il comando o il feedback siano corretti. Il collaudo resta manuale.</p><div class="bar"><button data-pilot-go="matches">Associa l'entità al widget</button><button data-pilot-go="dashboard-export">Prepara la dashboard reale</button><button data-pilot-go="diagnostic">Apri diagnostica bus</button></div></div></section></details>`;
}
function wirePilot(){
 if($('install-load'))wireBulkInstall();
 const fieldLabels={command:'Comando / movimento · DPT 1',feedback:'Stato ON/OFF · DPT 1',brightness:'Luminosità assoluta · DPT 5.001',brightness_feedback:'Stato luminosità · DPT 5.001',stop:'Arresto · DPT 1'};
 const fieldsByType={light:['command','feedback'],dimmer:['command','feedback','brightness','brightness_feedback'],cover:['command','stop']};
 let source=null,capability=null,device=null,review=null,plan=null,created=null,busy=false;
 const status=text=>$('pilot-status').textContent=text;
 const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const gate=()=>{$('pilot-create').disabled=busy||!plan||!capability?.available||!capability.connected||!capability.supported_platforms?.includes(plan.calls[0].platform)||!$('pilot-backup').checked||!$('pilot-ets').checked;};
 function invalidate(){review=null;plan=null;$('pilot-review').hidden=true;$('pilot-backup').checked=false;$('pilot-ets').checked=false;gate();}
 async function run(work){if(busy||pilotBusy)return;busy=true;pilotBusy=true;document.querySelectorAll('#real-pilot input,#real-pilot select,#real-pilot button').forEach(el=>el.disabled=true);try{await work();}catch(e){invalidate();status('Operazione non completata: '+e.message);}finally{busy=false;pilotBusy=false;document.querySelectorAll('#real-pilot input,#real-pilot select,#real-pilot button').forEach(el=>el.disabled=false);gate();}}
 function select(){
  invalidate();device=source?.devices.find(d=>d.index===Number($('pilot-device').value));
  if(!device){$('pilot-selection').hidden=true;return;}
  $('pilot-fields').innerHTML=`<p>${escapeHTML(device.room)} · ${escapeHTML(device.type)}</p><label>Nome<input id="pilot-name" readonly maxlength="80" value="${escapeHTML(device.name)}"></label><div class="ha-review-fields">${fieldsByType[device.type].map(key=>`<label>${escapeHTML(fieldLabels[key])}<input readonly data-pilot-field="${key}" value="${escapeHTML(device.fields[key]||'')}" placeholder="Es. 1/1/0"></label>`).join('')}</div>${device.type==='cover'?'<p class="warning">Questo primo collaudo configura movimento e arresto. Posizione e feedback percentuale non sono inclusi: vanno distinti e verificati prima di abilitarli.</p>':''}`;
  $('pilot-name').oninput=invalidate;document.querySelectorAll('[data-pilot-field]').forEach(el=>el.oninput=invalidate);
 }
 $('pilot-backup').onchange=gate;$('pilot-ets').onchange=gate;
 $('pilot-device').onchange=select;
 document.querySelectorAll('[data-pilot-go]').forEach(el=>el.onclick=()=>{if(!busy)setPage(el.dataset.pilotGo);});
 $('pilot-load').onclick=()=>run(async()=>{
  invalidate();source=null;capability=null;$('pilot-selection').hidden=true;$('pilot-access').textContent='Verifica in sola lettura…';
  const results=await Promise.all([api('dashboard/missing-ha'),api('knx/panel-capability')]);
  source=results[0];capability=results[1];
  if(etsData?.project_key&&source.project!==etsData.project_key)throw Error('Il progetto ETS aperto non corrisponde ai widget salvati. Salva prima i widget del progetto corretto; nessuna creazione è consentita.');
  $('pilot-access').textContent=capability.message+(capability.available?(capability.connected?' Interfaccia connessa.':' Interfaccia non connessa: creazione disabilitata.'):' Puoi preparare il dispositivo; la creazione resta disabilitata.');
  const devices=source.devices.filter(d=>Object.hasOwn(fieldsByType,d.type));
  $('pilot-device').innerHTML=devices.map(d=>`<option value="${d.index}">${escapeHTML(d.name)} · ${escapeHTML(d.room)} · ${escapeHTML(d.type)}</option>`).join('');
  if(devices.length){$('pilot-device').value=String(devices[0].index);$('pilot-selection').hidden=false;select();}
  status(devices.length?`${devices.length} funzioni disponibili · progetto ${etsData?.session_label||source.project?.slice(0,12)||'salvato'}. Scegli un solo dispositivo da verificare.`:'Nessuna funzione disponibile: salva i widget KNX oppure verifica le associazioni esistenti. Il clima sarà gestito in un percorso dedicato.');
 });
 $('pilot-prepare').onclick=()=>run(async()=>{
  invalidate();if(!device||!source)throw Error('Carica prima i dispositivi.');
  const fields=Object.fromEntries([...document.querySelectorAll('[data-pilot-field]')].map(el=>[el.dataset.pilotField,el.value.trim()]));
  const request={source_fingerprint:source.source_fingerprint,devices:[{index:device.index,approved:true,name:$('pilot-name').value.trim(),fields}]};
  const checked=await post('dashboard/missing-ha/review',request);
  const prepared=await post('knx/panel-create-plan',request);
  const conflicts=await post('dashboard/deployment-preflight',request);
  if(conflicts.status==='blocked')throw Error(conflicts.findings.filter(f=>f.severity==='block').map(f=>f.message).join(' · '));
  review=request;plan=prepared;
  $('pilot-plan').textContent=JSON.stringify(plan.calls[0].data,null,2);
  const notes=[...(checked.warnings||[]).map(w=>w.message),...(conflicts.findings||[]).map(f=>f.message)];
  if(device.type!=='cover'&&!fields.feedback)notes.unshift('Feedback ON/OFF assente: non potrai verificare lo stato reale tramite questo GA.');
  if(device.type==='dimmer'&&!fields.brightness_feedback)notes.unshift('Feedback luminosità assente: il valore percentuale potrebbe non seguire il dispositivo.');
  $('pilot-findings').textContent=notes.join(' · ');$('pilot-review').hidden=false;
  status('Bozza pronta per un solo dispositivo. Verifica i dati e le conferme prima di creare.');
 });
 $('pilot-create').onclick=()=>run(async()=>{
  if(!plan||!review||!capability?.available||!capability.connected||!$('pilot-backup').checked||!$('pilot-ets').checked)throw Error('Completa accesso KNX, backup e verifica ETS.');
  const call=plan.calls[0];
  if(!confirm('Creare questa entità KNX reale in Home Assistant?\n\n'+JSON.stringify(call.data,null,2)+'\n\nLa creazione può avviare letture sul bus.'))return;
  const done=await post('knx/panel-create-one',{confirm:true,backup_confirmed:true,ets_confirmed:true,review,source_fingerprint:plan.source_fingerprint,call_index:0,expected_call:call});
  created=done.entity_id;invalidate();$('pilot-created').textContent='Entità creata: '+created;$('pilot-observed').textContent='Stato non ancora letto.';$('pilot-result').hidden=false;
  status('Creazione confermata da HA. Ora esegui il collaudo e associa l’entità al widget.');
 });
 $('pilot-state').onclick=()=>run(async()=>{
  if(!created)return;
  const data=await api('entities'),entity=data.entities.find(e=>e.entity_id===created);
  $('pilot-observed').textContent=entity?'Stato letto: '+entity.state+' · '+new Date().toLocaleTimeString():'Entità non ancora presente negli stati HA. Riprova o controlla il pannello KNX.';
 });
 gate();
}
