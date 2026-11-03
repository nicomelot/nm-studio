const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('nm_bridge/index.html','utf8');

function harness(){
 const ids={};
 const $=id=>ids[id]??=( {disabled:true,textContent:'',innerHTML:'',value:''} );
 const snapshot={project:'magazzino',widgets:[{name:'L5',type:'light',fields:{command:'1/1/8'},entity_id:'light.nm_lab_old'}]};
 const calls=[];
 const context={$,document:{querySelectorAll:()=>[]},setPage:p=>calls.push({page:p}),
  widgetDirty:false,structureDirty:false,matchData:null,matchSnapshot:null,matchSelections:{},
  savedWidgetLayout:snapshot,widgetDrafts:[{kind:'light',fields:{command:'1/1/8'},entity_id:'light.nm_lab_old'}],
  etsData:{project_key:'magazzino'},nmDashboardDraft:{},confirm:()=>true,message:()=>{},
  api:async(path,opts)=>{calls.push({path,opts});if(opts?.method==='POST')return {saved:1};return snapshot;}
 };
 vm.createContext(context);
 const start=html.indexOf('async function wireEntityMatching('),end=html.indexOf('function wireMissingHa(',start);
 vm.runInContext(html.slice(start,end),context);context.wireEntityMatching();
 context.matchData={proposals:[{}]};context.matchSnapshot=snapshot;context.matchSelections={0:'light.fuori_ufficio_l5'};
 return {context,ids,calls};
}

test('save all associations reuses real IDs and enables publication after persistence',async()=>{
 const h=harness();
 await h.ids['match-save'].onclick();
 const writes=h.calls.filter(c=>c.opts?.method==='POST');
 assert.equal(writes.length,1);assert.equal(writes[0].path,'knx/widgets');
 assert.equal(JSON.parse(writes[0].opts.body).widgets[0].entity_id,'light.fuori_ufficio_l5');
 assert.equal(h.context.widgetDrafts[0].entity_id,'light.fuori_ufficio_l5');
 assert.equal(h.ids['match-next'].disabled,false);
 h.ids['match-next'].onclick();assert.equal(h.calls.at(-1).page,'dashboard-export');
 assert.equal(h.calls.some(c=>c.path?.includes('lab/')||c.path?.includes('create-one')),false);
});

test('failed persistence never enables next and leaves widget drafts unchanged',async()=>{
 const h=harness();const api=h.context.api;
 h.context.api=async(path,opts)=>{if(opts)throw Error('Salvataggio fallito');return api(path,opts)};
 await h.ids['match-save'].onclick();
 assert.equal(h.ids['match-next'].disabled,true);
 assert.equal(h.context.widgetDrafts[0].entity_id,'light.nm_lab_old');
});

test('saving associations does not rewrite an open different project with the same GA',async()=>{
 const h=harness();h.context.etsData.project_key='altro';
 await h.ids['match-save'].onclick();
 assert.equal(h.context.widgetDrafts[0].entity_id,'light.nm_lab_old');
});
