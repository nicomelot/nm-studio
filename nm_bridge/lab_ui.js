// Virtual-only wizard. No KNX provisioning or real widget assignments.
function wireVirtualLab(){
 const host=$('ets-progress')?.closest('.card');
 if(!host)return;
 const candidates=etsData.lab_candidates||[];
 const labels={light:'Luce',dimmer:'Dimmer',cover:'Tapparella',scene:'Richiamo scena',sensor:'Sensore numerico',binary_sensor:'Sensore binario',climate:'Termostato'};
 const roomNames=[...new Set(['Da assegnare',...candidates.map(d=>d.room),...(etsData.building||[]).filter(d=>['Room','Corridor','Stairway'].includes(d.type)).map(d=>d.path)])];
 host.insertAdjacentHTML('afterend',`<section class="card" id="lab-wizard"><div class="workspace-label">NM Studio 5.9.4 - Laboratorio virtuale</div><h2>Prepara Home Assistant di test</h2><p>${candidates.length} funzioni proposte. Non servono termostati. Seleziona fino a 200 funzioni e verifica le stanze. Scegli un ambiente dal menu oppure scrivi il nome nel campo sottostante. Gli abbinamenti proposti vanno verificati.</p><p class="warning">Solo simulazione: tapparelle a posizione istantanea; scene con registrazione del richiamo; sensori modificabili manualmente. Nessun collegamento KNX.</p><div style="max-height:320px;overflow:auto"><table><thead><tr><th>Usa</th><th>Funzione</th><th>Tipo virtuale</th><th>Stanza</th></tr></thead><tbody>${candidates.map((d,i)=>`<tr><td><input class="lab-selected" data-index="${i}" type="checkbox" ${i<200?'checked':''} aria-label="Simula ${escapeHTML(d.name)}"></td><td>${escapeHTML(d.name)} (${escapeHTML(d.command)})</td><td><select class="lab-kind" data-index="${i}" aria-label="Tipo virtuale">${Object.entries(labels).map(([key,label])=>`<option value="${key}" ${key===d.kind?'selected':''}>${label}</option>`).join('')}</select></td><td><select class="lab-room-choice" aria-label="Scegli ambiente ETS"><option value="">Scegli ambiente ETS…</option>${roomNames.filter(Boolean).map(r=>`<option value="${escapeHTML(r)}">${escapeHTML(r)}</option>`).join('')}</select><input class="lab-room" data-index="${i}" list="lab-rooms" maxlength="240" aria-label="Stanza" value="${escapeHTML(d.room)}"></td></tr>`).join('')}</tbody></table></div><datalist id="lab-rooms">${roomNames.map(r=>`<option value="${escapeHTML(r)}"></option>`).join('')}</datalist>${candidates.length?'':'<p class="warning">Nessuna funzione riconosciuta per il laboratorio. Controlla nomi, DPT e collegamenti del progetto ETS.</p>'}<div class="bar"><button id="lab-check" class="primary" ${candidates.length?'':'disabled'}>1. Verifica laboratorio</button><button id="lab-setup" disabled>2. Abilita pacchetti HA</button><button id="lab-install" disabled>3. Installa entità virtuali</button><button id="lab-dashboard-check">4. Verifica entità dopo riavvio HA</button><button id="lab-dashboard-publish" disabled>5. Crea NM Control LAB</button></div><p id="lab-status" class="small muted">Nessuna modifica eseguita. Le proposte virtuali non approvano il progetto KNX reale.</p></section>`);
 let plan=null,setup=null,dashboard=null,busy=false;
 const status=text=>$('lab-status').textContent=text;
 const post=(path,data)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 function base(){
  const devices=[...document.querySelectorAll('#lab-wizard .lab-selected:checked')].map(el=>{
   const i=Number(el.dataset.index), row=el.closest('tr');
   return {...candidates[i],kind:row.querySelector('.lab-kind').value,room:row.querySelector('.lab-room').value.trim()||'Da assegnare'};
  });
  if(!devices.length||devices.length>200)throw Error('Seleziona da 1 a 200 funzioni');
  return {mode:'virtual_devices',project:etsData.project_key,devices};
 }
 function invalidate(){plan=null;setup=null;dashboard=null;['lab-install','lab-setup','lab-dashboard-publish'].forEach(id=>$(id).disabled=true);}
 document.querySelectorAll('#lab-wizard input,#lab-wizard select').forEach(el=>el.oninput=()=>{invalidate();status('Selezione modificata: ripeti la verifica.');});
 document.querySelectorAll('#lab-wizard .lab-room-choice').forEach(el=>el.onchange=()=>{
  if(!el.value)return;
  el.closest('tr').querySelector('.lab-room').value=el.value;
  invalidate();status('Ambiente modificato: ripeti la verifica.');
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
  invalidate();status('Package installato. In Home Assistant verifica la configurazione e riavvia. Poi torna qui e premi Verifica entità dopo riavvio HA. Se ricarichi NM Studio, reimporta lo stesso ETS e riseleziona le stesse funzioni.');
 });
 $('lab-dashboard-check').onclick=()=>run(async()=>{
  dashboard=null;$('lab-dashboard-publish').disabled=true;
  dashboard=await post('lab/dashboard-preview',base());
  status(`${dashboard.summary.tiles} entità virtuali disponibili; ${dashboard.warnings.length} mancanti. `+dashboard.warnings.slice(0,4).map(w=>w.entity_id).join(', '));
  $('lab-dashboard-publish').disabled=!dashboard.summary.tiles||!!dashboard.warnings.length;
 });
 $('lab-dashboard-publish').onclick=()=>run(async()=>{
  if(!dashboard||!confirm('Creare una nuova dashboard NM Control LAB con sole entità virtuali?'))return;
  const result=await post('lab/dashboard-publish',{...base(),confirm:true,expected_fingerprint:dashboard.fingerprint});
  $('lab-dashboard-publish').disabled=true;status('Dashboard creata: apri NM Control LAB dalla barra laterale di Home Assistant. Percorso: /'+result.url_path);
 });
}
