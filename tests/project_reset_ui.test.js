const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('reset UI requires preview, downloaded backup, exact phrase and checked consent before apply',async()=>{
 const calls=[],errors=[],downloads=[];let handler,pending=Promise.resolve(),modalTitle='';
 const fields={'#reset-consent':{checked:false},'#reset-phrase':{value:''}};
 const review={project:'a'.repeat(64),fingerprint:'review',phrase:'AZZERA aaaaaaaaaaaa',files:['nm_knx_widget_layout.json'],helpers:[],dashboards:[],candidates:[],preserved:[],blockers:[],legacy_dashboards:[]};
 const context={busy:false,snapshot:{project:review.project},esc:String,$:s=>fields[s],
  work:fn=>{pending=fn().catch(e=>errors.push(e.message));},modal:title=>{modalTitle=title;},
  api:async(path,data)=>{calls.push(data);if(data.operation==='status')return {pending:null};if(data.operation==='preview')return review;if(data.operation==='backup')return {...review,backup_id:'b'.repeat(32),sha256:'checked'};if(data.operation==='apply')return {complete:true,message:'Progetto azzerato',preserved:[]};throw Error('Unexpected operation');},
  fetch:async()=>({ok:true,blob:async()=>({size:123})}),URL:{createObjectURL:()=> 'blob:local',revokeObjectURL:()=>{}},setTimeout:()=>{},
  document:{addEventListener:(type,fn)=>{handler=fn;},querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>({click(){downloads.push(this.download);}})}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../nm_bridge/control-reset.js'),'utf8'),context);
 const click=async dataset=>{handler({target:{closest:()=>({dataset})}});await pending;};
 await click({resetProject:'1'});assert.match(modalTitle,/Anteprima/);
 await click({resetBackup:'1'});assert.match(modalTitle,/Conferma/);
 await click({resetApply:'1'});assert.match(errors.pop(),/Scarica prima/);
 await click({resetDownload:'1'});assert.equal(downloads.length,1);
 await click({resetApply:'1'});assert.match(errors.pop(),/frase esatta/);
 assert.equal(calls.filter(c=>c.operation==='apply').length,0);
 fields['#reset-consent'].checked=true;fields['#reset-phrase'].value=review.phrase;
 await click({resetApply:'1'});assert.equal(calls.filter(c=>c.operation==='apply').length,1);
 assert.equal(calls.at(-1).fingerprint,'review');assert.equal(calls.at(-1).backup_downloaded,true);
 assert.equal(modalTitle,'Progetto NM azzerato');
});
