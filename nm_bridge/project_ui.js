// Saved installer sessions remain separate from HA/KNX approval.
let projectList=[];
function projectLibrary(){
 return `<section class="card"><div class="workspace-label">NM Studio 5.11.0</div><h2>Configura un impianto</h2><p>Crea e prova la supervisione in laboratorio. Per configurare il KNX reale apri il percorso dedicato qui sotto.</p><div class="installer-steps"><span>1 · Importa ETS</span><span>2 · Rivedi stanze e funzioni</span><span>3 · Installa e verifica</span><span>4 · Apri la supervisione</span></div><div class="bar"><button data-wizard-go="ets" class="primary">${etsData?'Continua il progetto aperto':'Inizia: importa ETS'}</button><button data-wizard-go="floorplans">Apri planimetrie</button></div><h3>Progetti salvati</h3><p class="small muted">Le revisioni sono salvate in NM Studio. Non creano Aree HA e non approvano i comandi KNX.</p>${projectList.map(p=>`<div class="row"><b>${escapeHTML(p.label)}</b><span>${p.functions} funzioni</span><button data-project-resume="${escapeHTML(p.project)}">Riprendi</button><button data-project-export="${escapeHTML(p.project)}">Scarica backup progetto</button></div>`).join('')||'<p>Nessun progetto salvato. Dopo l’importazione premi Salva progetto e revisione.</p>'}<p id="project-library-status" aria-live="polite"></p></section>`;
}
async function loadProjectLibrary(){projectList=(await api('projects')).projects||[];}
function acceptProject(data){
 etsData=data;proposeWidgets();auditReviews={};reviewDirty=false;candidateDrafts=[];
 const existing=new Set(approvedDevices.map(d=>d.command));
 candidateDrafts=(data.suggestions||[]).filter(s=>!existing.has(s.command)).map(s=>({...s,selected:false}));
 etsError='Progetto pronto: '+data.total+' indirizzi. Revisioni LAB ripristinate; verifica separatamente i widget reali.';
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
 const content=$('content'), lab=$('lab-wizard');
 if(!content||!lab)return;
 const importer=$('ets-progress').closest('.card');
 const advanced=document.createElement('details');advanced.className='card';
 const summary=document.createElement('summary');summary.textContent='Dettagli tecnici ETS e strumenti KNX';advanced.appendChild(summary);
 for(const child of [...content.children])if(child!==lab&&child!==importer)advanced.appendChild(child);
 const upload=document.createElement('details');upload.className='card';
 const title=document.createElement('summary');title.textContent='Importa un altro file / aggiorna il progetto';upload.appendChild(title);upload.appendChild(importer);
 content.appendChild(upload);content.appendChild(advanced);
}
