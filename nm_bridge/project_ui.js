// Saved installer sessions remain separate from HA/KNX approval.
let projectList=[];
function projectLibrary(){
 return `<section class="card"><div class="workspace-label">NM Control · Installazione</div><h2>Configura un impianto</h2><p>Importa ETS, controlla le funzioni riconosciute e installale in Home Assistant.</p><div class="bar"><button data-wizard-go="ets">1 · Importa ETS</button><button data-wizard-go="widgets">2 · Controlla</button><button data-wizard-go="real">3 · Installa</button></div><h3>Progetti salvati</h3>${projectList.map(p=>`<div class="row"><b>${escapeHTML(p.label)}</b><span>${p.functions} funzioni</span><button data-project-resume="${escapeHTML(p.project)}">Riprendi</button><button data-project-export="${escapeHTML(p.project)}">Scarica backup progetto</button></div>`).join('')||'<p>Importa il progetto ETS per iniziare.</p>'}<p id="project-library-status" aria-live="polite"></p></section>`;
}
async function loadProjectLibrary(){projectList=(await api('projects')).projects||[];}
function acceptProject(data){
 etsData=data;proposeWidgets();auditReviews={};reviewDirty=false;candidateDrafts=[];
 const existing=new Set(approvedDevices.map(d=>d.command));
 candidateDrafts=(data.suggestions||[]).filter(s=>!existing.has(s.command)).map(s=>({...s,selected:false}));
 etsError='Progetto pronto: '+data.total+' indirizzi. controlla le funzioni prima di installarle.';
}
function wireProjectLibrary(){
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
 host.insertAdjacentHTML('afterend',`<section class="card" id="import-summary"><h2>Progetto analizzato</h2><p>${escapeHTML(Object.entries(counts).map(([k,v])=>v+' '+({light:'luci',dimmer:'dimmer',cover:'tapparelle',climate:'clima'}[k]||k)).join(' · '))}</p><p>${etsRoomPaths().length} stanze ETS. Le proposte richiedono il controllo delle associazioni.</p>${hvacDevicePreview(etsData.hvac_units)}<label>Nome progetto<input id="project-label" maxlength="80" value="${escapeHTML(etsData.session_label||etsData.building?.find(n=>n.type==='Building')?.name||'Impianto')}"></label><button id="project-continue" class="primary">Salva progetto e controlla le funzioni</button><p id="import-status" role="status"></p></section>`);
 $('project-continue').onclick=async()=>{
  const b=$('project-continue');b.disabled=true;
  try{
   const label=$('project-label').value.trim();
   const result=await api('projects/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true,token:etsData.session_token,expected_revision:etsData.session_revision||'',label,reviews:(etsData.lab_candidates||[]).map(d=>({...d,selected:false}))})});
   etsData.session_revision=result.revision;etsData.session_label=label;
   await loadProjectLibrary();setPage('widgets');
  }catch(e){$('import-status').textContent=e.message;b.disabled=false;}
 };
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
