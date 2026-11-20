// Saved installer sessions remain separate from HA/KNX approval.
let projectList=[];
function projectLibrary(){
 return `<section class="card"><div class="workspace-label">NM Control · Installazione</div><h2>Configura un impianto</h2><p>Importa ETS, controlla le funzioni riconosciute e installale in Home Assistant.</p><div class="bar"><button data-wizard-go="ets">1 · Importa ETS</button><button data-wizard-go="widgets">2 · Controlla</button><button data-wizard-go="real">3 · Installa</button></div><h3>Progetti salvati</h3>${projectList.map(p=>`<div class="row"><b>${escapeHTML(p.label)}</b><span>${p.functions} funzioni</span><button data-project-resume="${escapeHTML(p.project)}">Riprendi</button><button data-project-dashboard="${escapeHTML(p.project)}">Prepara plancia offline</button><button data-project-export="${escapeHTML(p.project)}">Scarica backup progetto</button></div>`).join('')||'<p>Importa il progetto ETS per iniziare.</p>'}<p id="project-library-status" aria-live="polite"></p></section>`;
}
async function loadProjectLibrary(){projectList=(await api('projects')).projects||[];}
function acceptProject(data){
 etsData=data;proposeWidgets();auditReviews={};reviewDirty=false;candidateDrafts=[];
 const existing=new Set(approvedDevices.map(d=>d.command));
 candidateDrafts=(data.suggestions||[]).filter(s=>!existing.has(s.command)).map(s=>({...s,selected:false}));
 etsError='Progetto pronto: '+data.total+' indirizzi. controlla le funzioni prima di installarle.';
}
function wireProjectLibrary(){
 document.querySelectorAll('[data-project-dashboard]').forEach(b=>b.onclick=async()=>{
  const status=$('project-library-status');
  b.disabled=true;
  status.textContent='Preparazione plancia…';
  try{await showEtsDashboard(b.dataset.projectDashboard,status);status.textContent='';}
  catch(error){status.textContent=error.message;}
  finally{b.disabled=false;}
 });
 document.querySelectorAll('[data-project-resume]').forEach(b=>b.onclick=async()=>{
  b.disabled=true;
  try{acceptProject(await api('projects/resume?project='+encodeURIComponent(b.dataset.projectResume)));setPage('ets');}
  catch(e){$('project-library-status').textContent=e.message;b.disabled=false;}
 });
 document.querySelectorAll('[data-project-export]').forEach(b=>b.onclick=async()=>{
  try{const data=await api('projects/export?project='+encodeURIComponent(b.dataset.projectExport));
   const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
   const a=document.createElement('a');a.href=url;a.download='nm-project-'+b.dataset.projectExport.slice(0,12)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){$('project-library-status').textContent=e.message;}
 });
}

async function showEtsDashboard(project, status){
 const draft=await api('projects/dashboard?climate=1&project='+encodeURIComponent(project));
 const counts=draft.summary;
 $('ets-dashboard-preview')?.remove();
 status.closest('.card').insertAdjacentHTML('afterend',`<section class="card" id="ets-dashboard-preview">
  <h2>Anteprima plancia offline</h2>
  <p>${counts.rooms} ambienti · ${counts.functions} funzioni · ${counts.climate} termostati · ${counts.gateways} interfacce tecniche</p>
  ${counts.shared?'<p class="warning">'+counts.shared+' unità clima condividono indirizzi ETS. Controlla i collegamenti prima di attivarle.</p>':''}
  <p>La bozza crea la navigazione per ambiente e funzione con schede «Da associare». Potrai modificarla in Home Assistant e aggiungere i comandi dopo aver collegato le entità.</p>
  <details><summary>Viste per ambiente</summary><ul>${draft.dashboard.views.filter(v=>v.path.startsWith('stanza-')).map(v=>`<li>${escapeHTML(v.title)}</li>`).join('')}</ul></details>
  <p>Percorso Home Assistant <code>/${escapeHTML(draft.url_path)}</code></p>
  <button id="ets-dashboard-publish" class="primary">Crea bozza in Home Assistant</button>
  <p id="ets-dashboard-status" role="status"></p>
  ${counts.climate ? etsClimateReview(draft.climate_plan) : ''}
 </section>`);
 const panel=$('ets-dashboard-preview'), postStatus=$('ets-dashboard-status');
 panel.scrollIntoView({block:'nearest'});
 if(counts.climate)wireEtsClimateReview(project,draft);
 $('ets-dashboard-publish').onclick=async event=>{
  const button=event.currentTarget;
  button.disabled=true;
  postStatus.textContent='Creazione plancia…';
  try{
   const result=await api('dashboard/publish',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({mode:'ets_draft',project,title:draft.title,url_path:draft.url_path,
     climate_popups:true,expected_fingerprint:draft.fingerprint,confirm:true})});
   postStatus.innerHTML=`Plancia creata. <a href="/${encodeURIComponent(result.url_path)}/panoramica" target="_top">Apri ${escapeHTML(result.title)}</a>`;
  }catch(error){postStatus.textContent=error.message;button.disabled=false;}
 };
}

