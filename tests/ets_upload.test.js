const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('nm_bridge/index.html','utf8');
const helper=html.slice(html.indexOf('async function uploadETS('),html.indexOf('function wireETS(){'));

test('both ETS upload paths expose a password field and use shared transport',()=>{
 for(const id of ['ets-password','match-ets-password']){
  assert.ok(html.includes('type="password" id="'+id+'"'));
  assert.ok(html.includes("uploadETS(file,$('"+id+"'))"));
 }
});
test('UTF-8 password travels in bounded body and input is cleared',async()=>{
 const input={value:'prova-è-🔒'};let captured;
 const ctx={TextEncoder,Uint8Array,DataView,Blob,fetch:async(url,options)=>{
  assert.equal(input.value,'');captured=options;return {ok:true};
 }};
 vm.createContext(ctx);vm.runInContext(helper,ctx);
 await ctx.uploadETS(new Blob(['PKxx']),input);
 const bytes=new Uint8Array(await captured.body.arrayBuffer());
 const length=new DataView(bytes.buffer).getUint32(0);
 assert.equal(new TextDecoder().decode(bytes.slice(4,4+length)),'prova-è-🔒');
 assert.equal(new TextDecoder().decode(bytes.slice(4+length)),'PKxx');
 assert.equal(input.value,'');
 assert.deepEqual(Object.keys(captured.headers),['Content-Type']);
});
test('network failure also clears password',async()=>{
 const input={value:'secret'};
 const ctx={TextEncoder,Uint8Array,DataView,Blob,fetch:async()=>{throw Error('offline')}};
 vm.createContext(ctx);vm.runInContext(helper,ctx);
 await assert.rejects(ctx.uploadETS(new Blob(['PKxx']),input),/offline/);
 assert.equal(input.value,'');
});
