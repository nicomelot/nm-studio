/* Multi-device vacation editor. Weekly helpers are deliberately read-only here. */
(() => {
 const parse=s=>{try{return JSON.parse(s)}catch{return null}},e=ncEscape;
 const groups={light:'Luci',cover:'Tapparelle',climate:'Termostati'};
 const labels={on:'Accendi',off:'Spegni',open:'Apri',close:'Chiudi',stop:'Ferma',position:'Apertura %',brightness:'Luminosità %'};
 const timeLabel=time=>{if(!time.startsWith('sun'))return time;const [event,offset]=time.split(':');return (event==='sunrise'?'Alba':'Tramonto')+(Number(offset)?' '+(Number(offset)>0?'+':'')+Number(offset)+' min':'')};
 const group=entity=>entity.startsWith('switch.')?'light':entity.split('.')[0];
 function commands(s){const a=s.attributes||{},f=Number(a.supported_features)||0;
  return group(s.entity_id)==='cover'?[[1,'open'],[2,'close'],[8,'stop'],[4,'position']].filter(([bit])=>f&bit).map(([,v])=>v):['on','off',...((a.supported_color_modes||[]).some(v=>!['onoff','unknown'].includes(v))?['brightness']:[])];
 }
 function validateSlots(slots,state){
  if(!Array.isArray(slots)||slots.length>8)throw Error('Massimo 8 fasce per tipo');
  if(!slots.length)return;
  if(group(state.entity_id)==='climate'){const a=state.attributes||{};ncValidate([slots,[],[],[],[],[],[]],a.min_temp??7,a.max_temp??35,a.target_temp_step??.5);return}
  const seen=new Set(),allowed=commands(state);
  for(const [time,value] of slots){
   if(seen.has(time)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)&&!(/^(sunrise|sunset):-?\d{1,3}$/.test(time)&&Math.abs(Number(time.split(':')[1]))<=180))throw Error('Orario duplicato o non valido');
   seen.add(time);const [cmd,n]=String(value).split(':');
   if(!allowed.includes(cmd)||(['position','brightness'].includes(cmd)?!/^\d{1,3}$/.test(n)||Number(n)>100:n!==undefined))throw Error('Azione non supportata dal dispositivo');
  }
 }
 const methods={
  vacationEndOpen(){
   const targets=this.vacationTargets().filter(t=>parse(this.state(t.ids[0])?.state)?.enabled===true),host=this.shadowRoot.querySelector('#calendar-editor');
   this.vacationEndTargets=targets;
   host.innerHTML=`<style>[data-end-row][hidden]{display:none!important}</style><h3>Termina ferie</h3><p>Disabilita le ferie sui dispositivi scelti. Le fasce ferie restano salvate per riutilizzarle. Tornano applicabili le settimane esistenti e gli eventuali festivi abilitati, dalle prossime fasce. Nessun comando immediato e nessuna riattivazione dei programmi in pausa.</p><label>Cerca dispositivi per terminare ferie<input id="end-search" type="search" placeholder="Nome o entità"></label><div>${targets.map((t,i)=>{const m=parse(this.state(t.ids[0])?.state),ready=this.state(t.ids[0])?.state!=='unavailable';return `<label data-end-row="${i}" style="flex-direction:row;align-items:center"><input type="checkbox" data-end-target="${i}" ${ready?'':'disabled'}>${e(t.name)} · ${e(m.start||'?')} → ${e(m.end||'?')} · ${parse(this.state(t.commit)?.state)?.enabled?'programma attivo':'programma in pausa'}${this.available(t.entity)?'':' · dispositivo non disponibile, profilo disattivabile'}</label>`}).join('')||'<p>Nessun profilo ferie abilitato in questo progetto.</p>'}</div><button id="end-all" ${targets.length?'':'disabled'}>Seleziona tutti i risultati</button><button id="end-none">Deseleziona tutti</button><button id="end-preview" ${targets.length?'':'disabled'}>Anteprima fine ferie</button><div id="end-preview-content"></div>`;
   host.querySelector('#end-search').oninput=ev=>{const q=ev.target.value.trim().toLocaleLowerCase();host.querySelectorAll('[data-end-row]').forEach(n=>{const t=targets[Number(n.dataset.endRow)];n.hidden=!(t.name+' '+t.entity).toLocaleLowerCase().includes(q)})};
   host.querySelector('#end-all').onclick=()=>host.querySelectorAll('[data-end-row]:not([hidden]) input:not(:disabled)').forEach(n=>n.checked=true);
   host.querySelector('#end-none').onclick=()=>host.querySelectorAll('[data-end-target]').forEach(n=>n.checked=false);
   host.querySelector('#end-preview').onclick=()=>this.work(()=>this.vacationEndPreview());host.scrollIntoView({block:'nearest'});
  },
  vacationEndPlan(){
   const targets=[...this.shadowRoot.querySelectorAll('[data-end-target]:checked')].map(n=>this.vacationEndTargets[Number(n.dataset.endTarget)]);
   if(!targets.length)throw Error('Seleziona almeno un dispositivo');
   return targets.map(t=>{const meta=parse(this.state(t.ids[0])?.state);if(!meta||meta.enabled!==true)throw Error(t.name+': ferie già terminate o profilo cambiato. Riapri Termina ferie');
    const watch=[...t.ids,t.commit,t.targetId];return {...t,watch,base:watch.map(id=>this.state(id)?.state),value:JSON.stringify({...meta,enabled:false})};
   });
  },
  vacationEndCheck(plan){
   const ids=new Set();for(const p of plan){if(ids.has(p.ids[0]))throw Error('Profili condivisi: operazione annullata');ids.add(p.ids[0]);if(!this.state(p.ids[0])||this.state(p.ids[0]).state==='unavailable'||JSON.stringify(p.base)!==JSON.stringify(p.watch.map(id=>this.state(id)?.state)))throw Error(p.name+': dati cambiati. Ripeti l’anteprima')}
  },
  async vacationEndPreview(){
   const plan=this.vacationEndPlan();this.vacationEndCheck(plan);
   this.shadowRoot.querySelector('#end-preview-content').innerHTML=`<h3>Anteprima fine ferie · ${plan.length} dispositivi</h3><ul>${plan.map(p=>`<li><strong>${e(p.name)}</strong>: ferie disabilitate → ${parse(p.base[2])?.enabled?'settimana salvata, salvo eventuali festivi abilitati':'programma ancora in pausa'}</li>`).join('')}</ul><p>Le settimane, i festivi e le fasce ferie restano invariati. Gli orari già trascorsi non vengono recuperati. Il salvataggio è sequenziale: eventuali esiti parziali saranno indicati.</p>`;
   if(!await this.approve(`Terminare le ferie su ${plan.length} dispositivi selezionati? Le settimane salvate tornano applicabili dalle prossime fasce, salvo festivi abilitati. I programmi in pausa restano in pausa.`))return;
   await this.vacationEndApply(plan);
  },
  async vacationEndApply(plan){
   this.vacationEndCheck(plan);const done=[];let current;
   try{for(const p of plan){current=p;this.vacationEndCheck([p]);await this.service(p.ids[0],'set_value',{value:p.value});
    let verified=false;for(let i=0;i<20;i++){if(this.state(p.ids[0])?.state===p.value){verified=true;break}await new Promise(resolve=>setTimeout(resolve,250))}
    if(!verified)throw Error('Esito non confermato da Home Assistant: controlla il profilo');done.push(p.name);
   }}catch(err){throw Error(`Fine ferie interrotta su ${current?.name||'dispositivo'}: ${err.message}. Confermati ${done.length}/${plan.length}: ${done.join(', ')||'nessuno'}. Gli altri dispositivi non sono confermati; controlla i profili prima di riprovare. Settimane intatte.`)}
   this.message(`Ferie terminate su ${done.length} dispositivi. Settimane e festivi salvati conservati; programmi in pausa invariati. Nessun comando immediato.`);
  },
  vacationTargets(){
   const states=Object.values(this._hass.states),project=this.config.project||parse(this.calendarEntity('target')?.state)?.p;
   if(!project)return [];
   const found=[];
   for(const s of states){const name=s.attributes?.friendly_name||'';if(!s.entity_id.startsWith('input_text.')||!name.startsWith('NM target '))continue;
    const target=parse(s.state),commit=name.slice(10);if(target?.p!==project||!groups[group(target.e||'')])continue;
    const indexes=states.filter(x=>x.entity_id.startsWith('input_text.')&&x.attributes?.friendly_name==='NM index '+commit);
    const ids=indexes.length===1?parse(indexes[0].state)?.v:null;
    if(!Array.isArray(ids)||ids.length!==2||ids.some(id=>!/^input_text\.[a-z0-9_]+$/.test(id)))continue;
    const state=this.state(target.e),ready=!!state&&!['unknown','unavailable'].includes(state.state)&&[commit,...ids].every(id=>this.state(id)&&this.state(id).state!=='unavailable');
    found.push({entity:target.e,commit,ids,targetId:s.entity_id,name:state?.attributes?.friendly_name||target.e,ready,kind:group(target.e)});
   }
   return found.filter(t=>found.filter(x=>x.entity===t.entity||x.commit===t.commit).length===1).sort((a,b)=>a.name.localeCompare(b.name));
  },
  vacationOpen(){
   const targets=this.vacationTargets(),host=this.shadowRoot.querySelector('#calendar-editor');
   this.vacationDraft={targets,slots:{light:[],cover:[],climate:[]}};
   host.innerHTML=`<style>[data-vac-row][hidden]{display:none!important}</style><h3>Ferie su più dispositivi</h3><p>Date comuni, fasce per tipo. I profili ferie esistenti dei dispositivi scelti saranno sostituiti. Settimane, festivi e programmi in pausa restano invariati.</p><div class="fields"><label>Inizio ferie di gruppo<input type="date" id="vac-start"></label><label>Fine ferie di gruppo inclusa<input type="date" id="vac-end"></label></div><label>Cerca dispositivi ferie<input type="search" id="vac-search" placeholder="Nome o entità"></label><div id="vac-targets">${targets.map((t,i)=>`<label style="flex-direction:row;align-items:center" data-vac-row="${i}"><input type="checkbox" data-vac-target="${i}" ${t.ready?'':'disabled'}>${e(t.name)} · ${e(groups[t.kind])} · ${!t.ready?'non disponibile':parse(this.state(t.commit)?.state)?.enabled?'programma attivo':'programma in pausa'}</label>`).join('')||'<p>Nessun dispositivo predisposto in questo progetto. Pubblica le card da NM Control.</p>'}</div><p>Seleziona esplicitamente i dispositivi da modificare. Una lista di fasce vuota sospende le azioni per quel tipo durante le ferie. Le fasce clima non accendono un termostato spento.</p>${Object.entries(groups).map(([kind,name])=>`<section><h3>${name}</h3><div id="vac-slots-${kind}"></div><button data-vac-add="${kind}">＋ Fascia ${name.toLowerCase()}</button></section>`).join('')}<label>Applicazione<select id="vac-mode"><option value="save">Salva tutti i profili disabilitati</option><option value="enable">Salva e abilita i profili ferie</option></select></label><button id="vac-preview">Anteprima ferie di gruppo</button><div id="vac-preview-content"></div>`;
   host.querySelector('#vac-search').oninput=ev=>{const q=ev.target.value.trim().toLocaleLowerCase();host.querySelectorAll('[data-vac-row]').forEach(n=>{const t=targets[Number(n.dataset.vacRow)];n.hidden=!(t.name+' '+t.entity).toLocaleLowerCase().includes(q)})};
   host.querySelectorAll('[data-vac-add]').forEach(b=>b.onclick=()=>{const kind=b.dataset.vacAdd,slots=this.vacationDraft.slots[kind];if(slots.length>=8)return this.message('Massimo 8 fasce per tipo',true);slots.push(['07:00',kind==='climate'?17:kind==='cover'?'close':'off']);this.vacationSlots(kind)});
   host.querySelector('#vac-preview').onclick=()=>this.work(()=>this.vacationPreview());host.scrollIntoView({block:'nearest'});
  },
  vacationSlots(kind){
   const slots=this.vacationDraft.slots[kind],host=this.shadowRoot.querySelector('#vac-slots-'+kind),climate=kind==='climate';
   host.innerHTML=slots.map(([time,value],i)=>{const solar=time.startsWith('sun'),[cmd,n]=String(value).split(':');return `<fieldset><legend>${groups[kind]} · fascia ${i+1}</legend>${climate?'':`<label>Evento ${groups[kind]} ${i+1}<select data-vac-field="event" data-i="${i}">${[['time','Orario'],['sunrise','Alba'],['sunset','Tramonto']].map(([v,label])=>`<option value="${v}" ${v===(solar?time.split(':')[0]:'time')?'selected':''}>${label}</option>`).join('')}</select></label>`}<label>${solar?'Scostamento minuti':'Ora'} ${groups[kind]} ${i+1}<input data-i="${i}" data-vac-field="time" type="${solar?'number':'time'}" value="${e(solar?time.split(':')[1]:time)}"></label>${climate?`<label>Temperatura ferie ${i+1}<input type="number" step="0.5" data-i="${i}" data-vac-field="temperature" value="${e(value)}"></label>`:`<label>Azione ${groups[kind]} ${i+1}<select data-i="${i}" data-vac-field="command">${(kind==='cover'?['open','close','stop','position']:['on','off','brightness']).map(v=>`<option value="${v}" ${v===cmd?'selected':''}>${labels[v]}</option>`).join('')}</select></label>${['position','brightness'].includes(cmd)?`<label>Percentuale ${groups[kind]} ${i+1}<input type="number" min="0" max="100" data-i="${i}" data-vac-field="percent" value="${e(n)}"></label>`:''}`}<button data-vac-remove="${i}">Rimuovi ${groups[kind]} ${i+1}</button></fieldset>`}).join('');
   host.querySelectorAll('[data-vac-field]').forEach(n=>{const change=()=>{const slot=slots[Number(n.dataset.i)],field=n.dataset.vacField;
    if(field==='time')slot[0]=slot[0].startsWith('sun')?slot[0].split(':')[0]+':'+n.value:n.value;
    if(field==='temperature')slot[1]=n.value===''?null:Number(n.value);
    if(field==='percent')slot[1]=String(slot[1]).split(':')[0]+':'+n.value;
    if(field==='event'){slot[0]=n.value==='time'?'07:00':n.value+':0';this.vacationSlots(kind)}
    if(field==='command'){slot[1]=n.value+(['position','brightness'].includes(n.value)?':50':'');this.vacationSlots(kind)}
   };if(n.tagName==='SELECT')n.onchange=change;else n.oninput=change});
   host.querySelectorAll('[data-vac-remove]').forEach(b=>b.onclick=()=>{slots.splice(Number(b.dataset.vacRemove),1);this.vacationSlots(kind)});
  },
  vacationPlan(){
   const r=this.shadowRoot,d=this.vacationDraft,meta=window.NMCalendar.validate({kind:'v',start:r.querySelector('#vac-start').value,end:r.querySelector('#vac-end').value});
   const selected=[...r.querySelectorAll('[data-vac-target]:checked')].map(n=>d.targets[Number(n.dataset.vacTarget)]);
   if(!selected.length)throw Error('Seleziona almeno un dispositivo');
   const enabled=r.querySelector('#vac-mode').value==='enable';
   return selected.map(t=>{if(!this.available(t.entity))throw Error(t.name+': non disponibile');const slots=structuredClone(d.slots[t.kind]);try{validateSlots(slots,this.state(t.entity))}catch(err){throw Error(t.name+': '+err.message)}
    const v=ncVersion(),metaValue=JSON.stringify({...meta,v,enabled:false}),body=JSON.stringify({v,s:slots});if(metaValue.length>255||body.length>255)throw Error(t.name+': troppe fasce');
    const watch=[...t.ids,t.commit,t.targetId];return {...t,enabled,metaValue,body,slots,watch,base:watch.map(id=>this.state(id)?.state)};
   });
  },
  vacationCheck(plan){
   const ids=new Set();for(const p of plan){if(!this.available(p.entity)||JSON.stringify(p.base)!==JSON.stringify(p.watch.map(id=>this.state(id)?.state)))throw Error(p.name+': dati cambiati. Ripeti l’anteprima');validateSlots(p.slots,this.state(p.entity));for(const id of p.ids){if(ids.has(id))throw Error('Profili condivisi: operazione annullata');ids.add(id)}}
  },
  async vacationPreview(){
   const plan=this.vacationPlan();this.vacationCheck(plan);
   const host=this.shadowRoot.querySelector('#vac-preview-content'),m=parse(plan[0].metaValue);
   host.innerHTML=`<h3>Anteprima · ${e(m.start)} → ${e(m.end)}</h3><ul>${plan.map(p=>`<li><strong>${e(p.name)}</strong>: ${p.slots.length?p.slots.map(([time,value])=>e(timeLabel(time)+' → '+(p.kind==='climate'?value+' °C':(labels[String(value).split(':')[0]]||value)+(String(value).includes(':')?' '+String(value).split(':')[1]+'%':'')))).join('; '):'nessuna azione durante le ferie'} · ${parse(p.base[0])?'sostituisce ferie esistenti':'nuovo profilo'} · ${parse(p.base[2])?.enabled?(p.enabled?'abilitato':'salvato disabilitato'):'programma principale in pausa'}</li>`).join('')}</ul><p>La settimana e i festivi non vengono riscritti. Le azioni già trascorse non vengono recuperate. Il salvataggio su più dispositivi è sequenziale: eventuali errori vengono indicati per dispositivo.</p>`;
   if(!await this.approve(`Applicare le ferie dal ${m.start} al ${m.end} a ${plan.length} dispositivi? ${plan[0].enabled?'I profili saranno abilitati, senza riattivare programmi in pausa.':'I profili saranno salvati disabilitati.'}`))return;
   await this.vacationApply(plan);
  },
  async vacationApply(plan){
   this.vacationCheck(plan);const completed=[],activated=[];let current=null;
   try{
    // Stage every target disabled before enabling any; never touch weekly commits.
    for(const p of plan){current=p;this.vacationCheck([p]);await this.service(p.ids[0],'set_value',{value:p.metaValue});await this.service(p.ids[1],'set_value',{value:p.body});completed.push(p)}
    for(const p of plan){if(!p.enabled)continue;current=p;
     // Read back from HA, not a local optimistic state. Partial saves remain disabled.
     await this.vacationAwait(p);
     await this.service(p.ids[0],'set_value',{value:JSON.stringify({...parse(p.metaValue),enabled:true})});activated.push(p.name);
    }
   }catch(err){throw Error(`Operazione interrotta su ${current?.name||'dispositivo'}: ${err.message}. Salvati ${completed.length}/${plan.length}. Profili abilitati: ${activated.join(', ')||'nessuno'}. Controlla i profili dei dispositivi indicati nell’anteprima prima di riprovare; le settimane sono intatte.`)}
   this.message(`Ferie ${plan[0].enabled?'abilitate':'salvate disabilitate'} su ${completed.length} dispositivi. Settimane e stato dei programmi principali invariati. Controlla il riepilogo di oggi.`);
  },
  async vacationAwait(p){
   for(let i=0;i<20;i++){
    if(this.state(p.ids[0])?.state===p.metaValue&&this.state(p.ids[1])?.state===p.body){if(!this.available(p.entity))throw Error('Dispositivo non disponibile');validateSlots(p.slots,this.state(p.entity));if(this.state(p.commit)?.state!==p.base[2]||this.state(p.targetId)?.state!==p.base[3])throw Error('Configurazione modificata durante il salvataggio');return}
    await new Promise(resolve=>setTimeout(resolve,250));
   }throw Error('Salvataggio non confermato da Home Assistant; profilo lasciato disabilitato');
  }
 };
 Object.assign(NMClimateCard.prototype,methods);
 const mount=NMClimateCard.prototype.calendarMount;
 NMClimateCard.prototype.calendarMount=function(){mount.call(this);const bar=this.shadowRoot.querySelector('dialog .bar');if(!bar)return;for(const [label,method] of [['Ferie su più dispositivi','vacationOpen'],['Termina ferie','vacationEndOpen']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>this[method]();bar.append(b)}};
 window.NMVacation={validateSlots,commands};
})();
