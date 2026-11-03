const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function harness({available=true,connected=true,consent=true,projectMismatch=false}={}){
 const names=['pilot-load','pilot-status','pilot-access','pilot-selection','pilot-device','pilot-fields','pilot-prepare','pilot-review','pilot-plan','pilot-findings','pilot-backup','pilot-ets','pilot-create','pilot-result','pilot-created','pilot-state','pilot-observed','pilot-name'];
 const ids=Object.fromEntries(names.map(name=>[name,{value:'',checked:false,hidden:false,disabled:false,textContent:''}]));
 let fields=[];
 Object.defineProperty(ids['pilot-fields'],'innerHTML',{set(html){fields=[...html.matchAll(/data-pilot-field="([^"]+)" value="([^"]*)"/g)].map(m=>({dataset:{pilotField:m[1]},value:m[2]}));ids['pilot-name'].value='Luce ufficio';}});
 const calls=[];
 const context={etsData:projectMismatch?{project_key:'other'}:null,$:id=>ids[id],escapeHTML:String,confirm:()=>consent,setPage:()=>{},document:{querySelectorAll:s=>s==='[data-pilot-field]'?fields:s==='[data-pilot-go]'?[]:[...Object.values(ids),...fields]},api:async(path,options)=>{
  const body=options?JSON.parse(options.body):null;calls.push({path,body});
  if(path==='dashboard/missing-ha')return {project:'saved',source_fingerprint:'source',devices:[{index:4,type:'light',name:'Luce ufficio',room:'Ufficio',fields:{command:'1/1/0',feedback:'1/1/1'}}]};
  if(path==='knx/panel-capability')return {available,connected,supported_platforms:['light'],message:available?'Accessibile':'Permessi insufficienti'};
  if(path==='dashboard/missing-ha/review')return {warnings:[]};
  if(path==='knx/panel-create-plan')return {source_fingerprint:'source',calls:[{platform:'light',data:{name:'Luce ufficio',address:'1/1/0',state_address:'1/1/1'}}]};
  if(path==='dashboard/deployment-preflight')return {status:'review_required',findings:[]};
  if(path==='knx/panel-create-one')return {entity_id:'light.ufficio',created:true};
  if(path==='entities')return {entities:[{entity_id:'light.ufficio',state:'on'}]};
  throw Error(path);
 }};
 vm.createContext(context);vm.runInContext(fs.readFileSync('nm_bridge/real_ui.js','utf8'),context);context.wirePilot();
 return {ids,calls,fields:()=>fields};
}
test('pilot loads and prepares without provisioning; checks are required',async()=>{
 const h=harness();await h.ids['pilot-load'].onclick();await h.ids['pilot-prepare'].onclick();
 assert.equal(h.calls.some(c=>c.path==='knx/panel-create-one'),false);
 assert.equal(h.ids['pilot-create'].disabled,true);
 await h.ids['pilot-create'].onclick();assert.equal(h.calls.some(c=>c.path==='knx/panel-create-one'),false);
});
test('one confirmed creation uses exact preview and permits read-only state observation',async()=>{
 const h=harness();await h.ids['pilot-load'].onclick();await h.ids['pilot-prepare'].onclick();
 h.ids['pilot-backup'].checked=true;h.ids['pilot-ets'].checked=true;h.ids['pilot-ets'].onchange();assert.equal(h.ids['pilot-create'].disabled,false);
 await Promise.all([h.ids['pilot-create'].onclick(),h.ids['pilot-create'].onclick()]);
 const writes=h.calls.filter(c=>c.path==='knx/panel-create-one');assert.equal(writes.length,1);assert.equal(writes[0].body.call_index,0);assert.equal(writes[0].body.review.devices[0].index,4);assert.equal(writes[0].body.expected_call.data.state_address,'1/1/1');
 assert.equal(h.ids['pilot-create'].disabled,true);assert.equal(h.ids['pilot-result'].hidden,false);
 await h.ids['pilot-state'].onclick();assert.match(h.ids['pilot-observed'].textContent,/Stato letto: on/);
});
test('unavailable or disconnected KNX never enables create',async()=>{
 for(const settings of [{available:false},{connected:false}]){
  const h=harness(settings);await h.ids['pilot-load'].onclick();await h.ids['pilot-prepare'].onclick();h.ids['pilot-backup'].checked=true;h.ids['pilot-ets'].checked=true;h.ids['pilot-ets'].onchange();
  assert.equal(h.ids['pilot-create'].disabled,true);await h.ids['pilot-create'].onclick();assert.equal(h.calls.some(c=>c.path==='knx/panel-create-one'),false);
 }
});
test('cancelling confirmation and changing selection cannot submit an old plan',async()=>{
 const h=harness({consent:false});await h.ids['pilot-load'].onclick();await h.ids['pilot-prepare'].onclick();h.ids['pilot-backup'].checked=true;h.ids['pilot-ets'].checked=true;
 await h.ids['pilot-create'].onclick();assert.equal(h.calls.some(c=>c.path==='knx/panel-create-one'),false);
 h.ids['pilot-device'].onchange();assert.equal(h.ids['pilot-create'].disabled,true);assert.equal(h.ids['pilot-ets'].checked,false);
});
test('pilot script is shipped and routed',()=>{
 assert.match(fs.readFileSync('nm_bridge/Dockerfile','utf8'),/COPY real_ui.js \/app\/real_ui.js/);
 assert.match(fs.readFileSync('nm_bridge/bridge.py','utf8'),/path == "\/real_ui.js"/);
 assert.match(fs.readFileSync('nm_bridge/index.html','utf8'),/<script src="real_ui.js"><\/script>/);
});

test('a different open ETS project blocks loading saved widgets for creation',async()=>{
 const h=harness({projectMismatch:true});await h.ids['pilot-load'].onclick();
 assert.equal(h.ids['pilot-selection'].hidden,true);assert.equal(h.ids['pilot-create'].disabled,true);
 assert.match(h.ids['pilot-status'].textContent,/non corrisponde/);
 assert.equal(h.calls.some(c=>c.body),false);
});
