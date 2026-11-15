'use strict';
// Generic supervision layouts, not construction drawings or control programs.
const PLANT_MODELS = [
  {
    id:'direct',name:'Generatore e circuito diretto',description:'Un generatore, una pompa, una valvola e due sonde.',
    points:[
      {symbol:'boiler',label:'Generatore',x:16,y:50},
      {symbol:'temperature',label:'Sonda mandata',x:34,y:28,temp_low:30,temp_high:65},
      {symbol:'pump',label:'Pompa circuito',x:51,y:28},
      {symbol:'valve',label:'Valvola circuito',x:70,y:28},
      {symbol:'temperature',label:'Sonda ritorno',x:51,y:73,temp_low:25,temp_high:55}
    ],
    pipes:[{tone:'supply',xy:[[16,50],[16,28],[88,28],[88,48]]},{tone:'return',xy:[[88,54],[88,73],[16,73],[16,50]]}],
    areas:[{x:81,y:43,w:14,h:17,text:'CIRCUITO'}]
  },
  {
    id:'buffer_zones',name:'Accumulo e due zone',description:'Un generatore, accumulo e due circuiti con pompe, valvole e sonde indipendenti.',
    points:[
      {symbol:'boiler',label:'Generatore',x:10,y:50},
      {symbol:'pump',label:'Pompa primaria',x:25,y:25},
      {symbol:'tank',label:'Accumulo',x:41,y:50},
      {symbol:'temperature',label:'Sonda accumulo',x:41,y:73,temp_low:30,temp_high:65},
      {symbol:'pump',label:'Pompa zona 1',x:58,y:23},
      {symbol:'valve',label:'Valvola zona 1',x:73,y:23},
      {symbol:'temperature',label:'Mandata zona 1',x:88,y:23,temp_low:25,temp_high:50},
      {symbol:'pump',label:'Pompa zona 2',x:58,y:62},
      {symbol:'valve',label:'Valvola zona 2',x:73,y:62},
      {symbol:'temperature',label:'Mandata zona 2',x:88,y:62,temp_low:25,temp_high:50}
    ],
    pipes:[{tone:'supply',xy:[[10,50],[10,25],[41,25],[41,50],[49,50],[49,23],[93,23],[93,35]]},{tone:'supply',xy:[[49,50],[49,62],[93,62],[93,74]]},{tone:'return',xy:[[93,44],[93,49],[45,49],[45,82],[10,82],[10,50]]},{tone:'return',xy:[[93,83],[45,83],[45,50]]}],
    areas:[{x:87,y:35,w:11,h:9,text:'ZONA 1'},{x:87,y:74,w:11,h:9,text:'ZONA 2'}]
  },
  {
    id:'dual',name:'Due generatori e accumulo',description:'Due rami primari, accumulo comune e un circuito di distribuzione.',
    points:[
      {symbol:'boiler',label:'Generatore 1',x:11,y:27},
      {symbol:'pump',label:'Pompa primaria 1',x:29,y:27},
      {symbol:'boiler',label:'Generatore 2',x:11,y:67},
      {symbol:'pump',label:'Pompa primaria 2',x:29,y:67},
      {symbol:'tank',label:'Accumulo comune',x:49,y:47},
      {symbol:'temperature',label:'Sonda accumulo',x:49,y:76,temp_low:30,temp_high:65},
      {symbol:'pump',label:'Pompa distribuzione',x:65,y:27},
      {symbol:'valve',label:'Valvola distribuzione',x:81,y:27},
      {symbol:'temperature',label:'Sonda ritorno',x:73,y:76,temp_low:25,temp_high:55}
    ],
    pipes:[{tone:'supply',xy:[[11,27],[40,27],[40,47],[49,47],[49,27],[93,27],[93,43]]},{tone:'supply',xy:[[11,67],[40,67],[40,47]]},{tone:'return',xy:[[93,54],[93,76],[49,76],[49,87],[6,87],[6,27],[11,27]]},{tone:'return',xy:[[6,67],[11,67]]}],
    areas:[{x:87,y:43,w:11,h:11,text:'CIRCUITO'}]
  }
];

function plantBackground(model, includePipes=false) {
  const canvas=document.createElement('canvas');canvas.width=1600;canvas.height=1000;
  const c=canvas.getContext('2d');c.fillStyle='#111d1a';c.fillRect(0,0,1600,1000);
  c.strokeStyle='#20332b';c.lineWidth=1;
  for(let x=40;x<1600;x+=40){c.beginPath();c.moveTo(x,0);c.lineTo(x,1000);c.stroke()}
  for(let y=40;y<1000;y+=40){c.beginPath();c.moveTo(0,y);c.lineTo(1600,y);c.stroke()}
  c.fillStyle='#c2d4ca';c.font='600 28px system-ui';c.fillText(model.name,70,80);
  c.font='18px system-ui';c.fillStyle='#94aa9e';c.fillText('Schema di supervisione · personalizza componenti e collegamenti',70,116);
  for(const pipe of includePipes?model.pipes:[]){c.strokeStyle=pipe.tone==='supply'?'#c58d71':'#699fb6';c.lineWidth=7;c.lineJoin='round';c.beginPath();pipe.xy.forEach(([x,y],i)=>i?c.lineTo(x*16,y*10):c.moveTo(x*16,y*10));c.stroke()}
  for(const a of model.areas){c.fillStyle='#21382c';c.fillRect(a.x*16,a.y*10,a.w*16,a.h*10);c.strokeStyle='#6a8c78';c.lineWidth=2;c.strokeRect(a.x*16,a.y*10,a.w*16,a.h*10);c.fillStyle='#dce8e0';c.font='600 19px system-ui';c.textAlign='center';c.fillText(a.text,(a.x+a.w/2)*16,(a.y+a.h/2)*10+6)}
  c.textAlign='left';c.font='18px system-ui';c.fillStyle='#c58d71';c.fillText('MANDATA',70,945);c.fillStyle='#699fb6';c.fillText('RITORNO',230,945);c.fillStyle='#94aa9e';c.fillText('Tracciati grafici indicativi · nessuna regolazione automatica',430,945);
  return canvas.toDataURL('image/png');
}

