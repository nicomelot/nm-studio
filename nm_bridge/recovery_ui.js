// Compare ETS evidence with drafts; import prepares configuration, never HA entities.
function recoveryReport(data, drafts){
 const supported=new Set(['light','dimmer','cover','climate','button','switch','binary_sensor','number']);
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
  const signatures=new Set(list.map(s=>JSON.stringify([s.kind,s.profile||'',s.command_mode||'toggle',...['feedback','relative','stop','brightness','brightness_feedback','position','position_command','position_feedback','temperature','target_temperature_state','heat_cool','heat_cool_state','operation_mode','operation_mode_state','on_off','on_off_state','controller_mode','controller_mode_state','fan_speed','fan_speed_state','swing','swing_state'].map(k=>s[k]||'')])));
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
  if(candidate.command_mode==='off_only'&&key==='feedback')continue;
  fields[key]=linkedGA(candidate[key])||'';
 }
 const match=(etsData.room_matches||[]).find(m=>m.command===command);
 const parent=candidate?.climate_command&&widgetDrafts.find(w=>w.kind==='climate'&&w.fields.command===candidate.climate_command);
 const room=resolveRoomAlias(parent?.room&&parent.room!=='Da assegnare'?parent.room:match?.room||'Da assegnare');
 const known=structureRooms(false);
 widgetDrafts.push(newWidget(kind,candidate?.name||address.name||command,fields,
  automatic?'Riconosciuta da ETS · '+(candidate.reason||'verifica comando e feedback'):'Aggiunta manuale da indirizzo ETS · verifica funzione e DPT',
  known.includes(room)?room:'Da assegnare','',true,candidate?.command_mode,candidate?.profile));
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
 const editor=row.querySelector('.widget-editor');if(editor)editor.open=true;
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
 tools.append($('widget-export')); // Keep widget creation visible outside advanced tools.
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
function widgetAddressCompatible(kind,field,address,profile){
 const profileDpt={fan_auto:'1.003',fan_auto_inverted:'1.003',flap_position:'5.001',
  suspend:'1.001',suspend_inverted:'1.001',suspend_delay:'7.005',filter_reset:'1.017',filter_alarm:'1.002'};
 if((kind==='climate'||profileDpt[profile])&&address?.dpt){
  const match=address.dpt.match(/^(?:DPST-|DPT-)?(\d+)[.-](\d+)$/i);
  const hint=profileDpt[profile]?'DPT '+profileDpt[profile]:widgetFields.climate.find(f=>f[0]===field)?.[2];
  return !match||!hint||hint==='DPT '+Number(match[1])+'.'+String(Number(match[2])).padStart(3,'0');
 }
 if(!['button','switch'].includes(kind)||!address?.dpt)return true;
 if(offAddressCompatible(address))return true;
 return kind==='switch'&&field==='feedback'&&['DPST-1-11','DPT-1.011','1.011'].includes(address.dpt);
}
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
  if(w.kind==='button'&&w.profile!=='filter_reset'){
   const selector=document.createElement('label');
   selector.className='small';
   selector.innerHTML='<span>Valore alla pressione</span><select class="widget-command-mode"><option value="on_only">1 (ON)</option><option value="off_only">0 (OFF)</option></select>';
   row.querySelector('.widget-name').after(selector);
   const input=selector.querySelector('select');
   input.value=w.command_mode||'on_only';
   input.onchange=()=>{w.command_mode=input.value;widgetDirty=true;renderKeepingScroll();};
   row.querySelector('.widget-preview .smart-state').textContent='Premi';
   row.querySelector('.widget-preview .smart-meta').textContent=input.value==='off_only'?'Invia 0 (OFF)':'Invia 1 (ON)';
  }
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


