const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../nm_bridge/nm-floorplan-card.js'),'utf8');
const ctx=vm.createContext({HTMLElement:class{},customElements:{get:()=>true}});vm.runInContext(source,ctx);
test('fit respects both desktop and mobile viewport dimensions and preserves image proportions',()=>{
 for(const [w,h,r] of [[1500,800,1.2],[360,600,1.2],[800,500,.7]]){const s=ctx.nmFit(w,h,r,1);assert.ok(s.width<=w+.001);assert.ok(s.height<=h+.001);assert.ok(Math.abs(s.width/s.height-r)<.0001);assert.equal(ctx.nmFit(w,h,r,2).width,s.width*2)}
});
test('popup labels and notes are escaped and no service is invoked by opening a point',()=>{assert.equal(vm.runInContext('nmEscape("<img onerror=bad> & \\\"x\\\"")',ctx),'&lt;img onerror=bad&gt; &amp; &quot;x&quot;');assert.ok(!source.includes('callService'));assert.ok(source.includes('hass-more-info'));});
