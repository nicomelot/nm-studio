// Compare the imported evidence with the current draft; never modify existing widgets.
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
  const signatures=new Set(list.map(s=>JSON.stringify([s.kind,...['feedback','relative','stop','brightness','brightness_feedback','position','temperature','target_temperature_state','heat_cool','heat_cool_state','operation_mode','operation_mode_state'].map(k=>s[k]||'')])));
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
  automatic?'Recuperata da ETS · verifica comando e feedback':'Aggiunta manuale da indirizzo ETS · verifica funzione e DPT',
  known.includes(room)?room:'Da assegnare'));
 widgetDirty=true;
 return true;
}

function recoveryPanel(){
 if(!etsData)return '';
 const report=recoveryReport(etsData,widgetDrafts);
 const row=(s,manual=false)=>`<div class="row recovery-row" data-search="${escapeHTML((s.name+' '+(s.command||s.address)).toLowerCase())}" style="margin:8px 0"><div class="grow"><b>${escapeHTML(s.name)}</b><p class="small muted">${escapeHTML(s.command||s.address)} · ${escapeHTML(s.kind||s.dpt||'Tipo da verificare')}${!s.linked?' · Nessun collegamento ETS rilevato':''}${s.shared?' · Indirizzo già usato in un altro campo':''}${s.ambiguous?' · Proposte discordanti':''}</p></div>${!manual&&!s.ambiguous&&!s.shared&&s.linked?`<button data-recover="${escapeHTML(s.command)}" data-kind="${s.kind}">Aggiungi alla bozza</button>`:`<select class="recovery-kind" aria-label="Tipo funzione per ${escapeHTML(s.name)}" style="max-width:180px"><option value="">Scegli tipo…</option><option value="light">Luce</option><option value="dimmer">Dimmer</option><option value="cover">Tapparella</option><option value="climate">Termostato</option></select><button data-recover-manual="${escapeHTML(s.command||s.address)}">Prepara manualmente</button>`}</div>`;
 return `<section class="card" id="recovery-panel"><div class="workspace-label">Confronto con il progetto ETS aperto</div><h2>Recupera funzioni mancanti</h2><p>${report.missing.length} proposte assenti dalla bozza · ${report.other.length} altri indirizzi da esaminare. Gli indirizzi possono essere comandi, feedback o funzioni ausiliarie: non corrispondono necessariamente a dispositivi mancanti.</p><input id="recovery-search" placeholder="Cerca L5, nome o indirizzo di gruppo" aria-label="Cerca funzioni mancanti"><div style="max-height:360px;overflow:auto">${report.missing.map(s=>row(s)).join('')||'<p>Nessuna proposta riconosciuta da aggiungere.</p>'}<details><summary>Altri indirizzi ETS (${report.other.length})</summary>${report.other.map(a=>row(a,true)).join('')}</details></div>${report.stale.length?`<p class="warning">${report.stale.length} widget hanno un comando assente dal progetto importato: ${report.stale.map(w=>escapeHTML(w.name+' ('+w.fields.command+')')).join(', ')}. Sono stati conservati: verifica prima di modificarli.</p>`:''}<p class="small muted">Aggiungere prepara una bozza senza entità HA. Controlla tipo, indirizzi e stanza, poi salva. Le associazioni esistenti vengono conservate.</p><p id="recovery-status" aria-live="polite"></p></section>`;
}

function wireRecovery(){
 if(!$('recovery-panel'))return;
 $('recovery-search').oninput=e=>document.querySelectorAll('.recovery-row').forEach(row=>{
  row.hidden=!row.dataset.search.includes(e.target.value.trim().toLowerCase());row.style.display=row.hidden?'none':'';
  if(e.target.value&&row.closest('details'))row.closest('details').open=true;
 });
 document.querySelectorAll('[data-recover]').forEach(b=>b.onclick=()=>{
  if(addRecoveredWidget(b.dataset.recover,b.dataset.kind)){render();message('Funzione aggiunta alla bozza. Verifica e salva.');}
 });
 document.querySelectorAll('[data-recover-manual]').forEach(b=>b.onclick=()=>{
  const kind=b.closest('.recovery-row').querySelector('.recovery-kind').value;
  if(!kind){$('recovery-status').textContent='Scegli il tipo di funzione da preparare.';return;}
  if(addRecoveredWidget(b.dataset.recoverManual,kind,false)){render();message('Bozza manuale aggiunta. Verifica che il GA sia il comando della funzione.');}
 });
}

function realFlowBar(){
 const steps=[['ets','1 · Importa ETS'],['widgets','2 · Funzioni e stanze'],['matches','3 · Associa esistenti'],['real','4 · Crea mancanti'],['dashboard-export','5 · Pubblica']];
 return `<section class="card"><b>Percorso impianto reale</b><div class="bar" style="margin-top:12px">${steps.map(([p,label])=>`<button data-real-flow="${p}" ${p===page?'class="primary" aria-current="step"':''}>${label}</button>`).join('')}</div><p class="small muted">Se le entità esistono già, dopo le associazioni puoi passare alla pubblicazione. Il laboratorio virtuale è una prova separata.</p></section>`;
}
