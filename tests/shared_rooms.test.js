const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('nm_bridge/index.html','utf8');
function get(name,next){const start=html.indexOf('function '+name+'(');return html.slice(start,html.indexOf('function '+next+'(',start+1));}
function harness(){
 const ctx={structureDraft:[{id:'b',parent:null,name:'Casa',type:'building'},{id:'f',parent:'b',name:'Terra',type:'floor'},{id:'r',parent:'f',name:'Ufficio',type:'room'}],structureAliases:{},etsData:{lab_candidates:[{room:'Casa / Terra / Ufficio',command:'1/0/0'},{room:'Casa / Primo / Ufficio',command:'1/0/1'}]},widgetDrafts:[{room:'Casa / Terra / Ufficio'}],widgetRooms:[],structureDirty:false,widgetDirty:false,structureRooms:()=>[]};
 vm.createContext(ctx);vm.runInContext(get('nodePath','structureRooms')+get('syncGuidedRooms','alignLegacyGuidedRooms')+get('refreshEditableRooms','proposeWidgets'),ctx);return ctx;
}
test('rename updates guided candidates by full path and leaves namesakes untouched',()=>{
 const c=harness(),old=new Map(c.structureDraft.map(n=>[n.id,c.nodePath(n.id)]));c.structureDraft[2].name='Studio';c.refreshEditableRooms(old);
 assert.equal(c.etsData.lab_candidates[0].room,'Casa / Terra / Studio');assert.equal(c.etsData.lab_candidates[1].room,'Casa / Primo / Ufficio');assert.equal(c.widgetDrafts[0].room,'Casa / Terra / Studio');
 assert.equal(c.structureAliases['Casa / Terra / Ufficio'],'Casa / Terra / Studio');
});
test('floor renames compose aliases so original imported paths still resolve',()=>{
 const c=harness();let old=new Map(c.structureDraft.map(n=>[n.id,c.nodePath(n.id)]));c.structureDraft[2].name='Studio';c.refreshEditableRooms(old);
 old=new Map(c.structureDraft.map(n=>[n.id,c.nodePath(n.id)]));c.structureDraft[1].name='Ingresso';c.refreshEditableRooms(old);
 assert.equal(c.structureAliases['Casa / Terra / Ufficio'],'Casa / Ingresso / Studio');assert.equal(c.etsData.lab_candidates[0].room,'Casa / Ingresso / Studio');
});

test('ETS rooms directly under building retain their path without fictitious floor',()=>{
 const c={};vm.createContext(c);
 vm.runInContext(get('nodePath','structureRooms')+get('buildEditableStructure','syncGuidedRooms'),c);
 const nodes=c.buildEditableStructure([{type:'Building',name:'Casa',path:'Casa'},
  {type:'Room',name:'Sala',path:'Casa / Sala'},
  {type:'DistributionBoard',name:'Quadro',path:'Casa / Sala / Quadro'}]);
 assert.equal(nodes.length,2);
 assert.equal(c.nodePath(nodes[1].id,nodes),'Casa / Sala');
});

test('a reimport adds an ETS climate room under a renamed saved floor',()=>{
 const original=[
  {id:'nm_1',parent:null,type:'building',name:'Casa',active:true,source:'ets'},
  {id:'nm_2',parent:'nm_1',type:'floor',name:'Ingresso',active:true,source:'ets'},
  {id:'nm_3',parent:'nm_2',type:'room',name:'Studio',active:true,source:'ets'},
 ];
 const oldWidget={type:'climate',name:'Termostato esistente',room:'Casa / Ingresso / Studio',
  fields:{command:'2/1/2'},entity_id:'climate.studio'};
 const c={savedWidgetLayout:{project:'p',structure:original,rooms:[oldWidget.room],widgets:[oldWidget],
  room_aliases:{'Casa / Terra':'Casa / Ingresso','Casa / Terra / Ufficio':'Casa / Ingresso / Studio'}},
  etsData:{project_key:'p',
   building:[{type:'Building',name:'Casa',path:'Casa'},
    {type:'Floor',name:'Terra',path:'Casa / Terra'},
    {type:'Room',name:'Ufficio',path:'Casa / Terra / Ufficio'},
    {type:'Room',name:'Sala nuova',path:'Casa / Terra / Sala nuova'}],
   addresses:[{address:'2/1/2',name:'Studio',linked:true},{address:'2/2/2',name:'Sala nuova',linked:true}],
   suggestions:[{kind:'climate',name:'Sala nuova',command:'2/2/2'}],
   room_matches:[{command:'2/2/2',room:'Casa / Terra / Sala nuova'}]},
  widgetFields:{climate:[['command']]},newWidget:(kind,name,fields,source,room,entity_id)=>({kind,name,fields,room,entity_id}),
  linkedGA:()=>'',widgetDrafts:[],widgetSeq:0,widgetDirty:false,structureDirty:false,widgetRooms:[],structureDraft:[],structureAliases:{}};
 vm.createContext(c);
 vm.runInContext(get('nodePath','widgetGAOptions')+fs.readFileSync('nm_bridge/recovery_ui.js','utf8'),c);
 c.proposeWidgets();
 assert.equal(c.structureDraft.length,4);
 assert.equal(c.structureDraft[3].parent,'nm_2');
 assert.equal(c.widgetDrafts.length,2);
 assert.equal(c.widgetDrafts[0].entity_id,'climate.studio');
 assert.equal(c.widgetDrafts[0].room,oldWidget.room);
 assert.equal(c.widgetDrafts[1].room,'Casa / Ingresso / Sala nuova');
 assert.equal(c.structureDirty,true);
 assert.equal(original.length,3);
 c.savedWidgetLayout={...c.savedWidgetLayout,structure:c.structureDraft,room_aliases:c.structureAliases};
 c.proposeWidgets();
 assert.equal(c.structureDraft.length,4);
 assert.equal(c.widgetDrafts.length,2);
 assert.equal(c.structureDirty,false);
});
