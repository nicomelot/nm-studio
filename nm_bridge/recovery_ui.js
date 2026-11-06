// Compare ETS evidence with drafts; import prepares configuration, never HA entities.
function recoveryReport(data, drafts){
 const supported=new Set(['light','dimmer','cover','climate']);
 const commands=new Set(drafts.map(w=>w.fields?.command).filter(Boolean));
 const referenced=new Set(drafts.flatMap(w=>Object.values(w.fields||{})).filter(Boolean));
 const addresses=new Map((data?.addresses||[]).map(a=>[a.address,a]));
 const groups=new Map();
 for(const s of data?.suggestions||[]){
  if(!supported.has(s.kind)||!s.command||commands.has(s.command))continue;
  if(!groups.has(s.command))groups.set(s.command,[]);
  groups.get(s.command).push(s);
 }
 const missing=[];
 for(const [command,list] of groups){
  const signatures=new Set(list.map(s=>JSON.stringify([s.kind,...['feedback','relative','stop','brightness','brightness_feedback','position','position_command','position_feedback','temperature','target_temperature_state','heat_cool','heat_cool_state','operation_mode','operation_mode_state'].map(k=>s[k]||'')])));
  const s=list[0],a=addresses.get(command);
  missing.push({...s,command,linked:!!a?.linked,ambiguous:signatures.size>1,
   shared:referenced.has(command)});
 }
 const covered=new Set([...referenced,...groups.keys()]);
 // Feedback and auxiliary addresses belonging to a missing suggestion are not extra functions.
 for(const list of groups.values())for(const s of list)for(const value of Object.values(s))
  if(typeof value==='string'&&addresses.has(value))covered.add(value);
 return {missing,other:[...addresses.values()].filter(a=>!covered.has(a.address)),
  stale:drafts.filter(w=>w.fields?.command&&!addresses.has(w.fields.command))};
}

function addRecoveredWidget(command, kind, automatic=true){
 if(!etsData||!widgetFields[kind])return false;
 if(widgetDrafts.some(w=>w.fields.command===command))return false;
 const address=etsData.addresses.find(a=>a.address===command);
 if(!address)return false;
 const report=recoveryReport(etsData,widgetDrafts);
 const candidate=automatic?report.missing.find(s=>s.command===command):null;
 if(automatic&&(!candidate||candidate.kind!==kind||candidate.ambiguous||candidate.shared||!candidate.linked))return false;
 const fields={command};
 if(candidate)for(const [key] of widgetFields[kind]){
  if(key==='command')continue;
  if(kind==='cover'&&key==='feedback')continue;
  fields[key]=linkedGA(candidate[key])||'';
 }
 const match=(etsData.room_matches||[]).find(m=>m.command===command);
 const room=resolveRoomAlias(match?.room||'Da assegnare');
 const known=structureRooms(false);
 widgetDrafts.push(newWidget(kind,candidate?.name||address.name||command,fields,
  automatic?'Riconosciuta da ETS · '+(candidate.reason||'verifica comando e feedback'):'Aggiunta manuale da indirizzo ETS · verifica funzione e DPT',
  known.includes(room)?room:'Da assegnare'));
 widgetDirty=true;
 return true;
}

