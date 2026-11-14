'use strict';
// Presentation only: animation always follows reported state, never a command.
function visualState(symbol, d, point = {}) {
  const idle = {tone:'neutral', running:false, angle:0, label:'Non collegato'};
  if (!d) return idle;
  if (!d.entity_id || ['unknown','unavailable',''].includes(d.state)) return {...idle,tone:'offline',label:'Non disponibile'};
  const a=d.attributes||{};
  if (symbol==='temperature' || symbol==='climate') {
    const raw=d.type==='climate'?a.current_temperature:d.state;
    const value=typeof raw==='number'?raw:typeof raw==='string'&&raw.trim()!==''?Number(raw):NaN;
    const unit=a.unit_of_measurement||a.temperature_unit||'°C';
    if (!Number.isFinite(value)) return {...idle,tone:'offline',label:'Temperatura non disponibile'};
    const c=unit==='°F'?(value-32)*5/9:unit==='K'?value-273.15:value;
    if (!['°C','°F','K'].includes(unit)) return {...idle,label:`${value} ${unit} · unità non riconosciuta`};
    const low=point.temp_low??18, high=point.temp_high??28;
    const band=c<low?'cold':c>=high?'hot':'normal';
    return {...idle,tone:band,label:`${value} ${unit} · ${band==='cold'?'Bassa':band==='hot'?'Alta':'Intermedia'}`};
  }
  if (symbol==='pump') {
    const running=d.type==='climate'?['heating','cooling'].includes(a.hvac_action):d.state==='on';
    const stopped=d.type==='climate'?['idle','off'].includes(a.hvac_action)||d.state==='off':d.state==='off';
    return {...idle,running,tone:running?'active':'neutral',label:running?'In marcia':stopped?'Ferma':'Stato non interpretabile'};
  }
  if (symbol==='valve'||symbol==='cover') {
    const position=typeof a.current_position==='number'&&a.current_position>=0&&a.current_position<=100?a.current_position:null;
    const moving=['opening','closing'].includes(d.state);
    const open=['on','open'].includes(d.state),closed=['off','closed'].includes(d.state);
    const pct=position??(open?100:closed?0:null);
    const label=d.state==='opening'?'In apertura':d.state==='closing'?'In chiusura':pct===0?'Chiusa':pct===100?'Aperta':pct!==null?'Parziale':'Stato non interpretabile';
    return {...idle,tone:moving?'moving':pct>0?'active':'neutral',angle:pct===null?0:pct*.9,label:label+(position!==null?` · ${position}%`:'')};
  }
  return {...idle,tone:d.state==='on'?'active':'neutral',label:d.state==='on'?'Acceso':d.state==='off'?'Spento':d.state};
}
function controlIcon(symbol, v={}) {
  const icons={
    pump:'<path d="M2 20h6m16 0h6M16 8V3h9"/><circle cx="16" cy="18" r="10"/><g class="pump-rotor"><path d="M16 18c-7-1-7-7-2-7 4 0 4 4 2 7Zm0 0c4-6 9-3 6 1-2 3-5 2-6-1Zm0 0c3 6-2 9-5 5-2-3 1-5 5-5Z"/></g><circle cx="16" cy="18" r="2"/>',
    valve:'<path d="M2 10l14 7L2 24Zm28 0-14 7 14 7ZM16 17V6m-5 0h10"/><path class="valve-gate" d="M16 9v16"/>',
    temperature:'<path d="M12 19V7a4 4 0 0 1 8 0v12a7 7 0 1 1-8 0Z"/><path d="M16 10v13m8-13h3m-3 5h3"/><circle cx="16" cy="24" r="2"/>',
    boiler:'<rect x="6" y="3" width="20" height="25" rx="4"/><path d="M11 29v2m10-2v2M11 8h10m-5 4c1 4 6 5 4 9-3 5-11 0-5-5 0 2 1 3 2 3"/>',
    tank:'<ellipse cx="16" cy="6" rx="9" ry="4"/><path d="M7 6v20c0 5 18 5 18 0V6M7 16h18M3 11h4m18 12h4"/>',
    light:'<path d="M12 24h8m-7 4h6M10 17a9 9 0 1 1 12 0c-2 2-2 3-2 4h-8c0-1 0-2-2-4Z"/>',
    button:'<circle cx="16" cy="16" r="12"/><path d="M16 7v9m-5-7a8 8 0 1 0 10 0"/>',
    cover:'<path d="M4 28V4h24v24M8 8h16M8 12h16M8 16h16M8 20h16M16 24v4"/>',
    label:'<rect x="4" y="6" width="24" height="20" rx="4"/><path d="M10 13h12m-12 6h8"/>',
    home:'<path d="m3 15 13-11 13 11M7 13v15h18V13M13 28v-9h6v9"/>',
    devices:'<rect x="4" y="4" width="9" height="9" rx="2"/><rect x="19" y="4" width="9" height="9" rx="2"/><rect x="4" y="19" width="9" height="9" rx="2"/><rect x="19" y="19" width="9" height="9" rx="2"/>',
    rooms:'<path d="M4 28V4h24v24ZM4 16h15V4m0 12v12"/>',
    scenes:'<path d="m18 2-12 17h10l-2 11 12-18H16Z"/>',
    schedules:'<circle cx="16" cy="16" r="12"/><path d="M16 8v9l6 3"/>',
    activity:'<path d="M4 8h24M4 16h24M4 24h16"/>'
  };
  const key=({dimmer:'light',momentary:'button',climate:'temperature',diagrams:'pump',plans:'rooms'})[symbol]||symbol;
  const angle=Number.isFinite(v.angle)?v.angle:0;
  return `<svg class="nm-icon ${v.running?'is-running':''}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" style="--valve-angle:${angle}deg">${icons[key]||icons.label}</svg>`;
}
