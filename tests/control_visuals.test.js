const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const ctx=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../nm_bridge/control-visuals.js'),'utf8'),ctx);
const visual=ctx.visualState,device=(state,attributes={},type='light')=>({state,attributes,type,entity_id:type+'.test'});
test('pump animation follows actual activity and never a heat setpoint or unavailable state',()=>{
 assert.equal(visual('pump',device('on')).running,true);
 for(const s of ['off','unknown','unavailable'])assert.equal(visual('pump',device(s)).running,false);
 assert.equal(visual('pump',device('heat',{hvac_action:'idle'},'climate')).running,false);
 assert.equal(visual('pump',device('heat',{hvac_action:'heating'},'climate')).running,true);
 assert.equal(visual('pump',device('heat',{},'climate')).label,'Stato non interpretabile');
});
test('valve respects reported percentage and distinguishes travel direction',()=>{
 assert.equal(visual('valve',device('opening',{current_position:40},'cover')).label,'In apertura · 40%');
 assert.equal(visual('valve',device('closing',{current_position:60},'cover')).angle,54);
 assert.equal(visual('valve',device('on')).angle,90);
 assert.equal(visual('valve',device('off')).label,'Chiusa');
 assert.equal(visual('valve',device('unknown',{current_position:100})).tone,'offline');
 assert.equal(visual('valve',device('open',{current_position:-1},'cover')).label,'Aperta');
});
test('temperature colors support custom plant thresholds, Fahrenheit and missing readings',()=>{
 const temp=(s,unit='°C')=>device(s,{unit_of_measurement:unit},'temperature');
 assert.equal(visual('temperature',temp('17.9')).tone,'cold');
 assert.equal(visual('temperature',temp('18')).tone,'normal');
 assert.equal(visual('temperature',temp('28')).tone,'hot');
 assert.equal(visual('temperature',temp('50'),{temp_low:35,temp_high:65}).tone,'normal');
 assert.equal(visual('temperature',temp('86','°F')).tone,'hot');
 assert.equal(visual('temperature',temp('293.15','K')).tone,'normal');
 for(const s of ['',null,'NaN','Infinity','unavailable'])assert.equal(visual('temperature',temp(s)).tone,'offline');
 assert.equal(visual('temperature',temp('30','%')).tone,'neutral');
});