function recoverableUpgrades(data,drafts){
 return drafts.flatMap((w,index)=>{
  const found=(data?.suggestions||[]).filter(s=>s.command===w.fields.command&&s.kind==='dimmer');
  const all=(data?.suggestions||[]).filter(s=>s.command===w.fields.command);
  const linked=ga=>(data?.addresses||[]).some(a=>a.address===ga&&a.linked);
  return w.kind==='light'&&w.command_mode!=='off_only'&&all.length===1&&found.length===1&&linked(found[0].command)&&linked(found[0].brightness)?[{index,candidate:found[0]}]:[];
 });
}
function upgradeRecoveredDimmer(index){
 const upgrade=recoverableUpgrades(etsData,widgetDrafts).find(u=>u.index===index);
 if(!upgrade)return false;
 const w=widgetDrafts[index],s=upgrade.candidate;
 // Keep existing names, rooms, entity links and installer overrides.
 for(const [key] of widgetFields.dimmer)if(!w.fields[key]&&linkedGA(s[key]))w.fields[key]=s[key];
 w.kind='dimmer';w.source='Dimmer riconosciuto da ETS; verificare le capacità della eventuale entità HA già collegata';
 widgetDirty=true;return true;
}
function reconcileRecognizedFunctions(){
 let upgraded=0,added=0;
 for(const u of recoverableUpgrades(etsData,widgetDrafts))if(upgradeRecoveredDimmer(u.index))upgraded++;
 for(const w of widgetDrafts){
  if(w.command_mode==='off_only')continue;
  const found=(etsData?.suggestions||[]).filter(s=>s.command===w.fields.command);
  if(found.length!==1||found[0].kind!==w.kind)continue;
  for(const [key] of widgetFields[w.kind]||[]){
   if(w.kind==='cover'&&['feedback','position'].includes(key))continue;
   if(!w.fields[key]&&linkedGA(found[0][key])){w.fields[key]=found[0][key];widgetDirty=true;}
  }
 }
 for(const s of recoveryReport(etsData,widgetDrafts).missing)
  if(addRecoveredWidget(s.command,s.kind))added++;
 return {added,upgraded};
}
function renderKeepingScroll(){
 const top=window.scrollY,left=window.scrollX;
 render();window.scrollTo({top,left,behavior:'instant'});
}
function recoveryPanel(){
 if(!etsData)return '';
 const report=recoveryReport(etsData,widgetDrafts);
 const row=(s,manual=false)=>`<div class="row recovery-row" data-search="${escapeHTML((s.name+' '+(s.command||s.address)).toLowerCase())}" style="margin:8px 0"><div class="grow"><b>${escapeHTML(s.name)}</b><p class="small muted">${escapeHTML(s.command||s.address)} · ${escapeHTML(s.kind||s.dpt||'Tipo da verificare')}${!s.linked?' · Nessun collegamento ETS rilevato':''}${s.shared?' · Indirizzo già usato in un altro campo':''}${s.ambiguous?' · Proposte discordanti':''}</p></div>${!manual&&!s.ambiguous&&!s.shared&&s.linked?`<button data-recover="${escapeHTML(s.command)}" data-kind="${s.kind}">Aggiungi ${escapeHTML(s.name)} alle funzioni</button>`:`<select class="recovery-kind" aria-label="Tipo funzione per ${escapeHTML(s.name)}" style="max-width:180px"><option value="">Scegli tipo…</option><option value="light">Luce</option><option value="dimmer">Dimmer</option><option value="cover">Tapparella</option><option value="climate">Termostato</option></select><button data-recover-manual="${escapeHTML(s.command||s.address)}">Prepara manualmente</button>`}</div>`;
 return `<section class="card" id="recovery-panel"><div class="workspace-label">Confronto con il progetto ETS aperto</div><h2>Riconoscimento automatico</h2><p>${widgetDrafts.length} funzioni nel riepilogo · ${report.missing.length} proposte da verificare · ${report.other.length} altri indirizzi da esaminare. Gli indirizzi possono essere comandi, feedback o funzioni ausiliarie: non corrispondono necessariamente a dispositivi mancanti.</p><input id="recovery-search" placeholder="Cerca L5, nome o indirizzo di gruppo" aria-label="Cerca funzioni mancanti"><div style="max-height:360px;overflow:auto">${report.missing.map(s=>row(s)).join('')||'<p>Le funzioni riconosciute sono già inserite nel riepilogo.</p>'}<details><summary>Avanzato: indirizzi non classificati (${report.other.length})</summary>${report.other.map(a=>row(a,true)).join('')}</details></div>${report.stale.length?`<p class="warning">${report.stale.length} widget hanno un comando assente dal progetto importato: ${report.stale.map(w=>escapeHTML(w.name+' ('+w.fields.command+')')).join(', ')}. Sono stati conservati: verifica prima di modificarli.</p>`:''}<p class="small muted">Le funzioni vengono inserite nella bozza senza creare entità HA. Controlla il riepilogo, poi salva e continua. Le associazioni esistenti vengono conservate.</p><p id="recovery-status" aria-live="polite"></p></section>`;
}