function etsClimateReview(plan){
 const shortRoom=room=>room.split(' / ').at(-1);
 return `<h3>Associazioni clima e popup</h3>
 <p>${plan.associations.length} termostati Home Assistant proposti. Il file YAML resta da installare dopo il controllo dei collegamenti KNX.</p>
 ${plan.shared_groups.map(group=>`<details><summary>${escapeHTML(group.rooms.map(shortRoom).join(' / '))}
 · ${group.points.length} indirizzi condivisi</summary>
 <ul>${group.points.map(p=>`<li><code>${escapeHTML(p.address)}</code> · ${escapeHTML(p.label)}</li>`).join('')}</ul></details>`).join('')}
 <div class="bar">
  ${plan.associations.length?'<button id="ets-climate-yaml">Scarica bozza KNX</button><button id="ets-climate-json">Scarica associazioni e configurazioni card</button>':''}
  <button id="ets-climate-review">Anteprima aggiornamento popup</button>
  <button id="ets-climate-apply" hidden class="primary">Applica popup alla plancia</button>
 </div><p id="ets-climate-status" role="status"></p>`;
}

function wireEtsClimateReview(project,draft){
 const plan=draft.climate_plan, status=$('ets-climate-status'), apply=$('ets-climate-apply');
 const review=$('ets-climate-review');
 const request={mode:'ets_climate',project,url_path:draft.url_path};
 const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 function download(filename,content,type){
  const url=URL.createObjectURL(new Blob([content],{type}));
  const a=document.createElement('a');a.href=url;a.download=filename;a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 if(plan.associations.length){
  $('ets-climate-yaml').onclick=()=>download('nm-clima-'+project.slice(0,12)+'.yaml',plan.ha_yaml,'text/yaml');
  $('ets-climate-json').onclick=()=>{
   const {ha_yaml,...report}=plan;
   download('nm-clima-'+project.slice(0,12)+'.json',JSON.stringify(report,null,2),'application/json');
  };
 }
 review.onclick=async()=>{
  review.disabled=true;
  apply.hidden=true;
  status.textContent='Verifica plancia…';
  try{
   const diff=await post('dashboard/update-preview',request);
   if(!diff.changed){
    status.textContent='La plancia è già aggiornata o le schede sono state personalizzate in Home Assistant.';
    return;
   }
   status.textContent='Pronto ad aggiungere i popup in sola lettura. Verrà salvata una copia della plancia attuale.';
   apply.hidden=false;
   apply.onclick=async()=>{
    apply.disabled=true;
    review.disabled=true;
    try{
     const result=await post('dashboard/update',{...request,confirm:true,expected_current:diff.expected_current,
      expected_fingerprint:diff.expected_fingerprint});
     status.innerHTML=`Popup preparati. <a href="/${encodeURIComponent(result.url_path)}/panoramica" target="_top">Apri la plancia</a>`;
    }catch(error){status.textContent=error.message;}
    finally{apply.hidden=true;apply.disabled=false;review.disabled=false;}
   };
  }catch(error){status.textContent=error.message;}
  finally{review.disabled=false;}
 };
}

// Keep technical inspection available without mixing it with the guided flow.
function organizeInstallerPage(){
 const content=$('content'), lab=$('import-summary');
 if(!content||!lab)return;
 const importer=$('ets-progress').closest('.card');
 const advanced=document.createElement('details');advanced.className='card';
 const summary=document.createElement('summary');summary.textContent='Dettagli tecnici ETS e strumenti KNX';advanced.appendChild(summary);
 for(const child of [...content.children])if(child!==lab&&child!==importer)advanced.appendChild(child);
 const upload=document.createElement('details');upload.className='card';
 const title=document.createElement('summary');title.textContent='Importa un altro file / aggiorna il progetto';upload.appendChild(title);upload.appendChild(importer);
 content.appendChild(upload);content.appendChild(advanced);
}

// Real project import: persistence and review, without virtual provisioning.
function hvacUnitLabel(unit){
 const room=(unit.rooms||[]).map(path=>path.split(' / ').at(-1)).join(' / ');
 const name=unit.name==='Dispositivo'&&room?'':unit.name;
 return [name,room,unit.individual_address].filter(Boolean).join(' · ');
}

function hvacDevicePreview(units){
 if(!units?.length)return '';
 const climate=units.filter(unit=>unit.kind==='climate').length;
 const technical=units.length-climate;
 const shared=units.filter(unit=>unit.points.some(point=>point.shared_hvac)).length;
 const linked=units.filter(unit=>unit.points.length).length;
 const counts=[climate?climate+' KLIC di zona':'',technical?technical+' altre interfacce clima':''].filter(Boolean);
 return `<section aria-label="Climatizzazione ETS">
  <h3>Climatizzazione ETS</h3>
  <p>${escapeHTML(counts.join(' · '))} · ${linked} con indirizzi collegati</p>
  ${shared?`<p class="warning">${shared} unità condividono uno o più indirizzi. Verifica quali controlli devono funzionare insieme prima di associarle a Home Assistant.</p>`:''}
  <details><summary>Controlla comandi e stati per unità</summary>
  ${units.map(unit=>{
   const points=unit.points;
   const common=points.filter(point=>point.shared_hvac).length;
   const location=unit.rooms.length===1?unit.rooms[0]:unit.rooms.length?'Più posizioni ETS: '+unit.rooms.join(' · '):'Ambiente da assegnare';
   return `<details class="tile" style="margin-top:8px">
    <summary><b>${escapeHTML(hvacUnitLabel(unit))}</b> · ${escapeHTML(unit.model)} · ${points.length} indirizzi${common?` · <span class="warning">${common} condivisi</span>`:''}</summary>
    <p class="small muted">${escapeHTML(location)} · ${points.length?'Da associare':'Nessun indirizzo di gruppo collegato nel file ETS'}</p>
    ${points.length?`<div style="overflow-x:auto"><table><thead><tr><th>Funzione</th><th>Indirizzo e DPT</th><th>Collegamenti</th></tr></thead><tbody>
     ${points.map(point=>{
      const others=point.shared_with.map(hvacUnitLabel);
      const extra=point.peer_count-others.length;
      const availability=point.shared_hvac?'Condiviso con altre unità':point.peer_count?'Collegato anche a':'Individuale in ETS';
      return `<tr><td><b>${escapeHTML(point.label)}</b><div class="small muted">${escapeHTML(point.name)}</div></td>
       <td>${escapeHTML(point.address)}<div class="small muted">${escapeHTML(point.dpt||'DPT da verificare')}</div></td>
       <td class="${point.shared_hvac?'warning':''}">${availability}
       ${others.length?`<div class="small">${escapeHTML(others.join(' · '))}${extra>0?' · altri '+extra:''}</div>`:''}</td></tr>`;
     }).join('')}
    </tbody></table></div>`:''}</details>`;
  }).join('')}
  </details>
 </section>`;
}

function wireImportSummary(){
 const host=$('ets-progress')?.closest('.card');
 if(!host||!etsData)return;
 const counts={};for(const s of etsData.suggestions||[])counts[s.kind]=(counts[s.kind]||0)+1;
 host.insertAdjacentHTML('afterend',`<section class="card" id="import-summary"><h2>Progetto analizzato</h2><p>${escapeHTML(Object.entries(counts).map(([k,v])=>v+' '+({light:'luci',dimmer:'dimmer',cover:'tapparelle',climate:'clima'}[k]||k)).join(' · '))}</p><p>${etsRoomPaths().length} stanze ETS. Le proposte richiedono il controllo delle associazioni.</p>${hvacDevicePreview(etsData.hvac_units)}<label>Nome progetto<input id="project-label" maxlength="80" value="${escapeHTML(etsData.session_label||etsData.building?.find(n=>n.type==='Building')?.name||'Impianto')}"></label><div class="bar"><button id="project-continue" class="primary">Salva progetto e controlla le funzioni</button><button id="project-offline">Salva e prepara plancia offline</button></div><p id="import-status" role="status"></p></section>`);
 const continueButton=$('project-continue'), offlineButton=$('project-offline'), status=$('import-status');
 async function save(offline){
  continueButton.disabled=true;
  if(offlineButton)offlineButton.disabled=true;
  try{
   const label=$('project-label').value.trim();
   const keepSelection=offline&&Boolean(etsData.session_revision);
   const reviews=(etsData.lab_candidates||[]).map(d=>({...d,selected:keepSelection&&d.selected===true}));
   const result=await api('projects/save',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({confirm:true,token:etsData.session_token,expected_revision:etsData.session_revision||'',label,reviews})});
   etsData.session_revision=result.revision;etsData.session_label=label;
   await loadProjectLibrary();
   if(offline){await showEtsDashboard(result.project,status);status.textContent='Progetto salvato.';}
   else setPage('widgets');
  }catch(error){status.textContent=error.message;}
  finally{continueButton.disabled=false;if(offlineButton)offlineButton.disabled=false;}
 }
 continueButton.onclick=()=>save(false);
 if(offlineButton)offlineButton.onclick=()=>save(true);
}


// Explicit laboratory route: never provision virtual entities from the real import flow.
function labPage(){
 return '<section class="card"><h2>Laboratorio senza bus KNX</h2><p>Le entità virtuali sono separate dall’impianto reale. Importa o riprendi un progetto ETS prima di preparare i simulati.</p><p id="ets-progress" role="status"></p></section>';
}
async function wireLabPage(){
 if(!etsData){$('ets-progress').textContent='Nessun progetto aperto. Riprendi Sentire da Avvio guidato oppure importa ETS.';return;}
 try{
  if(typeof wireVirtualLab!=='function')await new Promise((resolve,reject)=>{
   const script=document.createElement('script');script.src='lab_ui.js';script.onload=resolve;script.onerror=()=>reject(Error('Caricamento laboratorio non riuscito'));document.head.append(script);
  });
  if(page==='lab')wireVirtualLab();
 }catch(error){if(page==='lab')$('ets-progress').textContent=error.message;}
}
