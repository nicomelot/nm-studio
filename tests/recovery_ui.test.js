const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('nm_bridge/recovery_ui.js','utf8');
function fixture(){
 const context={
  etsData:{addresses:[{address:'1/1/1',name:'L1',linked:true},
   {address:'1/1/8',name:'L5',linked:true},{address:'1/6/8',name:'Feedback L5',linked:true},
   {address:'1/1/9',name:'L6',linked:true}],
   suggestions:[{name:'L5',kind:'light',command:'1/1/8',feedback:'1/6/8'}],
   room_matches:[{command:'1/1/8',room:'Casa / Terra / Ufficio'}]},
  widgetDrafts:[{kind:'light',name:'Nome personalizzato',room:'Studio',fields:{command:'1/1/1'},entity_id:'light.l1'}],
  widgetFields:{light:[['command'],['feedback']],dimmer:[['command'],['brightness']],cover:[['command'],['stop'],['position'],['feedback']]},
  widgetDirty:false,structureRooms:()=>['Casa / Terra / Ufficio'],resolveRoomAlias:s=>s,
  newWidget:(kind,name,fields,source,room)=>({kind,name,fields,source,room,entity_id:''})
 };
 context.linkedGA=ga=>context.etsData.addresses.some(a=>a.address===ga&&a.linked)?ga:'';
 vm.createContext(context);vm.runInContext(source,context);return context;
}
test('saved project exposes missing L5 and preserves existing real bindings',()=>{
 const c=fixture(),before=JSON.stringify(c.widgetDrafts[0]);
 const r=c.recoveryReport(c.etsData,c.widgetDrafts);
 assert.equal(r.missing.length,1);assert.equal(r.missing[0].name,'L5');
 assert.equal(r.other.length,1);assert.equal(r.other[0].name,'L6');
 assert.equal(c.addRecoveredWidget('1/1/8','light'),true);
 assert.equal(JSON.stringify(c.widgetDrafts[0]),before);
 assert.equal(c.widgetDrafts[1].entity_id,'');
 assert.equal(c.widgetDrafts[1].fields.feedback,'1/6/8');
 assert.equal(c.widgetDrafts[1].room,'Casa / Terra / Ufficio');
 assert.equal(c.widgetDirty,true);
 assert.equal(c.addRecoveredWidget('1/1/8','light'),false);
 assert.equal(c.recoveryReport(c.etsData,c.widgetDrafts).missing.length,0);
});
test('unclassified GA requires explicit manual type and does not invent feedback',()=>{
 const c=fixture();assert.equal(c.addRecoveredWidget('1/1/9','light'),false);
 assert.equal(c.addRecoveredWidget('1/1/9','light',false),true);
 assert.deepEqual(Object.keys(c.widgetDrafts[1].fields),['command']);
 assert.equal(c.widgetDrafts[1].room,'Da assegnare');
 assert.equal(c.addRecoveredWidget('9/9/9','light',false),false);
});
test('conflicting suggestions and shared auxiliary GA require manual review',()=>{
 const c=fixture();c.etsData.suggestions.push({name:'D5',kind:'dimmer',command:'1/1/8'});
 assert.equal(c.recoveryReport(c.etsData,c.widgetDrafts).missing[0].ambiguous,true);
 assert.equal(c.addRecoveredWidget('1/1/8','light'),false);
 c.etsData.suggestions.pop();c.widgetDrafts[0].fields.feedback='1/1/8';
 assert.equal(c.recoveryReport(c.etsData,c.widgetDrafts).missing[0].shared,true);
 assert.equal(c.addRecoveredWidget('1/1/8','light'),false);
});
test('unlinked GA never enters automatic recovery; removed GA stays visible',()=>{
 const c=fixture();c.etsData.addresses[1].linked=false;
 assert.equal(c.addRecoveredWidget('1/1/8','light'),false);
 c.etsData.addresses.shift();
 const r=c.recoveryReport(c.etsData,c.widgetDrafts);
 assert.equal(r.stale.length,1);assert.equal(c.widgetDrafts[0].entity_id,'light.l1');
});
test('cover recovery does not treat a generic feedback as verified position feedback',()=>{
 const c=fixture();c.etsData.suggestions[0].kind='cover';
 assert.equal(c.addRecoveredWidget('1/1/8','cover'),true);
 assert.equal(c.widgetDrafts[1].fields.feedback,undefined);
});
test('recovery script is served, packaged and used in the guided widgets page',()=>{
 assert.match(fs.readFileSync('nm_bridge/bridge.py','utf8'),/path == "\/recovery_ui.js"/);
 assert.match(fs.readFileSync('nm_bridge/Dockerfile','utf8'),/COPY recovery_ui.js \/app\/recovery_ui.js/);
 const html=fs.readFileSync('nm_bridge/index.html','utf8');
 assert.match(html,/<script src="recovery_ui.js"><\/script>/);
 assert.match(html,/wireWidgetPersistence\(\);wireRecovery\(\)/);
});
