const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function context(){const c=vm.createContext({HTMLElement:class{},customElements:{get:()=>true},window:{},structuredClone,crypto:require('node:crypto').webcrypto,setInterval,clearInterval});
 for(const file of ['nm-climate-card.js','nm-calendar.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../nm_bridge',file),'utf8'),c);return c}
test('calendar rejects impossible dates, reversed ranges and duplicate holidays',()=>{
 const c=context(),v=c.window.NMCalendar.validate;
 assert.equal(v({kind:'v',start:'2026-12-24',end:'2027-01-06'}).end,'2027-01-06');
 for(const meta of [{kind:'v',start:'2026-02-30',end:'2026-03-01'},{kind:'v',start:'2026-12-26',end:'2026-12-25'},{kind:'f',dates:['2026-12-25','2026-12-25']},{kind:'f',dates:[]}])assert.throws(()=>v(meta));
});
test('saving exception writes only its two helpers and starts disabled',async()=>{
 const c=context(),save=vm.runInContext('NMClimateCard.prototype.saveProfile',c),calls=[];
 const card={profileDraft:{ids:['input_text.vc','input_text.vs']},profileValues:()=>({meta:{kind:'v',start:'2026-12-24',end:'2027-01-06'},slots:[['08:00',19]]}),checkProfileBase(){},service:async(...a)=>calls.push(a),shadowRoot:{querySelector:()=>({})},message(){}};
 await save.call(card);assert.equal(calls.length,2);assert.deepEqual(calls.map(c=>c[0]),['input_text.vc','input_text.vs']);
 const meta=JSON.parse(calls[0][2].value),body=JSON.parse(calls[1][2].value);assert.equal(meta.enabled,false);assert.equal(meta.v,body.v);
});
test('concurrent exception edit during confirmation blocks activation',async()=>{
 const c=context(),enable=vm.runInContext('NMClimateCard.prototype.enableProfile',c);let checks=0,writes=0;
 const saved={kind:'v',start:'2026-12-24',end:'2027-01-06',v:'a'.repeat(32),enabled:false},slots=[['08:00',19]];
 const card={profileDraft:{kind:'v',ids:['input_text.vc','input_text.vs'],base:[JSON.stringify(saved),JSON.stringify({v:saved.v,s:slots})]},checkProfileBase(){if(++checks===2)throw Error('Profilo modificato altrove')},profileValues:()=>({meta:{kind:'v',start:saved.start,end:saved.end},slots}),approve:async()=>true,service:async()=>writes++};
 await assert.rejects(enable.call(card,true),/modificato altrove/);assert.equal(writes,0);
});
