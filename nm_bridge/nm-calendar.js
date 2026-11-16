/* Shared popup calendar. Dates and solar previews are evaluated by the scheduler. */
(() => {
 const names={v:'Ferie',f:'Festivi',w:'Settimana abituale'};
 const escape=ncEscape;
 const parse=value=>{try{return JSON.parse(value)}catch{return null}};
 const version=ncVersion;
 function validDate(value){return /^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T12:00:00Z'))&&new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value}
 function validate(meta){
  if(meta.kind==='v'){if(!validDate(meta.start)||!validDate(meta.end)||meta.end<meta.start)throw Error('Controlla inizio e fine ferie')}
  else if(meta.kind==='f'){if(!Array.isArray(meta.dates)||!meta.dates.length||meta.dates.length>10||new Set(meta.dates).size!==meta.dates.length||meta.dates.some(d=>!validDate(d)))throw Error('Inserisci da 1 a 10 date festive distinte nel formato AAAA-MM-GG')}
  else throw Error('Profilo non valido');
  return meta;
 }
 const methods={
  calendarEntity(kind){
   const name=`NM ${kind} ${this.config.schedule?.commit}`;
   const matches=Object.values(this._hass?.states||{}).filter(s=>s.entity_id.startsWith('input_text.')&&s.attributes?.friendly_name===name);
   return matches.length===1?matches[0]:null;
  },
  calendarIndex(){return parse(this.calendarEntity('index')?.state)},
  actionLabel(value){
   if(this.config.entity.startsWith('climate.'))return `${value} °C`;
   const [kind,percent]=String(value).split(':');return (this.label?.(kind)||kind)+(percent===undefined?'':` ${percent}%`);
  },
  calendarMount(){
   const dialog=this.shadowRoot.querySelector('dialog');if(!dialog)return;
   const host=document.createElement('section');host.id='calendar-summary';host.className='notice';host.setAttribute('aria-label','Programmazione di oggi');
   dialog.insertBefore(host,dialog.querySelector('.bar'));
   const button=document.createElement('button');button.id='calendar-open';button.textContent='Ferie e festivi';button.onclick=()=>this.calendarEditor();
   dialog.querySelector('.bar').append(button);
   const editor=document.createElement('section');editor.id='calendar-editor';dialog.insertBefore(editor,dialog.querySelector('#confirmation'));
   this.calendarSummary();
  },
  calendarSummary(){
   const host=this.shadowRoot.querySelector('#calendar-summary');if(!host)return;
   const status=parse(this.calendarEntity('next')?.state),today=parse(this.calendarEntity('today')?.state);
   if(!status){host.innerHTML='<strong>Programmazione di oggi</strong><p>Anteprima non ancora disponibile. Attendi il controllo di NM Control.</p>';return}
   const stale=!status.checked||Date.now()-Date.parse(status.checked)>90000;
   const zone=this._hass.config?.time_zone||'Europe/Rome';
   const format=value=>new Date(value).toLocaleString('it-IT',{timeZone:zone,day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
   const mode=stale?'Stato non aggiornato: esecuzione non verificabile':status.mode==='active'?'Programma attivo':status.mode==='paused'?'Programma in pausa':'Programma sospeso: '+(status.why||'verifica configurazione');
   host.innerHTML=`<strong>Oggi · ${escape(names[status.profile]||'Programma')}</strong><p>${escape(mode)}</p>${Array.isArray(today)?(today.length?'<ul style="padding-left:20px">'+today.map(([time,value])=>`<li>${escape(time)} · ${escape(this.actionLabel(value))}</li>`).join('')+'</ul>':'<p>Nessuna azione prevista oggi.</p>'):'<p>Consulta la settimana per il dettaglio completo.</p>'}<p><strong>${status.mode==='active'&&!stale?'Prossima azione':'Prossima fascia prevista'}</strong>: ${status.at?escape(format(status.at)+' · '+this.actionLabel(status.value)):'nessuna nei prossimi 31 giorni'}${status.mode!=='active'?' · non attiva':''}</p><small>Orari ${escape(zone)}. Le modifiche non salvate non sono incluse.${this.config.entity.startsWith('climate.')?' Le fasce non accendono un termostato spento.':''}</small>`;
  },
  calendarEditor(kind='v'){
   const host=this.shadowRoot.querySelector('#calendar-editor'),index=this.calendarIndex();
   if(!index?.[kind]){this.message('Profili non ancora predisposti. Attendi il riavvio aggiornato di NM Control.',true);return}
   const ids=index[kind],metaRaw=this.state(ids[0])?.state,slotsRaw=this.state(ids[1])?.state;
   const meta=parse(metaRaw),data=parse(slotsRaw);
   this.profileDraft={kind,ids,base:[metaRaw,slotsRaw],meta:meta||{kind,enabled:false,start:'',end:'',dates:[]},slots:Array.isArray(data?.s)?structuredClone(data.s):[]};
   const m=this.profileDraft.meta;
   host.innerHTML=`<h3>Profili per date speciali</h3><p>Ferie → festivi selezionati → settimana abituale. Il profilo sostituisce tutte le fasce del giorno; la settimana rimane salvata e riprende al termine. La sospensione del programma principale vale anche per i profili.</p><label>Profilo<select id="profile-kind"><option value="v" ${kind==='v'?'selected':''}>Ferie</option><option value="f" ${kind==='f'?'selected':''}>Festivi</option></select></label>${kind==='v'?`<div class="fields"><label>Inizio ferie<input id="profile-start" type="date" value="${escape(m.start||'')}"></label><label>Fine ferie inclusa<input id="profile-end" type="date" value="${escape(m.end||'')}"></label></div>`:`<label>Date festive<input id="profile-dates" placeholder="2026-12-25, 2026-12-26" value="${escape((m.dates||[]).join(', '))}"></label><small>Fino a 10 date, separate da virgola. Le festività non vengono aggiunte automaticamente.</small>`}<p id="profile-state">${m.enabled?'Profilo abilitato':'Profilo disabilitato'}</p><div id="profile-slots"></div><button id="profile-add">＋ Fascia del profilo</button><p>Un profilo attivo senza fasce non invia comandi nelle date selezionate.</p><div class="bar"><button id="profile-save">Salva profilo disabilitato</button><button id="profile-enable">Verifica e abilita profilo</button><button id="profile-disable">Disabilita profilo</button></div><p>La settimana abituale non viene modificata.</p>`;
   host.querySelector('#profile-kind').onchange=async e=>{const next=e.target.value;e.target.value=kind;if(await this.approve('Cambiare profilo? Le modifiche non salvate verranno scartate.'))this.calendarEditor(next)};
   host.querySelector('#profile-add').onclick=()=>{if(this.profileDraft.slots.length>=8)return this.message('Massimo 8 fasce nel profilo',true);this.profileDraft.slots.push(['07:00',this.config.entity.startsWith('climate.')?20:(this.commands()[0]||'off')]);this.calendarSlots()};
   host.querySelector('#profile-save').onclick=()=>this.work(()=>this.saveProfile());
   host.querySelector('#profile-enable').onclick=()=>this.work(()=>this.enableProfile(true));
   host.querySelector('#profile-disable').onclick=()=>this.work(()=>this.enableProfile(false));
   this.calendarSlots();host.scrollIntoView({block:'nearest'});
  },
  calendarSlots(){
   const host=this.shadowRoot.querySelector('#profile-slots'),climate=this.config.entity.startsWith('climate.'),a=this.attrs();
   host.innerHTML=this.profileDraft.slots.map(([when,value],i)=>{
    const solar=String(when).startsWith('sun'),[command,percent]=String(value).split(':');
    return `<fieldset><legend>Fascia ${i+1}</legend>${!climate?`<label>Evento<select data-profile="${i}" data-field="event">${[['time','Orario'],['sunrise','Alba'],['sunset','Tramonto']].map(([v,n])=>`<option value="${v}" ${v===(solar?when.split(':')[0]:'time')?'selected':''}>${n}</option>`).join('')}</select></label>`:''}<label>${solar?'Scostamento minuti':'Ora'}<input aria-label="Ora profilo ${i+1}" data-profile="${i}" data-field="when" type="${solar?'number':'time'}" ${solar?'min="-180" max="180"':''} value="${escape(solar?when.split(':')[1]:when)}"></label>${climate?`<label>Temperatura<input aria-label="Temperatura profilo ${i+1}" data-profile="${i}" data-field="value" type="number" min="${a.min_temp??7}" max="${a.max_temp??35}" step="${a.target_temp_step??.5}" value="${escape(value)}"></label>`:`<label>Azione<select aria-label="Azione profilo ${i+1}" data-profile="${i}" data-field="command">${this.commands().map(v=>`<option value="${v}" ${v===command?'selected':''}>${escape(this.label(v))}</option>`).join('')}</select></label>${['position','brightness'].includes(command)?`<label>Percentuale<input data-profile="${i}" data-field="percent" type="number" min="0" max="100" value="${escape(percent)}"></label>`:''}`}<button data-profile-remove="${i}">Rimuovi fascia ${i+1}</button></fieldset>`;
   }).join('');
   host.querySelectorAll('[data-profile]').forEach(n=>{const change=()=>{const slot=this.profileDraft.slots[Number(n.dataset.profile)],field=n.dataset.field;
    if(field==='when')slot[0]=String(slot[0]).startsWith('sun')?slot[0].split(':')[0]+':'+n.value:n.value;
    if(field==='value')slot[1]=n.value===''?null:Number(n.value);
    if(field==='percent')slot[1]=String(slot[1]).split(':')[0]+':'+n.value;
    if(field==='event'){slot[0]=n.value==='time'?'07:00':n.value+':0';this.calendarSlots()}
    if(field==='command'){slot[1]=n.value+(['position','brightness'].includes(n.value)?':50':'');this.calendarSlots()}
   };if(n.tagName==='SELECT')n.onchange=change;else n.oninput=change});
   host.querySelectorAll('[data-profile-remove]').forEach(b=>b.onclick=()=>{this.profileDraft.slots.splice(Number(b.dataset.profileRemove),1);this.calendarSlots()});
  },
  profileValues(){
   const d=this.profileDraft,r=this.shadowRoot;
   const meta=validate(d.kind==='v'?{kind:'v',start:r.querySelector('#profile-start').value,end:r.querySelector('#profile-end').value}:{kind:'f',dates:r.querySelector('#profile-dates').value.split(',').map(v=>v.trim()).filter(Boolean).sort()});
   const slots=d.slots;
   if(slots.length)this.validateCalendarSlots(slots);
   return {meta,slots};
  },
  validateCalendarSlots(slots){const a=this.attrs();return ncValidate([slots,...Array.from({length:6},()=>[])],a.min_temp??7,a.max_temp??35,a.target_temp_step??.5)},
  checkProfileBase(){const d=this.profileDraft;if(JSON.stringify(d.base)!==JSON.stringify(d.ids.map(id=>this.state(id)?.state)))throw Error('Profilo modificato altrove: riapri Ferie e festivi prima di salvare')},
  async saveProfile(){
   const {meta,slots}=this.profileValues(),d=this.profileDraft;this.checkProfileBase();
   const v=version(),commit=JSON.stringify({...meta,v,enabled:false}),body=JSON.stringify({v,s:slots});
   if(commit.length>255||body.length>255)throw Error('Troppi dati: riduci date o fasce');
   await this.service(d.ids[0],'set_value',{value:commit});
   await this.service(d.ids[1],'set_value',{value:body});
   d.base=[commit,body];d.meta={...meta,v,enabled:false};
   this.shadowRoot.querySelector('#profile-state').textContent='Profilo salvato disabilitato';this.message('Profilo salvato. La settimana abituale è rimasta intatta.');
  },
  async enableProfile(enabled){
   const d=this.profileDraft;this.checkProfileBase();const saved=parse(d.base[0]),body=parse(d.base[1]);
   if(!saved||body?.v!==saved.v)throw Error('Salva prima il profilo completo');
   if(enabled){const {meta,slots}=this.profileValues();if(JSON.stringify(slots)!==JSON.stringify(body.s)||Object.keys(meta).some(k=>JSON.stringify(meta[k])!==JSON.stringify(saved[k])))throw Error('Salva prima le modifiche');
    if(!await this.approve(`Abilitare ${names[d.kind]}? Nelle date selezionate sostituirà la settimana, che rimane salvata. Ferie ha precedenza sui festivi. Se il programma principale è in pausa, resterà in pausa.`))return;
    this.checkProfileBase();
   }
   const value=JSON.stringify({...saved,enabled});await this.service(d.ids[0],'set_value',{value});d.base[0]=value;d.meta={...saved,enabled};
   this.shadowRoot.querySelector('#profile-state').textContent=enabled?'Profilo abilitato':'Profilo disabilitato';this.message(enabled?'Profilo abilitato. Controlla il riepilogo di oggi e lo stato del programma principale.':'Profilo disabilitato: tornano applicabili gli altri profili e la settimana.');
  }
 };
 Object.assign(NMClimateCard.prototype,methods);
 function attach(Type){const open=Type.prototype.open,update=Type.prototype.update;
  Type.prototype.open=function(...args){open.apply(this,args);this.calendarMount()};
  Type.prototype.update=function(...args){update.apply(this,args);this.calendarSummary()};
 }
 attach(NMClimateCard);
 NMClimateCard.prototype.connectedCallback=function(){clearInterval(this.calendarTimer);this.calendarTimer=setInterval(()=>this.calendarSummary(),30000)};
 NMClimateCard.prototype.disconnectedCallback=function(){clearInterval(this.calendarTimer);this.confirmResolve?.(false)};
 window.NMCalendar={attach,validate,validDate};
})();