function wireRecovery(){
 if(!$('recovery-panel'))return;
 const upgrades=recoverableUpgrades(etsData,widgetDrafts);
 if(upgrades.length){
  $('recovery-panel').insertAdjacentHTML('afterbegin',`<div class="card"><h3>Dimmer riconosciuti nelle luci salvate</h3>${upgrades.map(u=>`<p>${escapeHTML(widgetDrafts[u.index].name)} <button data-upgrade-dimmer="${u.index}">Completa come dimmer</button></p>`).join('')}<p>Conserva nomi, stanze e associazioni. Una entità HA già creata va aggiornata separatamente.</p></div>`);
  document.querySelectorAll('[data-upgrade-dimmer]').forEach(b=>b.onclick=()=>{if(upgradeRecoveredDimmer(Number(b.dataset.upgradeDimmer)))render();});
 }
 $('recovery-search').oninput=e=>document.querySelectorAll('.recovery-row').forEach(row=>{
  row.hidden=!row.dataset.search.includes(e.target.value.trim().toLowerCase());row.style.display=row.hidden?'none':'';
  if(e.target.value&&row.closest('details'))row.closest('details').open=true;
 });
 document.querySelectorAll('[data-recover]').forEach(b=>b.onclick=()=>{
  if(addRecoveredWidget(b.dataset.recover,b.dataset.kind)){renderKeepingScroll();message('Aggiunta '+widgetDrafts[widgetDrafts.length-1].name+'. Scegli la stanza, poi premi Salva e continua.');}
 });
 document.querySelectorAll('[data-recover-manual]').forEach(b=>b.onclick=()=>{
  const kind=b.closest('.recovery-row').querySelector('.recovery-kind').value;
  if(!kind){$('recovery-status').textContent='Scegli il tipo di funzione da preparare.';return;}
  if(addRecoveredWidget(b.dataset.recoverManual,kind,false)){renderKeepingScroll();message('Aggiunta manualmente '+widgetDrafts[widgetDrafts.length-1].name+'. Verifica la funzione: un comando generale non è una singola luce.');}
 });
}

function realFlowBar(){
 const steps=[['ets','1 · Importa ETS'],['widgets','2 · Controlla'],['real','3 · Applica e prova']];
 return `<section class="card"><b>Percorso impianto reale</b><div class="bar" style="margin-top:12px">${steps.map(([p,label])=>`<button data-real-flow="${p}" ${p===page?'class="primary" aria-current="step"':''}>${label}</button>`).join('')}</div><p class="small muted">Controlla le proposte, salva e installa. Le associazioni esistenti e la pubblicazione restano disponibili nelle rispettive schermate.</p></section>`;
}


