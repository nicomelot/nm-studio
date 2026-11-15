const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const ctx=vm.createContext({document:{addEventListener(){}},window:{addEventListener(){}}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nm_bridge/control-templates.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../nm_bridge/control-pipes.js'),'utf8'),ctx);
const models=vm.runInContext('PLANT_MODELS',ctx),create=ctx.instantiatePlant;
let sequence=0;const id=()=>`test_${++sequence}`;
test('each plant model creates independent editable points with no implicit device links',()=>{
 for(const model of models){const source={...model,background:'data:image/png;base64,test'},original=JSON.stringify(source);
 const a=create(source,'First',[],[],id),b=create(source,'Second',[],[],id);
 assert.equal(a.kind,'schematic');assert.equal(a.points.length,model.points.length);
 assert.equal(new Set([a.id,b.id,...a.points.map(p=>p.id),...b.points.map(p=>p.id)]).size,2+2*a.points.length);
 assert.ok(a.points.every(p=>p.device===''&&p.x>0&&p.x<100&&p.y>0&&p.y<100));
 a.points[0].label='Changed';assert.notEqual(a.points[0].label,b.points[0].label);assert.equal(JSON.stringify(source),original);
 }
});
test('reusing a saved plant clears original links and accepts only explicit project bindings',()=>{
 const source={background:'image',points:[{id:'old',device:'old-device',symbol:'temperature',label:'Supply',x:30,y:40,temp_low:35,temp_high:65}]};
 const devices=[{id:'sensor',entity_id:'sensor.test',type:'temperature'},{id:'lamp',entity_id:'light.test',type:'light'}];
 assert.equal(create(source,'Copy',[],devices,id).points[0].device,'');
 const p=create(source,'Copy',['sensor'],devices,id).points[0];
 assert.equal(p.device,'sensor');assert.equal(p.temp_low,35);assert.equal(p.temp_high,65);assert.notEqual(p.id,'old');
 assert.throws(()=>create(source,'Copy',['foreign'],devices,id));assert.throws(()=>create(source,'Copy',['lamp'],devices,id));assert.throws(()=>create(source,' ',[],devices,id));
 assert.equal(source.points[0].device,'old-device');
});
test('model backgrounds are drawn locally and exported as PNG for the existing archive',()=>{
 const commands=[];ctx.document.createElement=()=>({getContext:()=>new Proxy({}, {get:(_,key)=>(...args)=>commands.push([key,...args]),set:()=>true}),toDataURL:type=>type});
 for(const model of models)assert.equal(ctx.plantBackground(model),'image/png');
 assert.ok(commands.some(c=>c[0]==='lineTo'));assert.ok(commands.some(c=>c[0]==='fillText'));
});

test('pipe geometry is bounded, orthogonal and copied independently between models',()=>{
 assert.equal(JSON.stringify(ctx.pipeXY({clientX:500,clientY:-3},{left:0,top:0,width:100,height:100})),'[100,0]');
 const original=[[10,10]];assert.equal(JSON.stringify(ctx.pipeAppend(original,[80,50],true)),'[[10,10],[80,10],[80,50]]');assert.equal(original.length,1);
 const a=create(models[0],'A',[],[],id),b=create(models[0],'B',[],[],id);assert.ok(a.pipes.length);assert.notEqual(a.pipes[0].id,b.pipes[0].id);a.pipes[0].xy[0][0]=99;assert.notEqual(a.pipes[0].xy[0][0],b.pipes[0].xy[0][0]);
});
