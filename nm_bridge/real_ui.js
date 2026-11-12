let pilotBusy=false;
const installationStyles=`
.install-heading{display:flex;justify-content:space-between;align-items:start;gap:16px;flex-wrap:wrap}.install-heading h2{font-size:28px;margin:8px 0}.install-heading p{max-width:680px;color:#aec1da;line-height:1.6}.install-toolbar{display:flex;gap:8px;flex-wrap:wrap}.install-room{margin:22px 0}.install-room>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:16px 4px;border-bottom:1px solid #304963;font-size:19px;font-weight:650}.install-room>summary small{font-size:13px;color:#adc1d9;font-weight:400}.install-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:14px;padding-top:16px}.install-device{padding:18px;border:1px solid #304b69;border-radius:16px;background:#12243b;min-width:0}.install-device-top{display:flex;gap:10px;align-items:center}.install-device-top input{width:20px;height:20px;accent-color:#7d79ff}.install-device-top strong{flex:1;overflow-wrap:anywhere}.install-icon{font-size:23px;color:#adcaff}.install-badge{display:inline-block;font-size:12px;font-weight:650;padding:5px 9px;border-radius:7px;margin:12px 0;background:#233d5e;color:#bcd8ff}.install-badge.present{background:#12473d;color:#a3f0cf}.install-badge.update{background:#433c1f;color:#ffe19a}.install-badge.review{background:#50313e;color:#ffbecb}.install-details{font-size:13px;color:#b2c6e0;overflow-wrap:anywhere}.install-details summary{padding:9px 0;cursor:pointer}.install-details p{line-height:1.6}.install-help{font-size:13px;line-height:1.5;color:#ffcf9b}.install-dock{position:sticky;bottom:10px;z-index:20;border:1px solid #6484b8;border-radius:15px;background:#162b45f5;box-shadow:0 10px 30px #0007;padding:16px;margin-top:20px}.install-dock .bar{margin:12px 0 0}.install-dock label{font-size:13px;color:#c2d1e5}.install-dock button{min-height:44px}.commission-tools{margin:15px 0;padding:14px;border-radius:12px;background:#162f43;border:1px solid #3c6478}.commission-tools label{font-size:14px}.commission-tools input[type=checkbox]{width:20px;height:20px}.commission-tools p{font-size:13px;color:#b7cddd;margin:8px 0}.commission-controls{border-top:1px solid #304b69;margin-top:12px;padding-top:12px;display:flex;gap:8px;flex-wrap:wrap}.commission-controls button{min-height:44px;flex:1}.commission-controls button[data-commission-action=stop]{border:2px solid #ffce82;color:#ffe0ad}.commission-level{display:flex;gap:8px;align-items:center;width:100%}.commission-level input{width:80px}.commission-state{width:100%;font-size:13px;line-height:1.5;color:#bdd1eb;min-height:22px}.install-room summary:focus-visible,button:focus-visible{outline:3px solid #b4d2ff;outline-offset:3px}@media(max-width:600px){.install-heading h2{font-size:23px}.install-dock{bottom:4px;padding:12px}.install-dock .primary{width:100%}.install-device{padding:15px}}
`;
function bulkInstallPage(){return `<style>${installationStyles}</style><section class="card" id="bulk-install"><div class="install-heading"><div><div class="workspace-label">Installazione e collaudo</div><h2>Il tuo impianto, stanza per stanza</h2><p>Controlla le funzioni, applica le modifiche e prova i dispositivi installati. I dettagli KNX restano disponibili quando servono.</p></div><div class="install-toolbar"><button id="install-load">Aggiorna elenco</button><button id="install-select-climate" disabled>Seleziona termostati</button><button id="install-edit">Modifica funzioni</button></div></div><p id="install-status" role="status"></p><div class="commission-tools"><label class="row"><input type="checkbox" id="commission-enabled"> Abilita i comandi reali per il collaudo</label><p>I controlli azionano i dispositivi installati. L’abilitazione vale solo in questa schermata; il caricamento dell’elenco non invia comandi.</p><button id="commission-refresh">Leggi stati da HA</button></div><div id="install-list"></div><section class="install-dock"><label class="row"><input type="checkbox" id="install-verified" style="width:auto"> Ho verificato indirizzi e tipi in ETS e il backup HA</label><div class="bar"><button id="install-create" class="primary" disabled>Applica modifiche</button><button id="install-areas">Sincronizza stanze HA</button><button id="install-next" hidden>Apri pubblicazione dashboard</button></div></section><details><summary>Registro delle operazioni</summary><pre id="install-results" style="white-space:pre-wrap" aria-live="polite"></pre></details></section>`;}

