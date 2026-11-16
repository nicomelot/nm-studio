const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function setup(){
 const c=vm.createContext({HTMLElement:class{},customElements:{get:()=>true},window:{},structuredClone,crypto:require('node:crypto').webcrypto,setInterval,clearInterval,setTimeout});
 for(const file of ['nm-climate-card.js','nm-calendar.js','nm-vacation.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../nm_bridge',file),'utf8'),c);
 const proto=vm.runInContext('NMClimateCard.prototype',c),states={},calls=[],card=Object.create(proto);
 card._hass={states};card.config={project:'demo'};card.message=()=>{};card.state=id=>states[id];card.available=id=>!!states[id]&&!['unknown','unavailable'].includes(states[id].state);
 const put=(id,value,attrs={})=>states[id]={entity_id:id,state:typeof value==='string'?value:JSON.stringify(value),attributes:attrs};
 const plan=['light.demo','cover.demo','climate.demo'].map((entity,i)=>{
  put(entity,'off',i===1?{supported_features:15}:i===2?{min_temp:7,max_temp:30,target_temp_step:.5}:{});
  const ids=['input_text.v'+i,'input_text.s'+i],commit='input_text.c'+i,targetId='input_text.t'+i,metaValue=JSON.stringify({kind:'v',start:'2026-12-24',end:'2027-01-06',v:'a'.repeat(32),enabled:false}),slots=[['08:00',i===0?'off':i===1?'position:35':17]],body=JSON.stringify({v:'a'.repeat(32),s:slots});
  ids.forEach(id=>put(id,'unknown'));put(commit,{enabled:false,v:'b'.repeat(32)});put(targetId,{e:entity,p:'demo'},{friendly_name:'NM target '+commit});put('input_text.i'+i,{v:ids},{friendly_name:'NM index '+commit});
  const watch=[...ids,commit,targetId];return {entity,name:entity,ids,commit,targetId,watch,base:watch.map(id=>states[id].state),metaValue,body,slots,enabled:true};
 });
 card.service=async(id,service,data)=>{calls.push({id,value:data.value});put(id,data.value)};
 return {c,card,states,calls,plan,put};
}
test('mixed vacation stages all profiles then activates; weekly commits remain byte-identical',async()=>{
 const {card,states,calls,plan}=setup(),before=plan.map(p=>states[p.commit].state);
 await card.vacationApply(plan);
 assert.equal(calls.length,9);assert.ok(calls.slice(0,6).every(c=>!JSON.parse(c.value).enabled));
 assert.deepEqual(plan.map(p=>states[p.commit].state),before);
 assert.ok(calls.every(c=>plan.some(p=>p.ids.includes(c.id))));
 assert.ok(plan.every(p=>JSON.parse(states[p.ids[0]].state).enabled));
});
test('any target changed after preview blocks entire batch before writing',async()=>{
 const {card,states,calls,plan}=setup();states[plan[2].ids[0]].state='changed';
 await assert.rejects(card.vacationApply(plan),/dati cambiati/);assert.equal(calls.length,0);
});
test('failed staging never enables any profile and reports partial completion',async()=>{
 const {card,calls,plan}=setup(),service=card.service;card.service=async(...a)=>{if(a[0]===plan[1].ids[1])throw Error('Connessione interrotta');return service(...a)};
 await assert.rejects(card.vacationApply(plan),/Salvati 1\/3/);assert.ok(calls.every(c=>!JSON.parse(c.value).enabled));
});
test('capability and temperature mismatch block all selected devices',async()=>{
 const {card,calls,plan,states}=setup();states['cover.demo'].attributes.supported_features=3;
 await assert.rejects(card.vacationApply(plan),/non supportata/);assert.equal(calls.length,0);
 states['cover.demo'].attributes.supported_features=15;plan[2].slots=[['08:00',31]];
 await assert.rejects(card.vacationApply(plan),/Temperatura/);assert.equal(calls.length,0);
});
test('discovery is project-scoped, includes other cards and excludes ambiguous entities',()=>{
 const {card,put}=setup();assert.equal(card.vacationTargets().length,3);
 put('input_text.foreign',{e:'light.foreign',p:'other'},{friendly_name:'NM target input_text.other'});assert.equal(card.vacationTargets().length,3);
 put('input_text.duplicate',{e:'light.demo',p:'demo'},{friendly_name:'NM target input_text.c0'});assert.equal(card.vacationTargets().length,2);
});
test('empty vacation allows suspension, solar and duplicate times are validated',()=>{
 const {c,states}=setup(),validate=c.window.NMVacation.validateSlots;
 validate([],states['light.demo']);validate([['sunset:-15','on']],states['light.demo']);
 assert.throws(()=>validate([['08:00','on'],['08:00','off']],states['light.demo']),/duplicato/);
 assert.throws(()=>validate([['sunrise:181','open']],states['cover.demo']),/non valido/);
});
