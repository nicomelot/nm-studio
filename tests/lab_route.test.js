const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
test('laboratory is explicitly reachable and unavailable without an imported project',async()=>{
 const html=fs.readFileSync('nm_bridge/index.html','utf8');
 assert.match(html,/data-page="lab"/);assert.match(html,/lab:labPage/);assert.match(html,/if\(page==='lab'\)wireLabPage\(\)/);
 let calls=0;const status={};const ctx={etsData:null,page:'lab',$:()=>status,wireVirtualLab:()=>calls++};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nm_bridge/project_ui.js','utf8'),ctx);
 await ctx.wireLabPage();assert.equal(calls,0);assert.match(status.textContent,/Nessun progetto/);
 ctx.etsData={project_key:'a'.repeat(64)};await ctx.wireLabPage();assert.equal(calls,1);
 ctx.page='ets';await ctx.wireLabPage();assert.equal(calls,1);
});
