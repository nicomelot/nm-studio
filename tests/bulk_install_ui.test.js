const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
async function harness({failSecond=false,consent=true,connected=true}={}){
 const names=['load','edit','next','verified','create','list','status','results'];
 const ids=Object.fromEntries(names.map(n=>['install-'+n,{checked:false,disabled:false,hidden:false,textContent:''}]));
 let rows=[];const calls=[];
 Object.defineProperty(ids['install-list'],'innerHTML',{set(html){rows=[...html.matchAll(/data-install-index="(\d+)" data-blocked="(true|false)"/g)].map(m=>({dataset:{installIndex:m[1],blocked:m[2]},checked:m[2]==='false',disabled:m[2]==='true'}));}});
 const devices=[{index:0,name:'A',type:'light',room:'Sala',fields:{command:'1/1/1'}},{index:1,name:'B',type:'cover',room:'Sala',fields:{command:'1/1/2',stop:'1/1/3'}},{index:2,name:'C',type:'dimmer',room:'Sala',fields:{command:'1/1/4',relative:'1/1/5'}}];
 const context={etsData:null,$:id=>ids[id],escapeHTML:String,confirm:()=>consent,setPage:()=>{},document:{querySelectorAll:s=>s==='[data-install-index]'?rows:s.includes('input')?[...Object.values(ids),...rows]:Object.values(ids)},api:async(path,options)=>{
  const body=options?JSON.parse(options.body):null;calls.push({path,body});
  if(path==='knx/installation-review')return {source_fingerprint:'start',devices:devices.map(d=>({...d,status:d.index===0?'update':'create',reason:'Pronta'}))};
  if(path==='knx/panel-capability')return {available:true,connected,supported_platforms:['light','cover']};
  if(path==='knx/panel-create-plan')return {source_fingerprint:body.source_fingerprint,calls:body.devices.map(d=>({platform:d.index===1?'cover':'light',data:{entity:{name:d.name}}}))};
  if(path==='dashboard/deployment-preflight')return {status:'review_required',findings:[]};
  if(path==='knx/installation-apply'){
   const index=body.index;
   if(index===1&&failSecond)throw Error('Connessione interrotta');
   return {entity_id:'light.created_'+index,linked:true,source_fingerprint:'after-'+index};
  }
  throw Error(path);
 }};
 vm.createContext(context);vm.runInContext(fs.readFileSync('nm_bridge/real_ui.js','utf8'),context);
 await context.wireBulkInstall();return {ids,rows,calls};
}
test('one confirmation creates selected ready devices sequentially with refreshed fingerprint',async()=>{
 const h=await harness();assert.equal(h.rows[2].disabled,true);assert.equal(h.ids['install-create'].disabled,true);
 h.ids['install-verified'].checked=true;h.ids['install-verified'].onchange();
 await Promise.all([h.ids['install-create'].onclick(),h.ids['install-create'].onclick()]);
 const writes=h.calls.filter(c=>c.path==='knx/installation-apply');assert.equal(writes.length,2);
 assert.equal(writes[1].body.source_fingerprint,'after-0');assert.equal(writes[1].body.expected.name,'B');
 assert.match(h.ids['install-status'].textContent,/2 modifiche applicate/);assert.equal(h.ids['install-next'].hidden,false);
});
test('failure preserves success, stops queue and disables retry until reload',async()=>{
 const h=await harness({failSecond:true});h.ids['install-verified'].checked=true;await h.ids['install-create'].onclick();
 assert.match(h.ids['install-results'].textContent,/light.created_0/);assert.match(h.ids['install-status'].textContent,/Interrotto/);assert.equal(h.ids['install-create'].disabled,true);
 await h.ids['install-create'].onclick();assert.equal(h.calls.filter(c=>c.path==='knx/installation-apply').length,2);
});
test('cancellation and disconnected bus prevent provisioning',async()=>{
 for(const config of [{consent:false},{connected:false}]){
  const h=await harness(config);h.ids['install-verified'].checked=true;await h.ids['install-create'].onclick();assert.equal(h.calls.filter(c=>c.path==='knx/installation-apply').length,0);
 }
});
