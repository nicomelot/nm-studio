const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('all inline application scripts remain valid JavaScript',()=>{
 const html=fs.readFileSync('nm_bridge/index.html','utf8');
 for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
 assert.match(html,/<script src="lab_ui.js"><\/script>/);
 new vm.Script(fs.readFileSync('nm_bridge/project_ui.js','utf8'));
 assert.match(html,/<script src="project_ui.js"><\/script>/);
 assert.match(fs.readFileSync('nm_bridge/Dockerfile','utf8'),/COPY lab_ui.js \/app\/lab_ui.js/);
});

function harness(candidates){
 const ids=Object.fromEntries(['lab-open-dashboard','lab-room-filter','lab-step-help','lab-prev','lab-next','project-save','project-label','lab-stage','lab-real-path','lab-filter','lab-kind-filter','lab-status','lab-check','lab-setup','lab-install','lab-dashboard-check','lab-dashboard-publish'].map(id=>[id,{disabled:true,textContent:'',value:''}]));
 const rows=candidates.map((d,i)=>{
  const kind={value:d.kind},room={value:d.room},name={value:d.name};
  return {dataset:{index:String(i)},checked:d.selected!==false,closest:()=>({querySelector:s=>s==='.lab-kind'?kind:s==='.lab-name'?name:room}),kind,room,name};
 });
 let html='';
 ids['ets-progress']={closest:()=>({insertAdjacentHTML:(position,value)=>{html=value;}})};
 const calls=[];
 const context={
  etsData:{project_key:'a'.repeat(64),lab_candidates:candidates,building:[]},
  loadProjectLibrary:async()=>{},setPage:()=>{},$:id=>ids[id],escapeHTML:value=>String(value),confirm:()=>true,
  document:{querySelectorAll:selector=>selector.includes('data-lab-stage')||selector.includes('.lab-room-choice')?[]:selector.includes(':checked')?rows.filter(r=>r.checked):selector.endsWith('.lab-selected')?rows:rows.flatMap(r=>[r,r.kind,r.room,r.name])},
  api:async(path,options)=>{
   const body=JSON.parse(options.body);calls.push({path,body});
   if(path==='lab/preview')return {ready:true,packages_enabled:true,blocked_by_existing:false,already_installed:false,devices:body.devices.length,sha256:'fresh',target:'packages/nm_lab_virtual.yaml',message:'Virtuale'};
   if(path==='lab/install')return {installed:true};
   if(path==='lab/dashboard-preview')return {summary:{tiles:body.devices.length},warnings:[],fingerprint:'dashboard'};
   if(path==='lab/dashboard-existing')return {exists:false};
   if(path==='projects/save')return {saved:true,revision:'rev2'};
   if(path==='lab/dashboard-publish')return {created:true,url_path:'nm-studio-lab-test'};
   throw Error('Unexpected endpoint '+path);
  }
 };
 vm.createContext(context);
 vm.runInContext(fs.readFileSync('nm_bridge/lab_ui.js','utf8'),context);
 context.wireVirtualLab();
 return {ids,rows,calls,html};
}

test('project without climate exposes install and publishes separate LAB dashboard',async()=>{
 const h=harness([{kind:'light',command:'1/1/0',name:'L1',room:'Magazzino'}]);
 assert.match(h.html,/Configura la supervisione/);
 await h.ids['lab-check'].onclick();
 assert.equal(h.ids['lab-install'].disabled,false);
 await h.ids['lab-install'].onclick();
 assert.equal(h.calls[1].body.mode,'virtual_devices');
 assert.equal(h.calls[1].body.devices[0].kind,'light');
 assert.equal(h.calls[1].body.expected_sha256,'fresh');
 await h.ids['lab-dashboard-check'].onclick();
 assert.equal(h.ids['lab-dashboard-publish'].disabled,false);
 await h.ids['lab-dashboard-publish'].onclick();
 assert.equal(h.calls.at(-1).path,'lab/dashboard-publish');
 assert.ok(h.calls.every(c=>c.path.startsWith('lab/')));
});