function createWidgetRoom(widget, name, parentId, buildingName='') {
 name=name.trim();buildingName=buildingName.trim();
 if(!name||name.length>80||name.includes('/')||name==='Da assegnare')throw Error('Inserisci un nome stanza di 1–80 caratteri, senza /.');
 let parent=structureDraft.find(n=>n.id===parentId),pending=[];
 const newId=()=>{let i=1;while([...structureDraft,...pending].some(n=>n.id==='manual_room_'+i))i++;return 'manual_room_'+i;};
 if(!structureDraft.length){
  if(!buildingName||buildingName.length>80||buildingName.includes('/'))throw Error('Inserisci il nome dell’edificio (massimo 80 caratteri, senza /).');
  parent={id:newId(),parent:null,type:'building',name:buildingName,active:true,source:'manual'};pending.push(parent);
 }else if(!parent||!['building','floor'].includes(parent.type)||!structureAncestorsActive(parent.id))throw Error('Scegli un edificio o piano attivo.');
 const existing=structureDraft.find(n=>n.parent===parent.id&&n.name.toLocaleLowerCase()===name.toLocaleLowerCase());
 if(existing&&(existing.type!=='room'||!structureAncestorsActive(existing.id)))throw Error('Questo nome è già usato da un elemento diverso o nascosto.');
 if(!existing){
  if(structureDraft.length+pending.length+1>250||structureDraft.filter(n=>n.type==='room').length>=200)throw Error('Limite di stanze o elementi edificio raggiunto.');
  pending.push({id:newId(),parent:parent.id,type:'room',name,active:true,source:'manual'});
 }
 const room=existing||pending.at(-1),path=nodePath(room.id,[...structureDraft,...pending]);
 if(path.length>240)throw Error('Percorso stanza troppo lungo: abbrevia il nome.');
 structureDraft.push(...pending);widget.room=path;refreshEditableRooms();return path;
}
function assignManualWidgetGA(widget, field, value){
 const ga=value.trim();
 if(!/^(?:[0-9]|[12][0-9]|3[01])\/[0-7]\/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$/.test(ga))throw Error('GA non valido. Usa principale 0–31 / intermedio 0–7 / gruppo 0–255, per esempio 1/2/3.');
 if(!widgetFields[widget.kind]?.some(f=>f[0]===field))throw Error('Campo widget non valido.');
 const address=etsData?.addresses?.find(a=>a.address===ga);
 if(!widgetAddressCompatible(widget.kind,field,address))throw Error('DPT incompatibile con questo campo.');
 widget.fields[field]=ga;widgetDirty=true;return ga;
}
function revealWidgetEditor(index){
 functionSearch='';renderKeepingScroll();
 const row=document.querySelector(`.widget-proposal[data-index="${index}"]`);
 if(!row)return;row.hidden=false;
 for(const details of row.querySelectorAll('.widget-editor, .widget-editor > .widget-edit-body > details'))details.open=true;
 const details=row.querySelector('details');if(details)details.open=true;
 row.scrollIntoView({block:'center'});row.querySelector('.widget-name')?.focus({preventScroll:true});
}
// Reorder only draft objects or change their room, preserving GA, HA bindings and profiles.
function placeWidget(drafts,from,to,room){
 if(!Number.isInteger(from)||!Number.isInteger(to)||from<0||from>=drafts.length||to<0||to>=drafts.length)return false;
 const widget=drafts[from];
 if(room!==undefined&&(typeof room!=='string'||!room.trim()))return false;
 if(from===to&&(room===undefined||widget.room===room))return false;
 if(room!==undefined)widget.room=room;
 drafts.splice(from,1);drafts.splice(to,0,widget);return true;
}
let widgetPlacementUndo=null,compactSelectedWidget=null,compactDestinationRoom='';
const compactOpenWidgets=new WeakSet();
function rememberWidgetPlacement(drafts){return drafts.map(widget=>({widget,room:widget.room,afterRoom:widget.room}));}
function canRestoreWidgetPlacement(drafts,snapshot){
 return !!snapshot&&snapshot.length===drafts.length&&snapshot.every(item=>drafts.includes(item.widget)&&item.widget.room===item.afterRoom);
}
function restoreWidgetPlacement(drafts,snapshot){
 if(!canRestoreWidgetPlacement(drafts,snapshot))return false;
 for(const item of snapshot)item.widget.room=item.room;
 drafts.splice(0,drafts.length,...snapshot.map(item=>item.widget));return true;
}
function wireCompactWidgetEditor(){
 if(!etsData||!$('widget-save-next'))return;
 const content=$('content'),rows=[...content.querySelectorAll('.widget-proposal')];
 const style=document.createElement('style');
 style.textContent=`
 .widget-proposal.compact-widget{position:relative;padding:0 0 0 48px;margin-bottom:8px;border-radius:12px;box-shadow:none;min-width:0}
 .compact-widget > .widget-editor{margin:0}.compact-widget > .widget-editor > summary{display:flex;align-items:center;gap:12px;padding:12px;background:transparent;margin:0;list-style:none;min-height:72px}
 .widget-editor > summary::-webkit-details-marker{display:none}.widget-editor > summary::after{content:'Modifica';color:#9fc5ff;font-size:12px;margin-left:auto}
 .widget-editor[open] > summary::after{content:'Chiudi'}.widget-row-copy{min-width:0;flex:1}.widget-row-copy b{display:block;font-size:14px;overflow-wrap:anywhere}
 .widget-row-meta{display:block;font-size:12px;color:#a4bad4;margin-top:4px;overflow-wrap:anywhere}.widget-row-issue{color:#ffd18a}
 .widget-grip{position:absolute;top:14px;left:6px;width:38px;height:44px;padding:4px;touch-action:none;cursor:grab;font-size:20px;background:#1b3049}
 .widget-grip[aria-pressed=true]{border-color:#8abaff;background:#31548b}.widget-grip:focus-visible{outline:3px solid #8abaff;outline-offset:2px}
 .widget-edit-body{padding:0 12px 12px}.widget-edit-body .widget-name{min-width:0!important;width:100%}.widget-edit-body > .row > div{min-width:0;flex:1 1 260px}
 .widget-edit-body .widget-preview{margin:8px 0!important}.widget-preview .tile.smart{min-height:72px!important;max-width:420px!important;padding:10px 12px;flex-direction:row;gap:12px;align-items:center;box-shadow:none}
 .widget-preview .smart-top{flex-direction:column-reverse;gap:4px;flex:0 0 80px}.widget-preview .smart-icon{width:28px;height:28px;font-size:18px}.widget-preview .smart-state{font-size:14px!important;letter-spacing:0}.widget-preview .smart-name{font-size:13px}
 .widget-preview .smart-meta{margin-top:3px}.widget-preview .tile.smart > div{min-width:0}.widget-edit-body > p{font-size:12px}.widget-edit-body .tile{padding:12px}
 .widget-organizer{position:sticky;top:0;z-index:21;background:#102137;border:1px solid #436387;border-radius:12px;padding:10px;margin:12px 0}
 .widget-organizer .bar{margin:6px 0;gap:8px}.widget-organizer label{flex:1 1 230px;font-size:12px}.widget-organizer select{margin-top:4px}
 .widget-organizer p{margin:4px 0;font-size:12px;color:#b8cce6}.widget-room-drop{min-height:44px}.widget-drop-target{outline:3px solid #79c9ff;outline-offset:-3px;background:#21466b!important}
 .widget-drop-before{border-top:4px solid #79c9ff!important}.widget-drop-after{border-bottom:4px solid #79c9ff!important}.widget-dragging{opacity:.55}
 .widget-flow-actions{padding:9px;gap:8px;bottom:4px}.widget-flow-actions p{font-size:12px}.widget-flow-actions button{font-size:13px;padding:8px 10px;min-height:40px}
 .compact-evidence{margin:10px 0;padding:12px;border:1px solid #304963;border-radius:12px}.compact-evidence > summary{cursor:pointer}
 @media(max-width:600px){.widget-editor > summary::after{content:'＋';font-size:20px}.widget-editor[open] > summary::after{content:'−'}
 .widget-organizer .bar{display:grid;grid-template-columns:minmax(0,1fr) auto}.widget-organizer label{grid-column:1/-1}.widget-organizer button{font-size:13px;padding:8px}
 .widget-flow-actions{position:static}.widget-edit-body .grid{grid-template-columns:minmax(0,1fr)}.widget-row-meta{font-size:11px}}
 `;
 content.append(style);
 const recovery=$('recovery-panel');
 if(recovery){const details=document.createElement('details');details.className='compact-evidence';
  details.innerHTML='<summary>Confronto ETS e funzioni da recuperare</summary>';recovery.before(details);details.append(recovery);}
 const results=$('function-search-results');
 if(results){const details=document.createElement('details');details.className='compact-evidence';
  details.innerHTML='<summary>Indirizzi ETS e pulsanti di solo spegnimento</summary>';results.before(details);details.append(results);
  const note=details.nextElementSibling;if(note?.tagName==='P')details.append(note);}
 const organizer=document.createElement('section');organizer.className='widget-organizer';
 const rooms=[...new Set(['Da assegnare',...(structureDraft.length?structureRooms():widgetRooms)])];
 organizer.innerHTML=`<b>Ordina e sposta le funzioni</b><p>Trascina dalla maniglia ↕ per ordinare. Per cambiare stanza, scegli la destinazione e trascina su “Sposta qui”, oppure seleziona la maniglia e premi il pulsante.</p><div class="bar"><label>Stanza di destinazione<select id="widget-move-room"><option value="">Scegli una stanza…</option>${rooms.map(room=>`<option value="${escapeHTML(room)}">${escapeHTML(room)}</option>`).join('')}</select></label><button id="widget-room-drop" class="widget-room-drop" disabled>Sposta qui</button><button id="widget-move-undo" ${canRestoreWidgetPlacement(widgetDrafts,widgetPlacementUndo)?'':'disabled'}>Annulla spostamento</button></div><p id="widget-organizer-status" role="status" aria-live="polite"></p>`;
 if(rows.length)rows[0].before(organizer);else content.append(organizer);
 const destination=$('widget-move-room'),drop=$('widget-room-drop'),status=$('widget-organizer-status');
 destination.value=rooms.includes(compactDestinationRoom)?compactDestinationRoom:'';
 function announce(text){status.textContent=text;}
 function selectWidget(widget){
  compactSelectedWidget=widget;
  for(const row of rows)row.querySelector('.widget-grip')?.setAttribute('aria-pressed',String(widgetDrafts[Number(row.dataset.index)]===widget));
  drop.disabled=!widgetDrafts.includes(widget)||!destination.value;
  announce(widget?'Selezionata: '+widget.name+'. Le modifiche restano in bozza fino al salvataggio.':'Seleziona una funzione dalla maniglia ↕. Da tastiera: Alt + freccia su o giù per riordinare.');
 }
 function move(widget,to,room){
  const snapshot=rememberWidgetPlacement(widgetDrafts),from=widgetDrafts.indexOf(widget);
  if(room!==undefined&&!rooms.includes(room))return;
  if(!placeWidget(widgetDrafts,from,to,room))return;
  for(const item of snapshot)item.afterRoom=item.widget.room;
  widgetPlacementUndo=snapshot;widgetDirty=true;renderKeepingScroll();
  document.querySelector(`.widget-proposal[data-index="${widgetDrafts.indexOf(widget)}"] .widget-grip`)?.focus({preventScroll:true});
  const notice=room!==undefined?widget.name+' spostata in '+room:widget.name+' riordinata';
  $('widget-organizer-status').textContent=notice+'. Premi Salva bozza per conservare la modifica.';
 }
 destination.onchange=()=>{compactDestinationRoom=destination.value;drop.disabled=!widgetDrafts.includes(compactSelectedWidget)||!destination.value;};
 drop.onclick=()=>{if(compactSelectedWidget&&destination.value)move(compactSelectedWidget,widgetDrafts.indexOf(compactSelectedWidget),destination.value);};
 $('widget-move-undo').onclick=()=>{if(restoreWidgetPlacement(widgetDrafts,widgetPlacementUndo)){widgetPlacementUndo=null;widgetDirty=true;renderKeepingScroll();$('widget-organizer-status').textContent='Ultimo spostamento annullato. Salva bozza per conservare la modifica.';}};
 for(const row of rows){
  const widget=widgetDrafts[Number(row.dataset.index)],body=document.createElement('div');body.className='widget-edit-body';
  while(row.firstChild)body.append(row.firstChild);
  const details=document.createElement('details');details.className='widget-editor';
  const summary=document.createElement('summary');summary.innerHTML='<span class="widget-row-copy"><b></b><span class="widget-row-meta"></span></span>';
  const grip=document.createElement('button');grip.type='button';grip.className='widget-grip';grip.textContent='↕';
  function label(){
   summary.querySelector('b').textContent=widget.name||'Funzione senza nome';grip.setAttribute('aria-label','Sposta '+(widget.name||'funzione senza nome'));
   const missing=(widgetFields[widget.kind]||[]).filter(f=>f[3]&&!widget.fields[f[0]]).length;
   const meta=summary.querySelector('.widget-row-meta');meta.textContent=[widget.room||'Da assegnare',widget.fields.command||'Nessun GA',missing?'Da completare':null,widget.visible===false?'Nascosta':null].filter(Boolean).join(' · ');
   meta.classList.toggle('widget-row-issue',!!missing||widget.room==='Da assegnare');
  }
  details.append(summary,body);details.open=compactOpenWidgets.has(widget);
  details.ontoggle=()=>{if(details.open)compactOpenWidgets.add(widget);else compactOpenWidgets.delete(widget);};
  grip.title='Trascina per ordinare o spostare. Alt + ↑ / ↓ per riordinare.';
  grip.onclick=()=>selectWidget(widget);
  grip.onkeydown=e=>{
   if(e.altKey&&['ArrowUp','ArrowDown'].includes(e.key)){
    e.preventDefault();selectWidget(widget);
    const visible=rows.filter(r=>!r.hidden),position=visible.indexOf(row),target=visible[position+(e.key==='ArrowUp'?-1:1)];
    if(target)move(widget,Number(target.dataset.index));
   }
  };
  row.classList.add('compact-widget');row.append(grip,details);label();
  row.addEventListener('input',label);row.addEventListener('change',label);
  grip.onpointerdown=e=>{
   if(e.button!==0||!e.isPrimary)return;
   selectWidget(widget);grip.setPointerCapture(e.pointerId);
   const start={x:e.clientX,y:e.clientY};let dragging=false,target=null,after=false,frame=0,lastY=e.clientY,lastX=e.clientX;
   const clearTarget=()=>{content.querySelectorAll('.widget-drop-target,.widget-drop-before,.widget-drop-after').forEach(el=>el.classList.remove('widget-drop-target','widget-drop-before','widget-drop-after'));};
   const locate=(x,y)=>{
    clearTarget();target=null;
    const hit=document.elementFromPoint(x,y);
    if(hit?.closest('#widget-room-drop')&&destination.value){target=drop;drop.classList.add('widget-drop-target');return;}
    const candidate=hit?.closest('.widget-proposal');
    if(candidate&&candidate!==row&&!candidate.hidden){target=candidate;const box=target.getBoundingClientRect();after=y>box.top+box.height/2;target.classList.add(after?'widget-drop-after':'widget-drop-before');}
   };
   const scroll=()=>{if(!dragging)return;const delta=lastY<50?-12:lastY>window.innerHeight-60?12:0;
    if(delta){window.scrollBy(0,delta);locate(lastX,lastY);}frame=requestAnimationFrame(scroll);};
   grip.onpointermove=event=>{
    if(event.pointerId!==e.pointerId)return;
    lastX=event.clientX;lastY=event.clientY;
    if(!dragging&&Math.hypot(lastX-start.x,lastY-start.y)<7)return;
    event.preventDefault();if(!dragging){dragging=true;row.classList.add('widget-dragging');frame=requestAnimationFrame(scroll);}
    locate(lastX,lastY);
   };
   const finish=(event,cancelled=false)=>{
    if(event.pointerId!==e.pointerId)return;
    cancelAnimationFrame(frame);document.removeEventListener('keydown',escape);
    const picked=target;clearTarget();row.classList.remove('widget-dragging');
    grip.onpointermove=grip.onpointerup=grip.onpointercancel=grip.onlostpointercapture=null;
    if(grip.hasPointerCapture(e.pointerId))grip.releasePointerCapture(e.pointerId);
    if(cancelled||!dragging)return;
    grip.onclick=null;
    if(picked===drop)move(widget,widgetDrafts.indexOf(widget),destination.value);
    else if(picked){const from=widgetDrafts.indexOf(widget),index=Number(picked.dataset.index);move(widget,index+(after?1:0)-(from<index?1:0));}
    else announce('Nessuno spostamento. Rilascia su una funzione o sulla stanza scelta.');
    grip.onclick=()=>selectWidget(widget);
   };
   const escape=event=>{if(event.key==='Escape'){event.preventDefault();finish({pointerId:e.pointerId},true);}};
   document.addEventListener('keydown',escape);
   grip.onpointerup=event=>finish(event);grip.onpointercancel=event=>finish(event,true);grip.onlostpointercapture=event=>finish(event,true);
  };
 }
 selectWidget(widgetDrafts.includes(compactSelectedWidget)?compactSelectedWidget:null);
}

