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


test('progression requires names, rooms and mandatory commands, not an existing HA entity',()=>{
 const c=fixture();c.widgetFields.light=[['command','Comando','DPT 1',true],['feedback','Stato','DPT 1',false]];
 const draft={kind:'light',name:'L5',room:'Esterno',fields:{command:'1/1/8'},entity_id:''};
 assert.equal(c.widgetFlowIssues([draft]).length,0);
 assert.match(c.widgetFlowIssues([{...draft,room:'Da assegnare'}])[0].message,/stanza/);
 assert.match(c.widgetFlowIssues([{...draft,fields:{}}])[0].message,/Comando/);
 assert.match(c.widgetFlowIssues([{...draft,name:''}])[0].message,/nome/);
 assert.equal(c.widgetFlowIssues([]).length,1);
});
test('duplicate commands block progression without changing drafts or bindings',()=>{
 const c=fixture();const drafts=[...c.widgetDrafts,{...c.widgetDrafts[0],name:'Duplicato'}];
 const before=JSON.stringify(drafts);
 assert.match(c.widgetFlowIssues(drafts)[0].message,/duplicato/);
 assert.equal(JSON.stringify(drafts),before);
});


function updateHarness(){
 const ids={}, calls=[];
 const element=()=>({disabled:false,value:'',textContent:'',innerHTML:'',before(){},addEventListener(name,fn){this[name]=fn;}});
 const $=id=>ids[id]??=element();
 const preview={url_path:'nm-studio-test',expected_current:'old',expected_fingerprint:'new',dashboard:{views:[]},previous_dashboard:{views:[{title:'Old'}]},changed:true,old_views:1,new_views:2,notice:'Backup'};
 const c={$,document:{createElement:element},widgetDirty:false,structureDirty:false,nmDashboardDraft:{dashboard:{views:[]}},confirm:()=>true,
 api:async(path,opts)=>{calls.push({path,body:JSON.parse(opts.body)});return path.endsWith('update-preview')?preview:{updated:true,backup:'test.json'};}};
 $('dash-publish-path').value='nm-studio-test';$('dash-code').value=JSON.stringify(c.nmDashboardDraft.dashboard,null,2);
 vm.createContext(c);vm.runInContext(source,c);c.wireRealDashboardUpdate();
 return {c,ids,calls};
}
test('real dashboard update requires comparison and sends both reviewed fingerprints',async()=>{
 const h=updateHarness();
 await h.ids['real-update-apply'].onclick();assert.equal(h.calls.length,0);
 await h.ids['real-update-preview'].onclick();assert.equal(h.ids['real-update-apply'].disabled,false);
 await h.ids['real-update-apply'].onclick();
 assert.equal(h.calls[1].path,'dashboard/update');assert.equal(h.calls[1].body.expected_current,'old');
 assert.equal(h.calls[1].body.expected_fingerprint,'new');assert.equal(h.ids['real-update-apply'].disabled,true);
});
test('changing preview or cancelling confirmation prevents update',async()=>{
 const h=updateHarness();await h.ids['real-update-preview'].onclick();
 h.c.confirm=()=>false;await h.ids['real-update-apply'].onclick();assert.equal(h.calls.length,1);
 h.ids['dash-publish-path'].input();h.c.confirm=()=>true;
 await h.ids['real-update-apply'].onclick();assert.equal(h.calls.length,1);
 assert.equal(h.ids['real-update-apply'].disabled,true);
});

test('dimmer recovery preserves customer labels, rooms, links and filled fields',()=>{
 const c=fixture();
 c.etsData.suggestions.push({kind:'dimmer',command:'1/1/1',brightness:'1/1/9'});
 assert.equal(c.recoverableUpgrades(c.etsData,c.widgetDrafts).length,1);
 assert.equal(c.upgradeRecoveredDimmer(0),true);
 assert.equal(c.widgetDrafts[0].kind,'dimmer');
 assert.equal(c.widgetDrafts[0].name,'Nome personalizzato');
 assert.equal(c.widgetDrafts[0].entity_id,'light.l1');
 assert.equal(c.widgetDrafts[0].room,'Studio');
 assert.equal(c.widgetDrafts[0].fields.brightness,'1/1/9');
 assert.equal(c.upgradeRecoveredDimmer(0),false);
});