function templateCandidates(point, devices) {
  const types=point.symbol==='temperature'?['temperature','climate']:point.symbol==='pump'?['light','dimmer','momentary','climate']:point.symbol==='valve'?['cover','light','dimmer','momentary']:point.symbol==='boiler'?['climate','light','dimmer','momentary']:null;
  return devices.filter(d=>d.entity_id&&(!types||types.includes(d.type)));
}

function instantiatePlant(source,name,bindings,devices,makeId) {
  if(!name.trim()||name.trim().length>80)throw Error('Inserisci un nome da 1 a 80 caratteri.');
  return {id:makeId(),name:name.trim(),kind:'schematic',background:source.background,pipes:modelPipePaths(source,makeId),points:source.points.map((p,i)=>{
    const target=bindings[i]||'';
    if(target&&!templateCandidates(p,devices).some(d=>d.id===target))throw Error('Un dispositivo selezionato non è più disponibile nel progetto.');
    return {...p,id:makeId(),device:target};
  })};
}

let plantDraft=null;
function openPlantModels() {
  if(diagramDirty){toast('Salva prima lo schema corrente.');return}
  if(diagramArchive.plans.length>=15){toast('Il progetto contiene già il massimo di 15 schemi.');return}
  modal('Scegli un modello di centrale',`<p>1. Scegli lo schema · 2. Collega i dispositivi · 3. Personalizza</p><div class="plant-models">${PLANT_MODELS.map(m=>`<article class="plant-model"><div class="plant-preview"><img src="${plantBackground(m,true)}" alt="Schema ${esc(m.name)}">${m.points.map(p=>`<span style="left:${p.x}%;top:${p.y}%">${controlIcon(p.symbol)}</span>`).join('')}</div><h3>${esc(m.name)}</h3><p>${esc(m.description)}</p><small>${m.points.length} componenti · collegamenti da scegliere</small><button class="primary" data-plant-model="${m.id}">Usa questo modello</button></article>`).join('')}</div><p class="small muted">Schemi indicativi per la supervisione. Puoi sostituire lo sfondo con il progetto del termotecnico; le tubazioni del modello sono modificabili direttamente nello schema.</p>`,'');
}

function plantBindingForm(source) {
  plantDraft={...source,project:snapshot.project};
  modal('Collega e personalizza',`<label>Nome del sinottico<input id="plant-name" maxlength="80" value="${esc(source.name)}"></label><p>Collega i componenti ora oppure scegli «Collega in seguito». Gli elementi non collegati restano nel disegno. La creazione non invia comandi.</p><div class="plant-bindings">${source.points.map((p,i)=>`<label class="plant-binding">${controlIcon(p.symbol)}<span>${esc(p.label)}<small>${esc(DIAGRAM_NAMES[p.symbol])}</small></span><select data-plant-binding="${i}" aria-label="Dispositivo per ${esc(p.label)}"><option value="">Collega in seguito</option>${templateCandidates(p,snapshot.devices).map(d=>`<option value="${esc(d.id)}">${esc(d.name)} · ${esc(shortRoom(d.room))}${['unknown','unavailable'].includes(d.state)?' · non disponibile':''}</option>`).join('')}</select></label>`).join('')}</div><p class="small muted">Puoi aggiungere nuove sonde dall’editor con Aggiungi widget. Le soglie di temperatura proposte sono modificabili e hanno solo funzione grafica.</p>`,`<button data-plant-back="1">Altri modelli</button><button class="primary" data-plant-create="1">Crea e personalizza</button>`);
}

document.addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button||busy)return;const a=button.dataset;
  if(a.plantLibrary||a.plantBack)openPlantModels();
  if(a.plantModel){const m=PLANT_MODELS.find(m=>m.id===a.plantModel);if(m)plantBindingForm({...m,background:plantBackground(m)});}
  if(a.plantReuse){if(diagramDirty){toast('Salva prima lo schema corrente.');return}if(diagramArchive.plans.length>=15){toast('Massimo 15 schemi per progetto.');return}const p=currentDiagram();if(p)plantBindingForm({...p,name:(p.name+' · copia').slice(0,80)});}
  if(a.plantCreate){try{
    if(!plantDraft||plantDraft.project!==snapshot.project)throw Error('Progetto cambiato: riapri la scelta del modello.');
    if(diagramArchive.plans.length>=15)throw Error('Massimo 15 schemi per progetto.');
    const bindings=Array.from(document.querySelectorAll('[data-plant-binding]'),s=>s.value);
    const plan=instantiatePlant(plantDraft,$('#plant-name').value,bindings,snapshot.devices,uid);
    diagramArchive.plans.push(plan);diagramSelected=plan.id;diagramPoint=plan.points.find(p=>!p.device)?.id||'';diagramEditing=true;diagramZoom=1;page='diagrams';markDiagramDirty();$('#editor').close();plantDraft=null;render();toast('Copia pronta: personalizza e poi Salva e usa.');
  }catch(error){showError(error)}}
});
