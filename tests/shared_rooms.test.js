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
