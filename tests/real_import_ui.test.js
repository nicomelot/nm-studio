const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('nm_bridge/project_ui.js','utf8');
function fixture(fail=false){
 const elements={'project-label':{value:'Casa'},'project-continue':{disabled:false},'import-status':{textContent:''}};
 const host={insertAdjacentHTML(){}};elements['ets-progress']={closest:()=>host};
 const calls=[];
 const c={$:id=>elements[id],escapeHTML:String,etsRoomPaths:()=>['Casa / Sala'],
  etsData:{session_token:'token',session_revision:'old',suggestions:[{kind:'dimmer'}],lab_candidates:[{command:'1/1/0',selected:true}]},
  api:async(path,opts)=>{calls.push([path,opts]);if(fail)throw Error('Salvataggio fallito');return path==='projects'?{projects:[]}:{revision:'new'};},
  setPage:page=>c.destination=page};
 vm.createContext(c);vm.runInContext(source,c);c.wireImportSummary();return {c,elements,calls};
}
test('real import persists project then goes to review without virtual provisioning',async()=>{
 const {c,elements,calls}=fixture();await elements['project-continue'].onclick();
 assert.equal(c.destination,'widgets');assert.equal(c.etsData.session_revision,'new');
 assert.deepEqual(calls.map(c=>c[0]),['projects/save','projects']);
 const body=JSON.parse(calls[0][1].body);assert.equal(body.reviews[0].selected,false);
 assert.equal(body.expected_revision,'old');
});
test('failed project save stays on import and permits retry',async()=>{
 const {c,elements}=fixture(true);await elements['project-continue'].onclick();
 assert.equal(c.destination,undefined);assert.equal(elements['project-continue'].disabled,false);
 assert.match(elements['import-status'].textContent,/Salvataggio fallito/);
});

