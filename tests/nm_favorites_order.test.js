const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx=vm.createContext({HTMLElement:class{},customElements:{get:()=>true},window:{}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../nm_bridge/nm-climate-card.js'),'utf8'),ctx);
test('rank defaults preserve catalog order; moving first, last and between uses one rank',()=>{
 assert.equal(ctx.nfRank('0',3),4096);assert.equal(ctx.nfRank('unavailable',3),4096);
 assert.equal(ctx.nfRank('512',3),512);
 assert.equal(ctx.nfBetween(null,1024),512);assert.equal(ctx.nfBetween(1024,2048),1536);
 assert.equal(ctx.nfBetween(4096,null),5120);assert.equal(ctx.nfBetween(1,1),null);
 assert.equal(ctx.nfBetween(1,1.000001),null);
});
function fixture(){
 const cards=[1,2,3].map(i=>({type:'custom:nm-device-card',entity:'light.'+i,schedule:{commit:'input_text.nm_week_'+String(i).padStart(20,'0')+'_commit'}}));
 const proto=vm.runInContext('NMFavoritesCard.prototype',ctx),obj=Object.create(proto),states={},calls=[];
 obj.config={cards};for(const c of cards){states['input_boolean.nm_favorite_'+ctx.nfKey(c)]={state:'on'};states[obj.orderEntity(c)]={state:'0'};}
 obj._hass={states,callService:async(d,s,data)=>{calls.push({d,s,...data});states[data.entity_id]={state:String(data.value)};}};
 obj.shadowRoot={querySelectorAll:()=>[]};obj.status=t=>obj.message=t;obj.render=()=>{};
 return {obj,cards,calls};
}
test('reorder writes only moved preference, persists across new card instances and removal',async()=>{
 const {obj,cards,calls}=fixture();await obj.saveOrder(cards[2],[cards[2],cards[0],cards[1]].map(ctx.nfKey));
 assert.equal(calls.length,1);assert.equal(calls[0].d,'input_number');assert.equal(calls[0].value,512);
 assert.deepEqual(Array.from(obj.chosen(),c=>c.entity),['light.3','light.1','light.2']);
 const fresh=fixture().obj;fresh._hass=obj._hass;assert.equal(fresh.chosen()[0].entity,'light.3');
 obj._hass.states['input_boolean.nm_favorite_'+ctx.nfKey(cards[2])].state='off';assert.equal(obj.chosen().length,2);
 obj._hass.states['input_boolean.nm_favorite_'+ctx.nfKey(cards[2])].state='on';assert.equal(obj.chosen()[0].entity,'light.3');
});
test('cancel/no-op, unavailable helper and failed save never issue device commands',async()=>{
 const {obj,cards,calls}=fixture();await obj.saveOrder(cards[0],cards.map(ctx.nfKey));assert.equal(calls.length,0);
 obj._hass.states[obj.orderEntity(cards[0])].state='unavailable';await obj.saveOrder(cards[2],[cards[2],cards[0],cards[1]].map(ctx.nfKey));assert.equal(calls.length,0);
 obj._hass.states[obj.orderEntity(cards[0])].state='0';obj._hass.callService=async()=>{throw Error('offline')};
 await obj.saveOrder(cards[2],[cards[2],cards[0],cards[1]].map(ctx.nfKey));assert.match(obj.message,/non salvato: offline/);assert.equal(obj.busy,false);
});
const detachedTestSource=fs.readFileSync(require('node:path').join(__dirname,'../nm_bridge/nm-climate-card.js'),'utf8');
test('HA may initialize the collection while detached: child cards still receive configuration',async()=>{
 const children=[];const nodes=[];const host={append:()=>{}};const status={};
 const scope=vm.createContext({HTMLElement:class{},window:{},customElements:{get:()=>true,whenDefined:()=>Promise.resolve()},document:{createElement(name){const el={dataset:{},append:()=>{},setAttribute:()=>{},isConnected:false,setConfig(c){this.config=c;}};nodes.push(el);if(name==='nm-device-card')children.push(el);return el;}}});
 vm.runInContext(detachedTestSource,scope);
 const card={type:'custom:nm-device-card',entity:'light.demo',schedule:{commit:'input_text.nm_week_00000000000000000001_commit'}};
 const obj=Object.create(vm.runInContext('NMFavoritesCard.prototype',scope));obj.config={cards:[card]};obj.shadowRoot={querySelector:s=>s==='.cards'?host:status,querySelectorAll:()=>children};obj._hass={states:{'input_boolean.nm_favorite_00000000000000000001':{state:'on'},'input_number.nm_favorite_order_00000000000000000001':{state:'0'}}};
 obj.render();await Promise.resolve();assert.equal(children.length,1);assert.equal(children[0].config,card);assert.equal(children[0].hass,obj._hass);
});
