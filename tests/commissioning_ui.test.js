const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
async function harness(){
 const ids={},calls=[];let rows=[],buttons=[];
 const element=()=>({checked:false,disabled:false,value:'',textContent:'',dataset:{}});
 for(const key of ['install-load','install-list','install-status','install-results','install-edit','install-create','install-verified','install-next','commission-enabled','commission-refresh'])ids[key]=element();
 Object.defineProperty(ids['install-list'],'innerHTML',{set(html){
  rows=[...html.matchAll(/data-install-index="(\d+)" data-blocked="(true|false)"/g)].map(m=>({...element(),dataset:{installIndex:m[1],blocked:m[2]}}));
  buttons=[...html.matchAll(/data-commission-index="(\d+)" data-commission-action="(\w+)"/g)].map(m=>({...element(),dataset:{commissionIndex:m[1],commissionAction:m[2]}}));
  ids['commission-state-0']=element();ids['commission-level-0']={...element(),value:'50'};
 }});
 const c={etsData:null,$:id=>ids[id],escapeHTML:String,setPage(){},confirm:()=>true,
 document:{querySelectorAll(s){if(s==='[data-install-index]')return rows;if(s==='[data-commission-action]')return buttons;return [...Object.values(ids),...rows,...buttons];}},
 api:async(path,options)=>{const body=options?JSON.parse(options.body):null;calls.push({path,body});
  if(path==='knx/installation-review')return {project:'x',source_fingerprint:'snapshot',devices:[{index:0,name:'Sala',room:'Casa / Sala',type:'dimmer',status:'present',entity_id:'light.sala',fields:{command:'1/1/1',brightness:'1/1/2'}}]};
  if(path==='knx/panel-capability')return {available:true,connected:true,supported_platforms:['light']};
  if(path==='entities')return {entities:[{entity_id:'light.sala',state:'unavailable'}]};
  if(path==='knx/commission-command')return {sent:true,message:'Accettato da HA; verifica fisica da eseguire'};
  throw Error(path);
 }};
 vm.createContext(c);vm.runInContext(fs.readFileSync('nm_bridge/real_ui.js','utf8'),c);await c.wireBulkInstall();
 return {c,ids,calls,get buttons(){return buttons;}};
}
test('loading and state reads never send commands, arm is enabled but unchecked',async()=>{
 const h=await harness();assert.equal(h.ids['commission-enabled'].disabled,false);
 assert.equal(h.ids['commission-enabled'].checked,false);assert.ok(h.buttons.every(b=>b.disabled));
 await h.buttons[0].onclick();await h.ids['commission-refresh'].onclick();
 assert.equal(h.calls.filter(c=>c.body).length,0);
 assert.match(h.ids['commission-state-0'].textContent,/Stato non disponibile/);
});
test('explicit arm plus click sends exact target; changing level alone does nothing',async()=>{
 const h=await harness();h.ids['commission-enabled'].checked=true;h.ids['commission-enabled'].onchange();
 assert.ok(h.buttons.every(b=>!b.disabled));
 h.ids['commission-level-0'].value='35';assert.equal(h.calls.filter(c=>c.body).length,0);
 await h.buttons.find(b=>b.dataset.commissionAction==='brightness').onclick();
 const write=h.calls.find(c=>c.path==='knx/commission-command');
 assert.equal(write.body.entity_id,'light.sala');assert.equal(write.body.value,35);assert.equal(write.body.source_fingerprint,'snapshot');
 assert.match(h.ids['commission-state-0'].textContent,/verifica fisica/);
 await h.ids['install-load'].onclick();assert.equal(h.ids['commission-enabled'].checked,false);
 assert.ok(h.buttons.every(b=>b.disabled));
});
test('invalid percent is blocked in UI and unconfirmed entities have no controls',async()=>{
 const h=await harness();h.ids['commission-enabled'].checked=true;h.ids['commission-enabled'].onchange();
 h.ids['commission-level-0'].value='200';await h.buttons.find(b=>b.dataset.commissionAction==='brightness').onclick();
 assert.equal(h.calls.filter(c=>c.body).length,0);
 assert.equal(h.c.commissioningControls({status:'review',entity_id:'light.test',type:'light'}),'');
});