function commissioningControls(d){
 if(d.status!=='present'||!d.entity_id||!['light','dimmer','cover','button','switch'].includes(d.type))return '';
 const actions=d.type==='button'?[['press',d.profile==='filter_reset'?'Reset filtro':'Premi']]:d.command_mode==='off_only'?[['off','Spegni']]:d.type==='cover'?[['open','↑ Salita'],['stop','■ Stop'],['close','↓ Discesa']]:[['on','Accendi'],['off','Spegni']];
 const button=(action,label)=>`<button type="button" data-commission-index="${d.index}" data-commission-action="${action}" disabled>${label}</button>`;
 return `<div class="commission-controls">${actions.map(([a,l])=>button(a,l)).join('')}${d.type==='dimmer'?`<div class="commission-level"><label for="commission-level-${d.index}">Luminosità %</label><input id="commission-level-${d.index}" type="number" min="0" max="100" step="1" value="50">${button('brightness','Imposta')}</div>`:''}<div class="commission-state" id="commission-state-${d.index}" role="status">${d.type==='button'?'Invia '+(d.command_mode==='off_only'?'0 (OFF)':'1 (ON)'):d.command_mode==='off_only'?'Comando di solo spegnimento · nessuno stato aggregato':'Stato non ancora letto'}</div></div>`;
}
function climateScheduleLink(device){
 if(device.type!=='climate'||device.status!=='present'||!device.entity_id)return '';
 const source='https://github.com/nicomelot/nm-studio/blob/lab/blueprints/automation/nm_control/cronotermostato.yaml';
 const href='https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url='+encodeURIComponent(source);
 return `<details class="install-details"><summary>Programmazione settimanale</summary><p>Crea una Programmazione e un Interruttore virtuale in Home Assistant, poi importa il modello e seleziona questo clima.</p><a href="${href}" target="_blank" rel="noopener">Apri il modello cronotermostato</a></details>`;
}
function installListMarkup(data,access){
 const groups=new Map();for(const d of data.devices){const room=d.room||'Da assegnare';if(!groups.has(room))groups.set(room,[]);groups.get(room).push(d);}
 const labels={create:'Pronta da creare',update:'Da aggiornare',present:'Installata',review:'Da verificare'};
 return [...groups].map(([room,devices])=>`<details class="install-room" open><summary><span>${escapeHTML(room.split(' / ').at(-1))}</span><small>${devices.length} funzioni</small></summary><div class="install-cards">${devices.map(d=>{
  const reason=installBlocker(d)||(!access.supported_platforms?.includes(d.type==='dimmer'?'light':d.type)?'Piattaforma non disponibile':'');
  const state=reason?'review':d.status,blocked=!!reason||!['create','update'].includes(d.status);
  return `<article class="install-device"><label class="install-device-top"><input type="checkbox" data-install-index="${d.index}" data-blocked="${blocked}" ${blocked?'disabled':'checked'}><span class="install-icon" aria-hidden="true">${d.type==='cover'?'▤':d.type==='dimmer'?'◐':'☼'}</span><strong>${escapeHTML(d.name)}</strong></label><span class="install-badge ${state}">${escapeHTML(labels[state]||'Da verificare')}</span>${state==='review'?`<p class="install-help">${escapeHTML(reason||d.reason)} · Usa “Modifica funzioni” per correggere.</p>`:''}<details class="install-details"><summary>Dettagli KNX</summary><p>${escapeHTML(room)}<br>${escapeHTML(d.reason||'')}<br>${escapeHTML(d.entity_id||'Entità da creare')}</p><p>${escapeHTML(Object.entries(d.fields||{}).filter(([,v])=>v).map(([k,v])=>k+': '+v).join(' · '))}</p></details>${commissioningControls({...d,status:state})}${climateScheduleLink({...d,status:state})}</article>`;
 }).join('')}</div></details>`).join('');
}

