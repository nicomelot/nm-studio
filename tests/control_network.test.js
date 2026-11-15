const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../nm_bridge/control-network.js'),'utf8');
const ctx=vm.createContext({document:{addEventListener(){}},snapshot:{network_states:{}}});vm.runInContext(source,ctx);
test('port status distinguishes telemetry loss, link state and speed, never PoE',()=>{
 const p={network:{entity:'sensor.port',mode:'speed'}};
 for(const [state,label] of [['1000','Collegata'],['0','Scollegata'],['unavailable','Non disponibile'],['-1','Non disponibile'],['','Non disponibile'],['NaN','Non disponibile']])assert.equal(ctx.networkStatus(p,{'sensor.port':{state}}).label,label);
 assert.equal(ctx.networkStatus(p,{}).label,'Non disponibile');p.network.mode='link';assert.equal(ctx.networkStatus(p,{'sensor.port':{state:'off'}}).label,'Scollegata');
 assert.match(ctx.networkStatus({network:{simulation:'up'}}).label,/SIMULATO/);
});
test('port identity isolates simulation and racks but survives switch renaming with HA id',()=>{
 const p={technical:{rack:'A',switch:'Switch'},network:{switch_id:'stable'}};
 const k=ctx.networkKey(p);p.technical.switch='New';assert.equal(ctx.networkKey(p),k);p.network.simulation='up';assert.notEqual(ctx.networkKey(p),k);
 assert.notEqual(ctx.networkKey({technical:{rack:'A',switch:'S'}}),ctx.networkKey({technical:{rack:'B',switch:'S'}}));
});