test('import automatically adds recognized functions and upgrades dimmers without duplicates',()=>{
 const c=fixture();c.widgetDrafts[0].visible=false;
 c.etsData.suggestions.push({kind:'dimmer',command:'1/1/1',brightness:'1/1/9'});
 const first=c.reconcileRecognizedFunctions();
 assert.equal(first.added,1);assert.equal(first.upgraded,1);
 assert.equal(c.widgetDrafts.length,2);assert.equal(c.widgetDrafts[0].visible,false);
 assert.equal(c.widgetDrafts[0].entity_id,'light.l1');assert.equal(c.widgetDrafts[0].name,'Nome personalizzato');
 const next=c.reconcileRecognizedFunctions();assert.equal(next.added,0);assert.equal(next.upgraded,0);
});
test('automatic import leaves ambiguous and unlinked proposals for review',()=>{
 const c=fixture();c.etsData.suggestions.push({kind:'cover',command:'1/1/8'});
 c.etsData.addresses.find(a=>a.address==='1/1/9').linked=false;
 c.etsData.suggestions.push({kind:'light',command:'1/1/9'});
 assert.equal(c.reconcileRecognizedFunctions().added,0);
 assert.equal(c.widgetDrafts.length,1);
});
test('manual addition rerender preserves window scroll instead of focusing final card',()=>{
 const c=fixture();let scrolled=null,rendered=0;
 c.window={scrollY:245,scrollX:0,scrollTo:opts=>scrolled=opts};c.render=()=>rendered++;
 c.renderKeepingScroll();assert.equal(rendered,1);assert.equal(scrolled.top,245);
 assert.doesNotMatch(source,/render\(\);focusWidget\(widgetDrafts.length-1\)/);
});

test('reimport fills verified missing cover stop but preserves existing override and identity',()=>{
 const c=fixture();c.widgetDrafts[0].kind='cover';c.widgetDrafts[0].visible=false;
 c.etsData.suggestions=[{kind:'cover',command:'1/1/1',stop:'1/1/9'}];
 c.reconcileRecognizedFunctions();assert.equal(c.widgetDrafts[0].fields.stop,'1/1/9');
 assert.equal(c.widgetDrafts[0].entity_id,'light.l1');assert.equal(c.widgetDrafts[0].visible,false);
 c.widgetDrafts[0].fields.stop='2/1/20';c.reconcileRecognizedFunctions();
 assert.equal(c.widgetDrafts[0].fields.stop,'2/1/20');
});

test('search converts an existing light to off-only preserving identity without duplicates',()=>{
 const c=fixture(),w=c.widgetDrafts[0];w.fields.feedback='1/1/1';w.visible=false;
 assert.equal(c.searchFunctionAddresses(c.etsData,'1/1/1')[0].name,'L1');
 assert.equal(c.searchFunctionAddresses(c.etsData,'feedback l5')[0].address,'1/6/8');
 assert.equal(c.prepareOffButton('1/1/1'),true);
 assert.equal(w.command_mode,'off_only');assert.equal(w.fields.feedback,'');
 assert.equal(w.entity_id,'light.l1');assert.equal(w.name,'Nome personalizzato');
 assert.equal(w.room,'Studio');assert.equal(w.visible,false);
 assert.equal(c.prepareOffButton('1/1/1'),true);assert.equal(c.widgetDrafts.length,1);
 c.etsData.suggestions.push({kind:'dimmer',name:'L1',command:'1/1/1',feedback:'1/1/1'});
 c.reconcileRecognizedFunctions();assert.equal(w.kind,'light');assert.equal(w.fields.feedback,'');
});
test('off-button search rejects known incompatible DPT and creates unknown GA only explicitly',()=>{
 const c=fixture();c.etsData.addresses[3].dpt='DPST-5-1';
 assert.equal(c.prepareOffButton('1/1/9'),false);
 assert.equal(c.prepareOffButton('1/1/8'),true);
 assert.equal(c.widgetDrafts[1].command_mode,'off_only');assert.equal(c.widgetDrafts[1].fields.feedback,'');
 assert.equal(c.prepareOffButton('9/9/9'),false);
});

test('KNX onboarding reads capabilities only and does not reconfigure an existing connection',async()=>{
 const c=fixture(),nodes=Object.fromEntries(['knx-prerequisite-status','knx-prerequisite-refresh','knx-prerequisite-setup'].map(k=>[k,{hidden:false,disabled:false,textContent:''}]));
 c.$=id=>nodes[id];const calls=[];let state={available:true,connected:true};
 c.api=async(path,options)=>{calls.push({path,options});return state;};
 await c.checkKnxPrerequisite();assert.equal(nodes['knx-prerequisite-setup'].hidden,true);
 assert.match(nodes['knx-prerequisite-status'].textContent,/connesso/);
 state={available:false,message:'Integrazione non disponibile'};
 await c.checkKnxPrerequisite();assert.equal(nodes['knx-prerequisite-setup'].hidden,false);
 assert.equal(nodes['knx-prerequisite-refresh'].disabled,false);
 assert.ok(calls.every(c=>c.path==='knx/panel-capability'&&!c.options));
 assert.match(c.knxPrerequisitePanel(),/config_flow\/[?]domain=knx/);
});
