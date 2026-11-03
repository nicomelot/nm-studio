// Virtual-only wizard. No KNX provisioning or real widget assignments.
function wireVirtualLab(){
 const host=$('ets-progress')?.closest('.card');
 if(!host)return;
 const candidates=etsData.lab_candidates||[];
 const labels={light:'Luce',dimmer:'Dimmer',cover:'Tapparella',scene:'Richiamo scena',sensor:'Sensore numerico',binary_sensor:'Sensore binario',climate:'Termostato'};
 const roomNames=[...new Set(['Da assegnare',...candidates.map(d=>d.room),...(etsData.building||[]).map(d=>d.path)])];
 host.insertAdjacentHTML('afterend',`<section class="card" id="lab-wizard"><div class="workspace-label">NM Studio 5.10.1 - Laboratorio virtuale</div><h2>Configura e prova il progetto</h2><p>${candidates.length} funzioni proposte. Non servono termostati. Seleziona fino a 200 funzioni e verifica le stanze. Scegli un ambiente dal menu oppure scrivi il nome nel campo sottostante. Gli abbinamenti proposti vanno verificati.</p><p class="warning">Solo simulazione: tapparelle a posizione istantanea; scene con registrazione del richiamo; sensori modificabili manualmente. Nessun collegamento KNX.</p><div class="bar"><label>Nome progetto <input id="project-label" maxlength="80" value="${escapeHTML(etsData.session_label||'')}" placeholder="Es. Beppe Vello"></label><button id="project-save">Salva progetto e revisione</button></div><p class="small">${etsData.session_changes?`${etsData.session_changes.added.length} nuove · ${etsData.session_changes.changed.length} modificate · ${etsData.session_changes.removed.length} rimosse`:''}. Le funzioni modificate e nuove in una reimportazione richiedono una nuova selezione. Le rimosse non vengono cancellate da HA.</p>${etsData.session_changes?.removed.length?`<p class="warning">GA rimossi: ${etsData.session_changes.removed.map(escapeHTML).join(', ')}</p>`:''}<div class="bar"><label>Passaggio <select id="lab-stage"><option value="review">1. Ambienti e funzioni</option><option value="install">2. Installazione LAB</option><option value="publish">3. Verifica e dashboard</option></select></label><button id="lab-real-path">Preparazione impianto reale</button></div><div data-lab-stage="review"><div class="bar"><input id="lab-filter" placeholder="Cerca nome, stanza o GA" aria-label="Filtra funzioni"><select id="lab-kind-filter"><option value="">Tutte le categorie</option>${Object.entries(labels).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div><div style="max-height:420px;overflow:auto"><table><thead><tr><th>Usa</th><th>Funzione</th><th>Tipo virtuale</th><th>Stanza</th></tr></thead><tbody>${candidates.map((d,i)=>`<tr><td><input class="lab-selected" data-index="${i}" type="checkbox" ${(d.selected===true||(d.selected!==false&&i<200))?'checked':''} aria-label="Simula ${escapeHTML(d.name)}"></td><td><input class="lab-name" aria-label="Nome funzione" maxlength="80" value="${escapeHTML(d.name)}"> (${escapeHTML(d.command)})${etsData.session_changes?.changed.includes(d.command)?'<span class="warning"> Modificata: verifica</span>':etsData.session_changes?.added.includes(d.command)?'<span class="muted"> Nuova</span>':''}${d.room_source?`<div class="small warning">${escapeHTML(d.room_source)}</div>`:""}</td><td><select class="lab-kind" data-index="${i}" aria-label="Tipo virtuale">${Object.entries(labels).map(([key,label])=>`<option value="${key}" ${key===d.kind?'selected':''}>${label}</option>`).join('')}</select></td><td><select class="lab-room-choice" aria-label="Scegli ambiente ETS"><option value="">Scegli ambiente ETS…</option>${roomNames.filter(Boolean).map(r=>`<option value="${escapeHTML(r)}">${escapeHTML(r)}</option>`).join('')}</select><input class="lab-room" data-index="${i}" list="lab-rooms" maxlength="240" aria-label="Stanza" value="${escapeHTML(d.room)}"></td></tr>`).join('')}</tbody></table></div></div><datalist id="lab-rooms">${roomNames.map(r=>`<option value="${escapeHTML(r)}"></option>`).join('')}</datalist>${candidates.length?'':'<p class="warning">Nessuna funzione riconosciuta per il laboratorio. Controlla nomi, DPT e collegamenti del progetto ETS.</p>'}<div class="bar"><span data-lab-stage="install"><button id="lab-check" class="primary" ${candidates.length?'':'disabled'}>1. Verifica laboratorio</button><button id="lab-setup" disabled>2. Abilita pacchetti HA</button><button id="lab-install" disabled>3. Installa entità virtuali</button></span><span data-lab-stage="publish"><button id="lab-dashboard-check">4. Verifica entità dopo riavvio HA</button><button id="lab-dashboard-publish" disabled>5. Crea NM Control LAB v2</button></span></div><p id="lab-status" class="small muted">Nessuna modifica eseguita. Le proposte virtuali non approvano il progetto KNX reale.</p></section>`);
 let plan=null,setup=null,dashboard=null,existingDashboard=null,busy=false;
 const status=text=>$('lab-status').textContent=text;
 const post=(path,data)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 function base(){
  const devices=[...document.querySelectorAll('#lab-wizard .lab-selected:checked')].map(el=>{
   const i=Number(el.dataset.index), row=el.closest('tr');
   return {...candidates[i],name:row.querySelector('.lab-name').value.trim(),kind:row.querySelector('.lab-kind').value,room:row.querySelector('.lab-room').value.trim()||'Da assegnare'};
  });
  if(!devices.length||devices.length>200)throw Error('Seleziona da 1 a 200 funzioni');
  return {mode:'virtual_devices',project:etsData.project_key,devices};
 }
 function capture(){
  document.querySelectorAll('#lab-wizard .lab-selected').forEach(el=>{
   const d=candidates[Number(el.dataset.index)],row=el.closest('tr');
   d.selected=el.checked;d.name=row.querySelector('.lab-name').value.trim();d.kind=row.querySelector('.lab-kind').value;d.room=row.querySelector('.lab-room').value.trim()||'Da assegnare';
  });
 }
 function stage(){document.querySelectorAll('[data-lab-stage]').forEach(el=>el.hidden=el.dataset.labStage!==$('lab-stage').value);}
 $('lab-stage').onchange=stage;stage();
 $('lab-real-path').onclick=()=>{capture();setPage('building');};
 function filter(){const q=$('lab-filter').value.toLowerCase(),kind=$('lab-kind-filter').value;document.querySelectorAll('#lab-wizard .lab-selected').forEach(el=>{const row=el.closest('tr');const text=[row.querySelector('.lab-name').value,row.querySelector('.lab-room').value,candidates[Number(el.dataset.index)].command].join(' ').toLowerCase();row.hidden=!text.includes(q)||(kind&&row.querySelector('.lab-kind').value!==kind);});}
 $('lab-filter').onkeyup=filter;$('lab-kind-filter').onchange=filter;
 $('project-save').onclick=()=>run(async()=>{
  capture();const result=await post('projects/save',{confirm:true,token:etsData.session_token,expected_revision:etsData.session_revision||'',label:$('project-label').value,reviews:candidates.map(d=>({...d,selected:d.selected===true}))});
  etsData.session_revision=result.revision;etsData.session_label=$('project-label').value;
  status('Progetto e revisioni salvati. Puoi riprendere da Avvio guidato anche dopo un riavvio.');
  await loadProjectLibrary();$('lab-stage').value='install';stage();
 });
 function invalidate(){plan=null;setup=null;dashboard=null;existingDashboard=null;['lab-install','lab-setup','lab-dashboard-publish'].forEach(id=>$(id).disabled=true);}
 document.querySelectorAll('#lab-wizard input,#lab-wizard select').forEach(el=>el.oninput=()=>{capture();invalidate();status('Selezione modificata: ripeti la verifica.');});
 document.querySelectorAll('#lab-wizard .lab-room-choice').forEach(el=>el.onchange=()=>{
  if(!el.value)return;
  el.closest('tr').querySelector('.lab-room').value=el.value;
  capture();invalidate();status('Ambiente modificato: ripeti la verifica.');
 });
 async function run(work){
  if(busy)return;busy=true;
  document.querySelectorAll('#lab-wizard input,#lab-wizard select').forEach(el=>el.disabled=true);
  try{await work();}catch(e){invalidate();status('Operazione non completata: '+e.message);}finally{busy=false;document.querySelectorAll('#lab-wizard input,#lab-wizard select').forEach(el=>el.disabled=false);}
 }
 $('lab-check').onclick=()=>run(async()=>{
  invalidate();plan=await post('lab/preview',base());
  status((plan.packages_enabled?'Pacchetti HA abilitati. ':'Pacchetti HA da abilitare. ')+(plan.blocked_by_existing?(plan.replaceable?'Package LAB differente: puoi sostituirlo con backup e conferma. ':'File esistente non riconosciuto: sostituzione bloccata. '):plan.already_installed?'Package già installato. Verifica le entità dopo il riavvio HA. ':`${plan.devices} funzioni pronte per l’installazione. `)+plan.message);
  $('lab-install').textContent=plan.blocked_by_existing?'3. Sostituisci laboratorio con backup':'3. Installa entità virtuali';
  $('lab-install').disabled=!plan.ready||(plan.blocked_by_existing&&!plan.replaceable)||plan.already_installed;
  if(!plan.packages_enabled){setup=await post('lab/packages-preview',{});$('lab-setup').disabled=!setup.ready||setup.already_enabled;}
 });
 $('lab-setup').onclick=()=>run(async()=>{
  if(!setup?.expected_sha256)return;
  if(!confirm(setup.preview+'\n\nVerrà creato un backup di configuration.yaml. Autorizzi la modifica?'))return;
  await post('lab/packages-enable',{confirm:true,expected_sha256:setup.expected_sha256});
  invalidate();status('Pacchetti abilitati con backup. Ripeti Verifica laboratorio e installa le entità, poi verifica la configurazione e riavvia HA.');
 });
 $('lab-install').onclick=()=>run(async()=>{
  if(!plan?.ready)return;
  const replacing=plan.blocked_by_existing;
  if(!confirm(`${replacing?'Sostituire il precedente laboratorio (verrà salvato un backup) con':'Installare'} ${plan.devices} funzioni virtuali in ${plan.target}? ${replacing?'Le vecchie entità LAB non saranno più fornite dal package dopo il riavvio; le vecchie dashboard LAB restano da rimuovere da HA. ':''}Dopo l’installazione verifica la configurazione e riavvia HA.`))return;
  await post(replacing?'lab/replace':'lab/install',{...base(),confirm:true,expected_sha256:plan.sha256,replace_confirmed:replacing,expected_existing_sha256:plan.existing_sha256});
  invalidate();status('Package installato. In Home Assistant verifica la configurazione e riavvia. Poi torna qui e premi Verifica entità dopo riavvio HA. Se hai salvato la revisione, riapri il progetto da Avvio guidato; altrimenti reimporta ETS.');
 });
 $('lab-dashboard-check').onclick=()=>run(async()=>{
  dashboard=null;$('lab-dashboard-publish').disabled=true;
  dashboard=await post('lab/dashboard-preview',base());
  status(`${dashboard.summary.tiles} entità virtuali disponibili; ${dashboard.warnings.length} mancanti. `+dashboard.warnings.slice(0,4).map(w=>w.entity_id).join(', '));
  existingDashboard=await post('lab/dashboard-existing',base());
  $('lab-dashboard-publish').textContent=existingDashboard.exists?'5. Aggiorna NM Control LAB con backup':'5. Crea NM Control LAB v2';
  $('lab-dashboard-publish').disabled=!dashboard.summary.tiles||!!dashboard.warnings.length;
 });
 $('lab-dashboard-publish').onclick=()=>run(async()=>{
  if(!dashboard||!existingDashboard||!confirm(existingDashboard.exists?'Aggiornare la dashboard LAB? Eventuali personalizzazioni della dashboard saranno sostituite. Viene salvato un backup.':'Creare una nuova dashboard NM Control LAB con sole entità virtuali?'))return;
  const result=await post(existingDashboard.exists?'lab/dashboard-update':'lab/dashboard-publish',{...base(),confirm:true,expected_fingerprint:dashboard.fingerprint,expected_existing_fingerprint:existingDashboard.fingerprint});
  $('lab-dashboard-publish').disabled=true;status((result.updated?'Dashboard aggiornata con backup. ':'Dashboard creata. ')+'Apri NM Control LAB dalla barra laterale di Home Assistant. Percorso: /'+result.url_path);
 });
}