test('changing room invalidates reviewed plan and empty selection performs no write',async()=>{
 const h=harness([{kind:'cover',command:'1/2/0',name:'T1',room:'Magazzino'}]);
 await h.ids['lab-check'].onclick();
 h.rows[0].room.value='Ufficio';h.rows[0].room.oninput();
 assert.equal(h.ids['lab-install'].disabled,true);
 await h.ids['lab-install'].onclick();
 assert.equal(h.calls.length,1);
 h.rows[0].checked=false;
 await h.ids['lab-check'].onclick();
 assert.match(h.ids['lab-status'].textContent,/Seleziona da 1 a 200/);
 assert.equal(h.calls.length,1);
});

test('empty recognition still shows diagnostic laboratory panel',()=>{
 const h=harness([]);
 assert.match(h.html,/Nessuna funzione riconosciuta/);
 assert.match(h.html,/id="lab-check" class="primary" disabled/);
});

test('room picker exposes choices independently of current text',()=>{
 const h=harness([{kind:'light',command:'1/1/0',name:'L1',room:'Ufficio'}]);
 assert.match(h.html,/class="lab-room-choice"/);
 assert.match(h.html,/<option value="Ufficio">Ufficio<\/option>/);
 assert.match(h.html,/class="lab-room"/);
});

test('saving captures all reviews including deselected functions and edited names',async()=>{
 const h=harness([{kind:'light',command:'1/1/0',name:'L1',room:'Magazzino'},{kind:'cover',command:'1/2/0',name:'T1',room:'Sala',selected:false}]);
 h.ids['project-label'].value='Nuova FR';h.rows[0].name.value='Luce ufficio';
 await h.ids['project-save'].onclick();
 const saved=h.calls.find(c=>c.path==='projects/save');
 assert.equal(saved.body.label,'Nuova FR');assert.equal(saved.body.reviews.length,2);
 assert.equal(saved.body.reviews[0].name,'Luce ufficio');assert.equal(saved.body.reviews[1].selected,false);
 assert.equal(h.ids['lab-stage'].value,'install');
});


test('guided navigation preserves reviewed installation and filters do not invalidate it',async()=>{
 const h=harness([{kind:'light',command:'1/1/0',name:'L1',room:'Ufficio'}]);
 assert.equal(h.ids['lab-stage'].value,'review');
 h.ids['lab-next'].onclick();assert.equal(h.ids['lab-stage'].value,'install');
 await h.ids['lab-check'].onclick();
 h.ids['lab-next'].onclick();assert.equal(h.ids['lab-stage'].value,'publish');
 h.ids['lab-prev'].onclick();assert.equal(h.ids['lab-stage'].value,'install');
 assert.equal(h.ids['lab-install'].disabled,false);
 assert.equal(h.ids['lab-filter'].oninput,undefined);
 assert.equal(h.ids['lab-stage'].oninput,undefined);
 await h.ids['lab-install'].onclick();assert.equal(h.calls.at(-1).path,'lab/install');
});

test('empty selection cannot advance the guided workflow',()=>{
 const h=harness([{kind:'light',command:'1/1/0',name:'L1',room:'Ufficio',selected:false}]);
 h.ids['lab-next'].onclick();assert.equal(h.ids['lab-stage'].value,'review');
 assert.equal(h.calls.length,0);assert.match(h.ids['lab-status'].textContent,/Seleziona/);
});

test('technical panels are moved without losing their elements or handlers',()=>{
 function element(id){return {id,children:[],appendChild(child){if(child.parent){child.parent.children=child.parent.children.filter(c=>c!==child);}this.children.push(child);child.parent=this;}};}
 const content=element('content'),lab=element('lab-wizard'),importer=element('importer'),technical=element('technical');
 technical.onclick=()=>42;content.appendChild(importer);content.appendChild(lab);content.appendChild(technical);
 const context={document:{createElement:()=>element('details')},$:id=>id==='content'?content:id==='lab-wizard'?lab:{closest:()=>importer}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('nm_bridge/project_ui.js','utf8'),context);
 context.organizeInstallerPage();
 assert.equal(content.children[0],lab);assert.equal(content.children.length,3);
 assert.equal(technical.parent,content.children[2]);assert.equal(technical.onclick(),42);
 assert.equal(importer.parent,content.children[1]);
});