// Readiness of the configuration, independent of the HA entity creation step.
function widgetFlowIssues(drafts){
 const issues=[],commands=new Set();
 if(!drafts.length)return [{index:0,message:"Aggiungi almeno una funzione prima di continuare."}];
 drafts.forEach((w,index)=>{
  const label=w.name?.trim()||'Funzione '+(index+1);
  const add=reason=>issues.push({index,message:label+': '+reason});
  if(!w.name?.trim())add('inserisci un nome.');
  if(!w.room?.trim()||w.room==='Da assegnare')add('scegli una stanza.');
  for(const [key,label,,required] of widgetFields[w.kind]||[])if(required&&!w.fields?.[key])add('completa '+label+'.');
  if(w.fields?.command){if(commands.has(w.fields.command))add('comando già usato da un’altra funzione: verifica il duplicato.');commands.add(w.fields.command);}
 });
 return issues;
}
function focusWidget(index){
 const row=document.querySelector('.widget-proposal[data-index="'+index+'"]');
 if(!row)return;
 row.scrollIntoView({behavior:'smooth',block:'center'});
 row.querySelector('.widget-room')?.focus({preventScroll:true});
}
function wireClearWidgetFlow(){
 if(!etsData||!$('widget-save-next'))return;
 const content=$('content');
 const style=document.createElement('style');
 style.textContent='.widget-flow-actions{position:sticky;bottom:12px;z-index:20;background:#14243c;border:2px solid #759aff;border-radius:14px;padding:14px;box-shadow:0 4px 24px #0008;display:flex;flex-wrap:wrap;gap:12px;align-items:center}.widget-flow-actions p{flex:1 1 240px;margin:0}.widget-flow-actions button{min-height:46px}.widget-proposal{scroll-margin:100px}.widget-proposal details{margin-top:12px}.widget-proposal summary{cursor:pointer;padding:12px;background:#192d49;border-radius:8px}';
 content.append(style);
 const controls=$('widget-export').closest('.card');
 const tools=document.createElement('details');tools.innerHTML='<summary>Aggiunta manuale e strumenti avanzati</summary><p class="small">Per funzioni già riconosciute usa i pulsanti Aggiungi nel confronto ETS. Qui puoi preparare funzioni personalizzate.</p>';
 controls.prepend(tools);
 const bar=$('widget-export').closest('.bar');tools.append(bar);
 $('widget-export').classList.remove('primary');
 const bulk=$('widget-bulk-room')?.closest('.card');if(bulk)tools.append(bulk);
 document.querySelectorAll('.widget-proposal').forEach(row=>{
  const details=document.createElement('details');details.innerHTML='<summary>Verifica indirizzi KNX e anteprima</summary>';
  row.append(details);
  for(const selector of ['.widget-preview','.grid','.widget-status']){const el=row.querySelector(selector);if(el)details.append(el);}
 });
 const actions=document.createElement('section');actions.className='widget-flow-actions';
 actions.innerHTML='<p id="widget-flow-status" role="status" aria-live="polite"></p><button id="widget-flow-back">Indietro: riepilogo</button>';
 content.append(actions);
 const save=$('widget-save'),next=$('widget-save-next');
 save.classList.remove('primary');save.textContent='Salva bozza';
 next.classList.add('primary');next.textContent='Salva e continua alla creazione';
 next.onclick=async()=>{if(await save.onclick()===true)setPage('real');};
 actions.append(save,next);
 const associate=document.createElement('button');associate.textContent='Usa entità già esistenti';associate.onclick=async()=>{if(await save.onclick()===true)setPage('matches');};tools.append(associate);
 $('widget-flow-back').onclick=()=>setPage('live');
 function update(){
  const issues=widgetFlowIssues(widgetDrafts);
  $('widget-flow-status').textContent=(widgetDirty?'Modifiche da salvare. ':'Configurazione salvata. ')+widgetDrafts.length+' funzioni. '+(issues.length?issues[0].message+' Puoi continuare con le funzioni pronte e rifinire questa dopo.':'Pronto per creare le funzioni selezionate.');
 }
 content.addEventListener('input',update);content.addEventListener('change',update);update();
 const note=controls.querySelector('.warning');if(note)note.textContent='Controlla le funzioni riconosciute e continua alla creazione. Puoi completare le stanze e le funzioni incomplete in seguito. Nessuna entità HA viene creata in questo passaggio.';
}


