const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function fixture(){
 const context=vm.createContext({});
 vm.runInContext(fs.readFileSync('nm_bridge/recovery_ui.js','utf8'),context);
 const widgets=[
  {name:'Clima',kind:'climate',room:'Studio',entity_id:'climate.studio',fields:{command:'1/0/2',temperature:'1/0/14'}},
  {name:'Reset filtro',kind:'button',profile:'filter_reset',room:'Studio',fields:{command:'1/0/18'}},
  {name:'Luce',kind:'light',room:'Ingresso',visible:false,fields:{command:'2/0/1'}}
 ];
 return {context,widgets};
}
test('reorder in both directions keeps identity, GA, profiles and HA bindings',()=>{
 const {context:c,widgets:w}=fixture(),before=w.map(x=>JSON.stringify(x)),first=w[0];
 assert.equal(c.placeWidget(w,0,2),true);assert.equal(w[2],first);
 assert.equal(JSON.stringify(w[2]),before[0]);assert.equal(JSON.stringify(w[0]),before[1]);
 assert.equal(c.placeWidget(w,2,0),true);assert.deepEqual(w.map(x=>JSON.stringify(x)),before);
});
test('room move and undo restore original order without losing subsequent name edits',()=>{
 const {context:c,widgets:w}=fixture(),snapshot=c.rememberWidgetPlacement(w);
 assert.equal(c.placeWidget(w,0,1,'Ingresso'),true);snapshot.forEach(x=>x.afterRoom=x.widget.room);
 w[1].name='Nome modificato';assert.equal(c.restoreWidgetPlacement(w,snapshot),true);
 assert.equal(w[0].name,'Nome modificato');assert.equal(w[0].room,'Studio');
 assert.equal(w[0].entity_id,'climate.studio');assert.equal(w[1].profile,'filter_reset');
});
test('invalid placements and no-op do not mutate drafts',()=>{
 const {context:c,widgets:w}=fixture(),before=JSON.stringify(w);
 for(const args of [[-1,1],[0,3],[0,0],[0,1,''],[0,1,null],[0.5,1]])assert.equal(c.placeWidget(w,...args),false);
 assert.equal(JSON.stringify(w),before);
});
test('undo is invalid after import, removal, addition or another room edit',()=>{
 const {context:c,widgets:w}=fixture(),snapshot=c.rememberWidgetPlacement(w);
 assert.equal(c.restoreWidgetPlacement(w.map(x=>({...x})),snapshot),false);
 assert.equal(c.restoreWidgetPlacement(w.slice(1),snapshot),false);
 assert.equal(c.restoreWidgetPlacement([...w,{name:'Nuova'}],snapshot),false);
 w[1].room='Nuova stanza';assert.equal(c.restoreWidgetPlacement(w,snapshot),false);
 assert.equal(w[1].room,'Nuova stanza');
});
