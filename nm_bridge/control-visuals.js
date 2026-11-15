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
    data:'<rect x="4" y="5" width="24" height="22" rx="3"/><path d="M9 11h14v10h-4v3h-6v-3H9Zm3 0v5m4-5v5m4-5v5"/>',
    dali:'<rect x="3" y="8" width="26" height="16" rx="3"/><path d="M1 12h2m-2 8h2m26-8h2m-2 8h2M9 12v8h3a4 4 0 0 0 0-8Zm12 0v8"/>',
    knx:'<rect x="5" y="4" width="22" height="24" rx="3"/><path d="M11 10v12m9-12-9 6 9 6M9 1v3m7-3v3m7-3v3M9 28v3m7-3v3m7-3v3"/>',
    wifi:'<path d="M3 11a20 20 0 0 1 26 0M7 16a14 14 0 0 1 18 0m-14 5a8 8 0 0 1 10 0"/><circle cx="16" cy="27" r="1"/>',
    camera:'<path d="m4 6 21 5-5 13L1 17Zm20 8 6-1-3 8-5-3M10 22v7h9"/>',
    rack:'<rect x="6" y="2" width="20" height="28" rx="2"/><path d="M6 11h20M6 21h20M10 7h2m3 0h7m-12 9h2m3 0h7m-12 9h2m3 0h7"/>',
    outlet:'<circle cx="16" cy="16" r="12"/><path d="M11 13v5m10-5v5M16 4v4m0 16v4"/>',
    spot:'<path d="M7 4h18l-3 11H10Zm9 11v6m-6-4-4 7m16-7 4 7M5 28h22"/>',
    downlight:'<ellipse cx="16" cy="12" rx="13" ry="5"/><path d="M9 18v7m7-6v10m7-11v7"/>',
    'led-strip':'<path d="M3 8h26v16H3Z M8 12v8m5-8v8m6-8v8m5-8v8"/>',
    pendant:'<path d="M16 1v11M10 12h12l7 13H3Zm3 13a3 3 0 0 0 6 0"/>',
    wall:'<path d="M5 3v26m0-13h9M14 8h12l4 16H10Z"/>',
    sensor:'<circle cx="16" cy="16" r="5"/><path d="M7 7a13 13 0 0 0 0 18m18-18a13 13 0 0 1 0 18M3 3a19 19 0 0 0 0 26m26-26a19 19 0 0 1 0 26"/>',
    fan:'<circle cx="16" cy="16" r="3"/><path d="M16 13c-8-12 13-12 3 1m0 4c13-7 10 14-1 1m-5-3C1 24 1 3 14 13"/>',
    motion:'<circle cx="17" cy="6" r="3"/><path d="m7 17 6-6 7 3 5-3M15 12l-3 9-5 8m5-8 8 2 3 6"/>',
    contact:'<path d="M5 3h15v26H5Zm19 7h4v12h-4M15 16h1"/>',
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
  const key=({thermostat:'temperature',dimmer:'light',momentary:'button',climate:'temperature',diagrams:'pump',plans:'rooms'})[symbol]||symbol;
  const angle=Number.isFinite(v.angle)?v.angle:0;
  return `<svg class="nm-icon ${v.running?'is-running':''}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" style="--valve-angle:${angle}deg">${icons[key]||icons.label}</svg>`;
}