function wireRealDashboardUpdate(){
 const section=document.createElement('section');section.className='card';
 section.innerHTML='<h3>Aggiorna la dashboard reale esistente</h3><p>Genera l’anteprima reale, poi confrontala con la dashboard di questo progetto. Le personalizzazioni manuali vengono conservate. Controlla il confronto prima di aggiornare.</p><div class="bar"><button id="real-update-preview">1 · Confronta dashboard esistente</button><button id="real-update-backup" disabled>Scarica copia precedente</button><button id="real-update-apply" class="primary" disabled>2 · Aggiorna con backup</button></div><p id="real-update-status" role="status" aria-live="polite">Nessun confronto eseguito.</p><details><summary>Confronta le configurazioni complete</summary><h4>Prima</h4><pre id="real-update-before" style="max-height:300px;overflow:auto"></pre><h4>Dopo</h4><pre id="real-update-after" style="max-height:300px;overflow:auto"></pre></details>';
 $('dash-status').before(section);
 let preview=null,busy=false;
 const status=$('real-update-status'),apply=$('real-update-apply'),compare=$('real-update-preview'),download=$('real-update-backup');
 const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 function invalidate(){preview=null;apply.disabled=true;download.disabled=true;status.textContent='Anteprima cambiata: ripeti il confronto.';}
 $('dash-generate').addEventListener('click',invalidate);
 $('dash-publish-path').addEventListener('input',invalidate);
 $('dash-code').addEventListener('input',invalidate);
 compare.onclick=async()=>{
  if(busy)return;
  invalidate();
  if(!nmDashboardDraft){status.textContent='Premi prima Genera anteprima reale.';return;}
  if(widgetDirty||structureDirty){status.textContent='Salva prima le modifiche alle funzioni e alle stanze.';return;}
  if($('dash-code').value!==JSON.stringify(nmDashboardDraft.dashboard,null,2)){status.textContent='Rigenera l’anteprima: il JSON modificato non viene applicato automaticamente.';return;}
  busy=true;compare.disabled=true;
  try{
   preview=await post('dashboard/update-preview',{url_path:$('dash-publish-path').value.trim()});
   $('real-update-before').textContent=JSON.stringify(preview.previous_dashboard,null,2);
   $('real-update-after').textContent=JSON.stringify(preview.dashboard,null,2);
   status.textContent=preview.changed?preview.old_views+' viste attuali → '+preview.new_views+' viste nuove. '+preview.notice:'La dashboard è già aggiornata.';
   apply.disabled=!preview.changed;download.disabled=false;
  }catch(e){status.textContent='Confronto non riuscito: '+e.message;}finally{busy=false;compare.disabled=false;}
 };
 download.onclick=()=>{
  if(!preview)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(preview.previous_dashboard,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=preview.url_path+'-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 apply.onclick=async()=>{
  if(busy||!preview||!preview.changed)return;
  if(!confirm('Aggiornare /'+preview.url_path+'? Applicheremo il risultato del confronto conservando le personalizzazioni manuali. Verrà salvato un backup completo prima della scrittura.'))return;
  busy=true;apply.disabled=true;compare.disabled=true;
  try{
   const result=await post('dashboard/update',{confirm:true,url_path:preview.url_path,expected_current:preview.expected_current,expected_fingerprint:preview.expected_fingerprint});
   status.textContent=result.unchanged?'Dashboard già aggiornata.':'Dashboard aggiornata e riletta. Backup: '+result.backup+'. Puoi scaricare la copia precedente con il pulsante qui sopra.';
   preview.changed=false;
  }catch(e){status.textContent=e.message+' Ripeti il confronto prima di un altro tentativo.';preview.changed=false;}
  finally{busy=false;compare.disabled=false;}
 };
}


let busNextCursor=null;
function wireBusFilters(){
 const row=document.createElement('div');row.className='bar';
 row.innerHTML='<label>Mittente KNX<input id="bus-source" placeholder="1.1.10"></label><label>Ricevuto da<input id="bus-start" type="datetime-local"></label><label>Ricevuto fino a<input id="bus-end" type="datetime-local"></label><button id="bus-search">Cerca eventi</button><button id="bus-next" disabled>Pagina successiva</button>';
 $('bus-status').before(row);busNextCursor=null;
 $('bus-search').onclick=()=>busAction('refresh');
 $('bus-next').onclick=()=>busAction('next');
 for(const id of ['bus-filter','bus-source','bus-start','bus-end'])$(id).addEventListener('input',()=>{busNextCursor=null;$('bus-next').disabled=true;});
}
function busQuery(action){
 const query=new URLSearchParams({ga:$('bus-filter').value.trim()});
 if($('bus-source'))query.set('source',$('bus-source').value.trim());
 for(const key of ['start','end'])if($('bus-'+key)?.value)query.set(key,new Date($('bus-'+key).value).toISOString());
 if(action==='next'&&busNextCursor)query.set('before',busNextCursor);
 return query.toString();
}


let functionSearch='';
function searchFunctionAddresses(data,query){
 const words=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
 if(!words.length)return [];
 return (data?.addresses||[]).filter(a=>words.every(word=>(a.address+' '+a.name).toLocaleLowerCase().includes(word))).slice(0,30);
}
function offAddressCompatible(a){return !!a&&(!a.dpt||['DPST-1-1','DPT-1.001','1.001'].includes(a.dpt));}
function prepareOffButton(command){
 const a=etsData?.addresses?.find(a=>a.address===command);
 if(!offAddressCompatible(a))return false;
 const matches=widgetDrafts.filter(w=>w.fields.command===command);
 if(matches.length>1||matches.some(w=>w.kind!=='light'))return false;
 if(!matches.length){
  if(!addRecoveredWidget(command,'light',false))return false;
 }
 const w=widgetDrafts.find(w=>w.fields.command===command);
 w.command_mode='off_only';w.fields.feedback='';widgetDirty=true;
 return true;
}
function wireOffButtons(){
 if(!etsData)return;
 const panel=document.createElement('section');panel.className='card';
 panel.innerHTML='<h2>Cerca funzioni e aggiungi pulsanti</h2><label for="function-search">Nome, stanza o indirizzo di gruppo</label><input id="function-search" type="search" placeholder="Es. OFF, generale, 2/1/0"><p id="function-search-count" class="small muted" role="status"></p><div id="function-search-results" style="max-height:300px;overflow:auto"></div><p class="small muted">I pulsanti di solo spegnimento riutilizzano una funzione luce e inviano solo OFF dalla dashboard generata. L’entità HA sottostante resta disponibile nelle altre viste. Verifica che il GA sia un comando DPT 1.001.</p>';
 $('content').prepend(panel);
 $('function-search').value=functionSearch;
 function filter(){
  functionSearch=$('function-search').value;
  const query=functionSearch.trim().toLocaleLowerCase();let shown=0;
  document.querySelectorAll('.widget-proposal').forEach(row=>{
   const w=widgetDrafts[Number(row.dataset.index)];
   const text=[w.name,w.room,...Object.values(w.fields)].join(' ').toLocaleLowerCase();
   row.hidden=!query.split(/\s+/).every(part=>text.includes(part));if(!row.hidden)shown++;
  });
  $('function-search-count').textContent=shown+' funzioni visibili su '+widgetDrafts.length;
  const found=searchFunctionAddresses(etsData,functionSearch);
  $('function-search-results').innerHTML=found.map(a=>{
   const existing=widgetDrafts.filter(w=>w.fields.command===a.address);
   const allowed=offAddressCompatible(a)&&existing.length<=1&&existing.every(w=>w.kind==='light');
   const already=existing[0]?.command_mode==='off_only';
   return `<div class="row" style="padding:10px 0;border-bottom:1px solid #304963"><div class="grow"><b>${escapeHTML(a.name)}</b><div class="small muted">${escapeHTML(a.address)} · ${escapeHTML(a.dpt||'DPT da verificare')}</div></div><button data-off-ga="${escapeHTML(a.address)}" ${!allowed||already?'disabled':''}>${already?'Solo spegnimento configurato':!allowed?'Tipo da verificare':existing.length?'Usa come solo spegnimento':'+ Pulsante solo spegnimento'}</button></div>`;
  }).join('')||(query?'<p class="small muted">Nessun GA corrispondente nel progetto ETS.</p>':'');
  if(found.length===30)$('function-search-count').textContent+=' · primi 30 GA: affina la ricerca';
  document.querySelectorAll('[data-off-ga]').forEach(b=>b.onclick=()=>{
   if(prepareOffButton(b.dataset.offGa)){renderKeepingScroll();message('Pulsante preparato. Salva la configurazione e aggiorna la dashboard generata.');}
  });
 }
 $('function-search').oninput=filter;
 document.querySelectorAll('.widget-proposal').forEach(row=>{
  const w=widgetDrafts[Number(row.dataset.index)];
  if(w.kind==='light'){
   const selector=document.createElement('label');selector.className='small';
   selector.innerHTML='<span>Comportamento del comando</span><select class="widget-command-mode"><option value="toggle">Luce ON/OFF</option><option value="off_only">Pulsante solo spegnimento</option></select>';
   row.querySelector('.widget-name').after(selector);
   const input=selector.querySelector('select');input.value=w.command_mode||'toggle';
   input.onchange=()=>{w.command_mode=input.value;if(w.command_mode==='off_only')w.fields.feedback='';widgetDirty=true;renderKeepingScroll();};
   if(w.command_mode==='off_only'){
    row.querySelector('.widget-ga[data-field="feedback"]').closest('label').hidden=true;
    row.querySelector('.widget-preview .smart-state').textContent='Spegni';
    row.querySelector('.widget-preview .smart-meta').textContent='Invia sempre OFF · nessuno stato aggregato';
   }
  }
  row.querySelectorAll('.widget-ga').forEach(select=>{
   const options=[...select.options].map(o=>({value:o.value,text:o.textContent}));
   const search=document.createElement('input');search.type='search';search.placeholder='Cerca nome o GA…';search.setAttribute('aria-label','Filtra indirizzi di gruppo');search.style.marginTop='8px';
   select.before(search);search.oninput=e=>{
    e.stopPropagation();
    const selected=select.value,q=search.value.toLocaleLowerCase().trim();
    select.innerHTML=options.filter(o=>!o.value||o.value===selected||o.text.toLocaleLowerCase().includes(q)).map(o=>`<option value="${escapeHTML(o.value)}">${escapeHTML(o.text)}</option>`).join('');select.value=selected;
   };
  });
 });
 filter();
}


function knxPrerequisitePanel(){
 return `<section class="card" id="knx-prerequisite"><div class="workspace-label">Collegamento impianto</div><h2>KNX in Home Assistant</h2><p id="knx-prerequisite-status" role="status">Verifica della connessione in corso…</p><p class="small muted">L’integrazione ufficiale KNX è già inclusa in Home Assistant. Per il primo collegamento scegli l’interfaccia KNX/IP rilevata oppure inserisci IP e credenziali richiesti. L’importazione ETS può essere preparata anche prima del collegamento.</p><div class="bar"><a id="knx-prerequisite-setup" href="https://my.home-assistant.io/redirect/config_flow/?domain=knx" target="_blank" rel="noopener noreferrer">Configura KNX in Home Assistant</a><a href="/config/integrations/integration/knx" target="_blank" rel="noopener noreferrer">Gestisci connessione KNX</a><button id="knx-prerequisite-refresh">Ricontrolla connessione</button></div></section>`;
}
async function checkKnxPrerequisite(){
 const status=$('knx-prerequisite-status'),button=$('knx-prerequisite-refresh'),setup=$('knx-prerequisite-setup');
 if(!status||!button||!setup)return;
 button.disabled=true;setup.hidden=true;
 try{
  const result=await api('knx/panel-capability');
  if(result.available){status.textContent=result.connected?'KNX configurato e connesso: puoi procedere con il progetto.':'KNX configurato, ma non connesso. Apri Gestisci connessione KNX e verifica l’interfaccia.';}
  else{status.textContent=result.message+' Se non hai ancora configurato KNX, apri la configurazione guidata; altrimenti verifica connessione e autorizzazioni.';setup.hidden=false;}
 }catch(e){status.textContent='Verifica non riuscita: '+e.message+'. Controlla la connessione e riprova.';}
 finally{button.disabled=false;}
}
function wireKnxPrerequisite(){
 if(!$('knx-prerequisite-refresh'))return;
 $('knx-prerequisite-refresh').onclick=checkKnxPrerequisite;
 checkKnxPrerequisite();
}
