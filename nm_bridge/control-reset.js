'use strict';
let resetReview=null,resetBackup=null,resetDownloaded=false;
function resetList(items){return `<ul>${items.map(v=>`<li>${esc(v)}</li>`).join('')}</ul>`;}
async function resetPreview(selected=[]){
 resetBackup=null;resetDownloaded=false;
 resetReview=await api('control/reset',{operation:'preview',project:snapshot.project,legacy_dashboards:selected});
 const r=resetReview;
 modal('Azzera progetto NM · Anteprima',`<p>Progetto <strong>${esc(r.project.slice(0,12))}</strong>. Verranno cancellati importazione, associazioni e configurazioni NM elencate qui sotto. Le personalizzazioni delle pagine eliminate saranno nel backup.</p>
 <h3>Archivi del progetto (${r.files.length})</h3>${resetList(r.files)}
 <h3>Home Assistant</h3>${resetList(r.dashboards.map(d=>`${d.action}: ${d.title||d.path} (${d.path})`))}
 <details><summary>${r.helpers.length} aiutanti: settimane, ferie, preferiti e ordine</summary>${resetList(r.helpers)}</details>
 ${r.candidates.length?`<h3>Pagine NM da attribuire</h3><p>Queste pagine non contengono un’identità certa del progetto. Se appartengono a questa importazione, selezionale e aggiorna l’anteprima.</p>${r.candidates.map(d=>`<label class="check"><input type="checkbox" name="reset-legacy" value="${esc(d.path)}" ${selected.includes(d.path)?'checked':''}>${esc(d.title)} · ${esc(d.path)}</label>`).join('')}<button data-reset-preview="1">Aggiorna anteprima</button>`:''}
 <h3>Rimangono presenti</h3>${resetList(r.preserved)}
 ${r.restart_required?'<p>Il package dei simulati sarà rimosso. Servirà un riavvio manuale di Home Assistant per scaricare le entità YAML; non verrà eseguito da questo pulsante.</p>':''}
 ${r.blockers.length?`<div class="notice error">${resetList(r.blockers)}</div>`:''}
 <p>Prima della cancellazione creeremo un backup verificato da scaricare. Il backup NM consente un ripristino assistito; non sostituisce il backup completo di Home Assistant.</p>`,r.blockers.length?'':'<button data-reset-backup="1" class="primary">Crea backup</button>');
}
function resetConfirm(){
 const r=resetBackup;
 modal('Backup pronto · Conferma azzeramento',`<p>Backup salvato nell’add-on e verificato. Scaricalo prima di continuare.</p><button data-reset-download="1">Scarica backup NM</button><p id="reset-download-status" role="status">${resetDownloaded?'Backup scaricato.':'Download ancora da eseguire.'}</p><details><summary>Impronta del backup</summary><code>${esc(r.sha256)}</code></details><p>Per confermare scrivi <strong>${esc(r.phrase)}</strong>.</p><label>Conferma scritta<input id="reset-phrase" autocomplete="off" spellcheck="false"></label><label class="check"><input type="checkbox" id="reset-consent">Ho letto l’anteprima e voglio cancellare le configurazioni elencate.</label><p>Il reset non invia comandi ai dispositivi. In caso di errore si interrompe e conserva il backup, senza dichiarare completata la cancellazione.</p>`,`<button data-reset-apply="1" style="background:#8c2732;color:white">Azzera definitivamente il progetto NM</button>`);
}
async function resetResult(result){
 if(!result.complete){
  resetDownloaded=false;
  const p=result.pending;
  resetBackup={backup_id:p.backup_id,project:p.project,phrase:'AZZERA '+p.project.slice(0,12)};
  modal('Azzeramento da completare',`<p>${esc(result.message)}</p><p>${esc(p.error||'')}</p><p>Backup: ${esc(p.backup_id)}</p><button data-reset-download="1">Scarica backup NM</button><label>Scrivi ${esc(resetBackup.phrase)}<input id="reset-phrase" autocomplete="off"></label><label class="check"><input type="checkbox" id="reset-consent">Confermo di riprendere le operazioni rimanenti</label>`,`<button data-reset-resume="1">Riprendi azzeramento</button>`);
  return;
 }
 modal('Progetto NM azzerato',`<p>${esc(result.message)}</p><p>Backup conservato: ${esc(result.backup_id)}</p>${result.restart_required?'<p>Riavvia Home Assistant quando sei pronto per scaricare le entità simulate del package rimosso.</p>':''}<a href="advanced">Importa un nuovo file ETS →</a><details><summary>Elementi conservati</summary>${resetList(result.preserved||[])}</details>`,'');
}
document.addEventListener('click',e=>{
 const d=e.target.closest('button')?.dataset;if(!d||busy)return;
 if(d.resetProject)work(async()=>{const s=await api('control/reset',{operation:'status'});if(s.pending)await resetResult({complete:false,pending:s.pending,message:'Un azzeramento precedente è rimasto incompleto.'});else{if(!snapshot?.project)throw Error('Nessun progetto attivo da azzerare');await resetPreview();}});
 if(d.resetPreview)work(()=>resetPreview([...document.querySelectorAll('[name=reset-legacy]:checked')].map(e=>e.value)));
 if(d.resetBackup)work(async()=>{resetBackup=await api('control/reset',{operation:'backup',project:resetReview.project,fingerprint:resetReview.fingerprint,legacy_dashboards:resetReview.legacy_dashboards});resetConfirm();});
 if(d.resetDownload)work(async()=>{const response=await fetch('control/reset-backup?id='+encodeURIComponent(resetBackup.backup_id),{cache:'no-store'});if(!response.ok)throw Error('Download del backup non riuscito');const blob=await response.blob();if(!blob.size)throw Error('Backup vuoto');const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='NM-backup-prima-reset-'+resetBackup.backup_id+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),60000);resetDownloaded=true;const s=document.querySelector('#reset-download-status');if(s)s.textContent='Backup scaricato. Conserva il file prima di confermare.';});
 if(d.resetApply||d.resetResume)work(async()=>{if(!resetDownloaded)throw Error('Scarica prima il backup');if(!$('#reset-consent').checked||$('#reset-phrase').value!==resetBackup.phrase)throw Error('Spunta la conferma e scrivi la frase esatta');const r=await api('control/reset',{operation:d.resetResume?'resume':'apply',project:resetBackup.project,legacy_dashboards:resetBackup.legacy_dashboards||[],fingerprint:resetBackup.fingerprint,backup_id:resetBackup.backup_id,backup_downloaded:true,confirm:true,phrase:$('#reset-phrase').value});await resetResult(r);});
});
