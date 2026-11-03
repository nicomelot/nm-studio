const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('all inline application scripts remain valid JavaScript',()=>{
 const html=fs.readFileSync('nm_bridge/index.html','utf8');
 for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
 assert.match(html,/<script src="lab_ui.js"><\/script>/);
 assert.match(fs.readFileSync('nm_bridge/Dockerfile','utf8'),/COPY lab_ui.js \/app\/lab_ui.js/);
});

function harness(candidates){
 const ids=Object.fromEntries(['lab-status','lab-check','lab-setup','lab-install','lab-dashboard-check','lab-dashboard-publish'].map(id=>[id,{disabled:true,textContent:''}]));
 const rows=candidates.map((d,i)=>{
  const kind={value:d.kind},room={value:d.room};
  return {dataset:{index:String(i)},checked:true,closest:()=>({querySelector:s=>s==='.lab-kind'?kind:room}),kind,room};
 });
 let html='';
 ids['ets-progress']={closest:()=>({insertAdjacentHTML:(position,value)=>{html=value;}})};
 const calls=[];
 const context={
  etsData:{project_key:'a'.repeat(64),lab_candidates:candidates,building:[]},
  $:id=>ids[id],escapeHTML:value=>String(value),confirm:()=>true,
  document:{querySelectorAll:selector=>selector.includes('.lab-room-choice')?[]:selector.includes(':checked')?rows.filter(r=>r.checked):rows.flatMap(r=>[r,r.kind,r.room])},
  api:async(path,options)=>{
   const body=JSON.parse(options.body);calls.push({path,body});
   if(path==='lab/preview')return {ready:true,packages_enabled:true,blocked_by_existing:false,already_installed:false,devices:body.devices.length,sha256:'fresh',target:'packages/nm_lab_virtual.yaml',message:'Virtuale'};
   if(path==='lab/install')return {installed:true};
   if(path==='lab/dashboard-preview')return {summary:{tiles:body.devices.length},warnings:[],fingerprint:'dashboard'};
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
 assert.match(h.html,/Non servono termostati/);
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
