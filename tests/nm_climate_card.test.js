const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../nm_bridge/nm-climate-card.js'),'utf8');
const ctx=vm.createContext({HTMLElement:class{},customElements:{get:()=>true},window:{}});vm.runInContext(source,ctx);
test('week rejects invalid, duplicate and unsupported setpoints before any service call',()=>{
 const week=Array.from({length:7},()=>[['08:00',21],['06:30',18]]);
 assert.equal(ctx.ncValidate(week,7,30)[0][0][0],'06:30');
 for(const rows of [[['24:00',21]],[['08:00',21],['08:00',22]],[['08:00',null]],[['08:00',100]],[['08:00',21.2]]]){week[0]=rows;assert.throws(()=>ctx.ncValidate(week,7,30,.5))}
 assert.throws(()=>ctx.ncValidate(Array.from({length:7},()=>[]),7,30));
});
test('missing day is an empty editable draft and values are escaped',()=>{
 assert.equal(ctx.ncWeek({}, {days:['input_text.x']})[0].length,0);
 assert.equal(vm.runInContext('ncEscape("<script>")',ctx), '&lt;script&gt;');
 assert.ok(!source.includes('SUPERVISOR_TOKEN'));assert.ok(!source.includes('hassio/'));
});
test('new text helpers accept initial writes, offline helpers and unknown climates remain blocked',async()=>{
 const service=vm.runInContext('NMClimateCard.prototype.service',ctx),calls=[];
 const card={available:()=>false,state:()=>({state:'unknown'}),_hass:{callService:async(...a)=>calls.push(a)}};
 await service.call(card,'input_text.week','set_value',{value:'{}'});
 assert.equal(calls.length,1);
 await assert.rejects(service.call(card,'climate.demo','set_temperature',{temperature:22}),/non disponibile/);
 card.state=()=>({state:'unavailable'});
 await assert.rejects(service.call(card,'input_text.week','set_value',{value:'{}'}),/non disponibile/);
 assert.equal(calls.length,1);
});