function installBlocker(device){
 if(!['light','dimmer','cover','button','switch','climate','binary_sensor','number'].includes(device.type))return 'Tipo da configurare negli strumenti avanzati';
 if(!device.fields.command)return device.type==='binary_sensor'?'Manca l’indirizzo di stato':'Manca il comando';
 if(device.type==='climate'){
  const conflict=typeof etsData==='undefined'?null:etsData?.climate_conflicts?.find(item=>item.command===device.fields.command);
  if(conflict){
   const shared=Object.values(device.fields).filter(ga=>conflict.addresses.includes(ga));
   if(shared.length)return 'Indirizzi clima condivisi fra gateway: '+shared.join(', ');
   const missing=Object.values(device.fields).filter(ga=>ga&&!etsData.addresses.some(a=>a.address===ga&&a.linked));
   if(missing.length)return 'Indirizzi clima non collegati in questo export: '+missing.join(', ');
  }
  if(!device.fields.temperature||!device.fields.target_temperature_state)return 'Manca la temperatura rilevata o lo stato setpoint';
 }
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

function formatCommissionState(e){
 if(!e||['unknown','unavailable'].includes(e.state))return 'Stato non disponibile · nessuna conferma del dispositivo';
 const states={on:'Accesa',off:'Spenta',open:'Aperta',closed:'Chiusa',opening:'In apertura',closing:'In chiusura'};
 const extra=typeof e.brightness==='number'?` · luminosità ${Math.round(e.brightness*100/255)}%`:typeof e.current_position==='number'?` · posizione ${e.current_position}%`:'';
 return 'Stato HA: '+(states[e.state]||e.state)+extra+' · lettura '+new Date().toLocaleTimeString();
}
function wireBulkInstall(){
 let source=null,capability=null,busy=false,rows=[],testPending=0;
 const status=message=>$('install-status').textContent=message;
 const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const selected=()=>rows.filter(r=>r.checked&&r.dataset.blocked!=='true').map(r=>source.devices.find(d=>d.index===Number(r.dataset.installIndex)));
 function paint(){
  $('install-list').innerHTML=installListMarkup(source,capability);
  rows=[...document.querySelectorAll('[data-install-index]')];rows.forEach(r=>r.onchange=gate);
  document.querySelectorAll('[data-commission-action]').forEach(b=>b.onclick=()=>sendTest(b));
  gateTests();
 }
 function gateTests(){document.querySelectorAll('[data-commission-action]').forEach(b=>b.disabled=!source||!$('commission-enabled')?.checked||busy||(testPending>0&&b.dataset.commissionAction!=='stop'));}
 if($('commission-enabled'))$('commission-enabled').onchange=gateTests;
 if($('commission-refresh'))$('commission-refresh').onclick=async()=>{
  if(!source)return;
  try{const data=await api('entities');for(const d of source.devices){const el=$('commission-state-'+d.index);if(!el)continue;const e=data.entities.find(e=>e.entity_id===d.entity_id);el.textContent=d.command_mode==='off_only'?'Comando di solo spegnimento · nessuno stato aggregato':formatCommissionState(e);}}
  catch(e){status('Lettura stati non riuscita: '+e.message);}
 };
 async function sendTest(button){
  const action=button.dataset.commissionAction,index=Number(button.dataset.commissionIndex);
  if(!source||busy||!$('commission-enabled')?.checked||(testPending&&action!=='stop'))return;
  const d=source.devices.find(d=>d.index===index);if(!d||d.status!=='present')return;
  if(d.profile==='filter_reset'&&!confirm('Confermi il reset dopo la pulizia o sostituzione del filtro?'))return;
  const target=$('commission-state-'+index),body={confirm:true,source_fingerprint:source.source_fingerprint,index,entity_id:d.entity_id,action};
  if(action==='brightness'){const raw=$('commission-level-'+index).value;const value=Number(raw);if(!raw.trim()||!Number.isInteger(value)||value<0||value>100){target.textContent='Inserisci una percentuale da 0 a 100.';return;}body.value=value;}
  testPending++;pilotBusy=true;gate();gateTests();target.textContent='Invio comando…';
  try{const done=await post('knx/commission-command',body);target.textContent=done.message;}
  catch(e){target.textContent='Comando non confermato: '+e.message+(d.type==='button'?' Controlla il dispositivo prima di riprovare.':' Leggi lo stato prima di riprovare.');}
  finally{testPending--;pilotBusy=testPending>0;gate();gateTests();}
 }
 const selectClimate=$('install-select-climate');
 const readyClimate=()=>rows.filter(r=>r.dataset.blocked!=='true'
  &&source?.devices.find(d=>d.index===Number(r.dataset.installIndex))?.type==='climate');
 if(selectClimate)selectClimate.onclick=()=>{
  const thermostats=new Set(readyClimate());
  rows.forEach(r=>r.checked=thermostats.has(r));gate();
  status(`${thermostats.size} termostati selezionati.`);
 };
 function gate(){if(selectClimate)selectClimate.disabled=busy||!readyClimate().length;const n=source?selected().length:0;$('install-create').textContent=`Applica ${n} modifiche`;$('install-create').disabled=busy||testPending>0||!n||!$('install-verified').checked||!capability?.available||!capability?.connected;}
 async function run(work){if(busy||pilotBusy)return;busy=true;pilotBusy=true;gate();document.querySelectorAll('#bulk-install input,#bulk-install button').forEach(el=>el.disabled=true);try{await work();}catch(e){status('Interrotto: '+e.message+' Le operazioni già confermate restano salvate. Aggiorna elenco prima di riprovare.');source=null;}finally{busy=false;pilotBusy=false;document.querySelectorAll('#bulk-install button').forEach(el=>el.disabled=false);document.querySelectorAll('#bulk-install input').forEach(el=>el.disabled=false);$('install-verified').disabled=false;rows.forEach(r=>r.disabled=!source||r.dataset.blocked==='true');gate();gateTests();}}
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
  source=null;rows=[];if($('commission-enabled'))$('commission-enabled').checked=false;$('install-list').innerHTML='';$('install-verified').checked=false;status('Confronto con la configurazione KNX di Home Assistant.');
  const access=await api('knx/panel-capability');
  if(!access.available){
   status(access.message+' Per la simulazione torna a Importa ETS.');
   return;
  }
  const data=await api('knx/installation-review');
  if(etsData?.project_key&&data.project!==etsData.project_key)throw Error('Salva prima le funzioni del progetto aperto.');
  source=data;capability=access;
  paint();
  const labels={create:'da creare',update:'da aggiornare',present:'installate',review:'da verificare'};
  const summary=Object.entries(labels).map(([key,label])=>`${data.devices.filter(d=>d.status===key).length} ${label}`).join(' · ');
  const connection=access.connected?'':' KNX non connesso. Per la simulazione torna a Importa ETS.';
  status(summary+connection);
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
   let done;
   try{
    done=await post('knx/installation-apply',{confirm:true,backup_confirmed:true,ets_confirmed:true,source_fingerprint:fingerprint,index:d.index,expected:d});
    if(!done.linked||done.stop)throw Error(done.message||'Verifica la funzione in HA.');
   }catch(e){
    const detail=`${d.name} (${i+1}/${devices.length}): ${e.message}`;
    $('install-results').textContent+=detail+'\n';throw Error(detail);
   }
   $('install-results').textContent+=`${d.name}: ${done.entity_id} · ${done.updated?'aggiornata':'creata e associata'}\n`;
   syncCreatedAssociation(source.project,d,done.entity_id);fingerprint=done.source_fingerprint;d.entity_id=done.entity_id;d.status='present';d.reason='Installazione confermata; esegui il collaudo.';
   const row=rows.find(r=>Number(r.dataset.installIndex)===d.index);row.checked=false;row.dataset.blocked='true';
  }
  source.source_fingerprint=fingerprint;paint();$('install-verified').checked=false;$('install-next').hidden=false;
  status(`${devices.length} modifiche applicate. Abilita il collaudo e prova i dispositivi nelle schede qui sopra.`);
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
 const fieldsByType={button:['command'],switch:['command','feedback'],light:['command','feedback'],dimmer:['command','feedback','brightness','brightness_feedback'],cover:['command','stop']};
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