function wireInlineWidgetEditor(){
 if(!etsData)return;
 document.querySelectorAll('.widget-add').forEach(button=>button.onclick=()=>{
  if(widgetDrafts.length>=200)return message('Massimo 200 widget KNX',true);
  widgetDrafts.push(newWidget(button.dataset.kind));widgetDirty=true;revealWidgetEditor(widgetDrafts.length-1);
 });
 document.querySelectorAll('.widget-proposal').forEach(row=>{
  const index=Number(row.dataset.index),widget=widgetDrafts[index];
  const select=row.querySelector('.widget-room'),box=row.querySelector('.widget-custom-row');
  select.querySelector('option[value="__custom__"]').textContent='+ Crea stanza nell’edificio…';
  const parents=structureDraft.filter(n=>['building','floor'].includes(n.type)&&structureAncestorsActive(n.id));
  // Replace the legacy text-only custom room with a shared building node.
  const editor=document.createElement('div');editor.className='widget-custom-row';editor.hidden=true;
  editor.innerHTML=`${structureDraft.length?`<label>Edificio o piano<select class="new-room-parent"><option value="">Scegli collocazione…</option>${parents.map(n=>`<option value="${escapeHTML(n.id)}">${escapeHTML(nodePath(n.id))}</option>`).join('')}</select></label>`:'<label>Nome edificio<input class="new-room-building" maxlength="80" placeholder="Es. Negozio"></label>'}<label>Nome stanza<input class="new-room-name" maxlength="80" placeholder="Es. Ripostiglio"></label><div class="bar"><button class="new-room-create">Crea stanza e assegna</button><button class="new-room-cancel">Annulla</button></div><p class="small new-room-status" role="status">La stanza sarà disponibile anche in Edificio ETS e negli altri widget. Premi Salva bozza per conservarla.</p>`;
  box.replaceWith(editor);
  select.onchange=()=>{if(select.value==='__custom__'){editor.hidden=false;editor.querySelector('.new-room-name').focus();}else{editor.hidden=true;widget.room=select.value;widgetDirty=true;row.querySelector('.widget-room-status').textContent='Ambiente: '+widget.room;}};
  const parentSelect=editor.querySelector('.new-room-parent');
  if(parentSelect){const current=structureDraft.find(n=>n.type==='room'&&nodePath(n.id)===widget.room);parentSelect.value=current?.parent||(parents.length===1?parents[0].id:'');}
  editor.querySelector('.new-room-cancel').onclick=()=>{editor.hidden=true;select.value=widget.room;};
  editor.querySelector('.new-room-create').onclick=()=>{
   try{const path=createWidgetRoom(widget,editor.querySelector('.new-room-name').value,parentSelect?.value,editor.querySelector('.new-room-building')?.value||'');renderKeepingScroll();message('Stanza '+path+' creata e assegnata. Salva bozza per conservarla.');}
   catch(e){editor.querySelector('.new-room-status').textContent=e.message;}
  };
  row.querySelectorAll('.widget-ga').forEach(gaSelect=>{
   const manual=document.createElement('details');
   manual.innerHTML='<summary>Inserisci GA manualmente</summary><label>Indirizzo di gruppo<input class="manual-ga-value" placeholder="1/2/3" maxlength="8"></label><button class="manual-ga-assign">Associa GA</button><p class="small manual-ga-status" role="status">Salva l’associazione in NM Control. Il GA e i collegamenti ai dispositivi devono essere configurati anche in ETS; nessun telegramma viene inviato.</p>';
   gaSelect.after(manual);
   manual.querySelector('button').onclick=()=>{try{assignManualWidgetGA(widget,gaSelect.dataset.field,manual.querySelector('input').value);revealWidgetEditor(index);message('GA associato in bozza. Verifica DPT e collegamenti in ETS prima della creazione delle entità.');}catch(e){manual.querySelector('.manual-ga-status').textContent=e.message;}};
  });
 });
}
