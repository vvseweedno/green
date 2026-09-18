import {useEffect, useMemo, useRef, useState} from 'react';
import {Map as MLMap} from 'maplibre-gl';

const api=import.meta.env.VITE_API_URL||'http://localhost:8000';
const defaultGeometry={type:'Polygon',coordinates:[[[37.0,55.0],[37.01,55.0],[37.01,55.01],[37.0,55.01],[37.0,55.0]]]};

type Quality={
  stage?:string;date?:string;scene_id?:string;processing_baseline?:string;
  reflectance_path?:string;scl_path?:string;valid_fraction?:number;strict_valid_fraction?:number;
};
type CarbonContribution={area_ha?:number;E_event_tco2e?:number;share_of_aoi_area?:number;share_of_absolute_carbon_change_signal?:number};
type EventRecord={
  geometry:any;event_id:string;direction:string;confidence:string;cause?:string|null;cause_status?:string;
  date_min?:string|null;date_max?:string|null;date_precision?:string;date_conflict?:boolean;
  evidence?:Array<Record<string,unknown>>;data_quality?:Quality[];carbon_contribution?:CarbonContribution|null;limitations?:string[];
};
type AnalysisResult={
  run_id:string;
  coverage:{requested_area_ha:number;computed_area_ha:number;coverage_ratio:number;missing_area_ha:number};
  stock:{E_tco2e:number;e_tco2e_ha_year:number;delta_c_t:number;start:{total_carbon_t:number;mean_carbon_t_ha:number};end:{total_carbon_t:number;mean_carbon_t_ha:number};yearly:Array<{year:number;mean_carbon_t_ha:number;total_carbon_t:number;annual_delta_c_t?:number|null;annual_E_tco2e?:number|null;cumulative_delta_c_t?:number;cumulative_E_tco2e?:number}>};
  uncertainty?:{L:number;U:number;method:string;sensitivity?:Array<{scenario:string;status:string;L?:number;U?:number;interval_width_tco2e?:number;H?:number;H_over_R?:number;UNC?:number;Q?:number}>};
  credits:{status:string;reason?:string;R?:number;H?:number;UNC?:number;Radj?:number;buffer?:number;Q?:number;scenario_values_rub?:Array<Record<string,unknown>>;price_scenario_disclaimer?:string};
  baseline?:{Ebase?:number};
  events?:EventRecord[];
  provenance?:Record<string,unknown>;
  limitations?:string[];
  warnings?:string[];
};
type AreaFeature={type:'Feature';id?:string;properties:{aoi_id?:string};geometry:any};

const offlineStyle:any={
  version:8,
  sources:{},
  layers:[{id:'background',type:'background',paint:{'background-color':'#edf3ee'}}]
};

function normalizeGeometry(payload:any){
  if(payload?.type==='FeatureCollection'){
    if(!payload.features?.length)throw new Error('GeoJSON FeatureCollection is empty');
    return payload.features[0].geometry;
  }
  if(payload?.type==='Feature')return payload.geometry;
  if(payload?.type==='Polygon'||payload?.type==='MultiPolygon')return payload;
  throw new Error('Expected Polygon, MultiPolygon, Feature or FeatureCollection');
}

function coordinatePairs(value:any,out:[number,number][]=[]):[number,number][]{
  if(Array.isArray(value)&&value.length>=2&&typeof value[0]==='number'&&typeof value[1]==='number'){
    out.push([value[0],value[1]]);return out;
  }
  if(Array.isArray(value))for(const child of value)coordinatePairs(child,out);
  return out;
}

function fitGeometry(map:MLMap,geometry:any){
  const pairs=coordinatePairs(geometry?.coordinates);
  if(!pairs.length)return;
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for(const [x,y] of pairs){minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}
  map.fitBounds([[minX,minY],[maxX,maxY]],{padding:48,maxZoom:14,duration:0});
}

function draftGeoJSON(points:[number,number][]){
  if(points.length===0)return {type:'FeatureCollection',features:[]};
  const geometry=points.length>=3
    ?{type:'Polygon',coordinates:[[...points,points[0]]]}
    :points.length===2
      ?{type:'LineString',coordinates:points}
      :{type:'Point',coordinates:points[0]};
  return {type:'Feature',properties:{draft:true},geometry};
}

function VerifierMap({geometry,events,onGeometryDrawn}:{geometry:any;events:EventRecord[];onGeometryDrawn:(g:any)=>void}){
  const el=useRef<HTMLDivElement>(null);
  const mapRef=useRef<MLMap|null>(null);
  const [showAoi,setShowAoi]=useState(true),[showEvents,setShowEvents]=useState(true);
  const [drawMode,setDrawMode]=useState(false);
  const [drawPoints,setDrawPoints]=useState<[number,number][]>([]);
  const eventsFc=useMemo(()=>({
    type:'FeatureCollection',
    features:(events||[]).filter(e=>e.geometry).map(e=>({
      type:'Feature',
      properties:{event_id:e.event_id,direction:e.direction,confidence:e.confidence,cause:e.cause||'unknown'},
      geometry:e.geometry
    }))
  }),[events]);

  useEffect(()=>{
    if(!el.current||mapRef.current)return;
    const map=new MLMap({container:el.current,style:offlineStyle,center:[37,55],zoom:5});
    mapRef.current=map;
    map.on('load',()=>{
      map.addSource('aoi',{type:'geojson',data:{type:'Feature',properties:{},geometry}} as any);
      map.addLayer({id:'aoi-fill',type:'fill',source:'aoi',paint:{'fill-color':'#176b3a','fill-opacity':0.13}});
      map.addLayer({id:'aoi-line',type:'line',source:'aoi',paint:{'line-color':'#176b3a','line-width':3}});
      map.addSource('events',{type:'geojson',data:eventsFc as any});
      map.addLayer({id:'event-fill',type:'fill',source:'events',paint:{'fill-color':['match',['get','direction'],'disturbance','#cf4a2c','recovery','#3182bd','#777'],'fill-opacity':0.36}});
      map.addLayer({id:'event-line',type:'line',source:'events',paint:{'line-color':'#222','line-width':1.5}});
      map.addSource('draft',{type:'geojson',data:draftGeoJSON([]) as any});
      map.addLayer({id:'draft-fill',type:'fill',source:'draft',paint:{'fill-color':'#e69f00','fill-opacity':0.18}});
      map.addLayer({id:'draft-line',type:'line',source:'draft',paint:{'line-color':'#b66b00','line-width':3,'line-dasharray':[2,1]}});
      fitGeometry(map,geometry);
    });
    return()=>{map.remove();mapRef.current=null};
  },[]);

  useEffect(()=>{
    const map=mapRef.current;if(!map||!map.isStyleLoaded())return;
    (map.getSource('aoi') as any)?.setData({type:'Feature',properties:{},geometry});
    fitGeometry(map,geometry);
  },[geometry]);

  useEffect(()=>{
    const map=mapRef.current;if(!map||!map.isStyleLoaded())return;
    (map.getSource('events') as any)?.setData(eventsFc);
  },[eventsFc]);

  useEffect(()=>{
    const map=mapRef.current;if(!map||!map.isStyleLoaded())return;
    for(const id of ['aoi-fill','aoi-line'])if(map.getLayer(id))map.setLayoutProperty(id,'visibility',showAoi?'visible':'none');
  },[showAoi]);

  useEffect(()=>{
    const map=mapRef.current;if(!map||!map.isStyleLoaded())return;
    for(const id of ['event-fill','event-line'])if(map.getLayer(id))map.setLayoutProperty(id,'visibility',showEvents?'visible':'none');
  },[showEvents]);

  useEffect(()=>{
    const map=mapRef.current;if(!map)return;
    const click=(event:any)=>{
      if(!drawMode)return;
      const point:[number,number]=[event.lngLat.lng,event.lngLat.lat];
      setDrawPoints(prev=>{
        const next=[...prev,point];
        (map.getSource('draft') as any)?.setData(draftGeoJSON(next));
        return next;
      });
    };
    map.getCanvas().style.cursor=drawMode?'crosshair':'';
    map.on('click',click);
    return()=>{map.off('click',click);map.getCanvas().style.cursor='';};
  },[drawMode]);

  function clearDraft(){
    setDrawPoints([]);
    const map=mapRef.current;
    if(map?.isStyleLoaded())(map.getSource('draft') as any)?.setData(draftGeoJSON([]));
  }

  function finishDraft(){
    if(drawPoints.length<3)return;
    const polygon={type:'Polygon',coordinates:[[...drawPoints,drawPoints[0]]]};
    onGeometryDrawn(polygon);
    setDrawMode(false);
    clearDraft();
  }

  return <div className="map-wrap">
    <div className="map-toolbar">
      <label><input type="checkbox" checked={showAoi} onChange={e=>setShowAoi(e.target.checked)}/> AOI</label>
      <label><input type="checkbox" checked={showEvents} onChange={e=>setShowEvents(e.target.checked)}/> change objects</label>
      <button type="button" className={drawMode?'active':''} onClick={()=>setDrawMode(v=>!v)}>{drawMode?'Drawing…':'Draw AOI'}</button>
      {drawMode&&<button type="button" disabled={drawPoints.length<3} onClick={finishDraft}>Finish</button>}
      {drawPoints.length>0&&<button type="button" onClick={clearDraft}>Clear</button>}
      <span>offline map</span>
    </div>
    <div className="map" ref={el}/>
  </div>;
}

function Metric({label,value,sub}:{label:string;value:string;sub?:string}){
  return <article><b>{label}</b><span>{value}</span>{sub&&<small>{sub}</small>}</article>;
}

function CarbonTimeline({points,uncertainty}:{points:AnalysisResult['stock']['yearly'];uncertainty?:AnalysisResult['uncertainty']}){
  if(!points.length)return null;
  const width=760,height=230,pad=34;
  const vals=points.map(p=>p.mean_carbon_t_ha);
  const lo=Math.min(...vals),hi=Math.max(...vals),span=Math.max(hi-lo,1e-9);
  const xy=points.map((p,i)=>({
    x:pad+i*(width-2*pad)/Math.max(1,points.length-1),
    y:height-pad-(p.mean_carbon_t_ha-lo)/span*(height-2*pad),
    p
  }));
  const poly=xy.map(v=>`${v.x.toFixed(1)},${v.y.toFixed(1)}`).join(' ');
  return <div className="timeline">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="2019 to 2024 mean carbon trajectory">
      <line x1={pad} y1={height-pad} x2={width-pad} y2={height-pad}/>
      <polyline points={poly} fill="none" stroke="currentColor" strokeWidth="3"/>
      {xy.map(({x,y,p})=><g key={p.year}><circle cx={x} cy={y} r="4"/><text x={x} y={height-10} textAnchor="middle">{p.year}</text><text x={x} y={y-10} textAnchor="middle">{p.mean_carbon_t_ha.toFixed(2)}</text></g>)}
    </svg>
    <p className="hint">Mean tC/ha by year. Requested-period E interval: {uncertainty?`${uncertainty.L.toFixed(1)} … ${uncertainty.U.toFixed(1)} tCO₂e`:'unavailable'}.</p>
  </div>;
}

function SceneImage({runId,path,label,date}:{runId:string;path?:string;label:string;date?:string}){
  if(!path)return <div className="scene-empty"><b>{label}</b><span>No referenced scene</span></div>;
  const src=`${api}/api/v1/analysis/${encodeURIComponent(runId)}/scene-preview?path=${encodeURIComponent(path)}`;
  return <figure className="scene"><figcaption><b>{label}</b><span>{date||''}</span></figcaption><img src={src} alt={`${label} Sentinel-2 evidence`}/></figure>;
}

export default function App(){
  const [geometryText,setGeometryText]=useState(JSON.stringify(defaultGeometry,null,2));
  const [y0,setY0]=useState(2020),[y1,setY1]=useState(2022),[scenario,setScenario]=useState('moderate');
  const [result,setResult]=useState<AnalysisResult|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const [areas,setAreas]=useState<AreaFeature[]>([]);
  const [selectedEventId,setSelectedEventId]=useState<string>('');

  useEffect(()=>{
    fetch(`${api}/api/v1/areas`).then(r=>r.ok?r.json():Promise.reject()).then(data=>setAreas(data.features||[])).catch(()=>setAreas([]));
  },[]);

  let geometry:any=defaultGeometry;
  try{geometry=normalizeGeometry(JSON.parse(geometryText));}catch{}

  async function run(){
    setLoading(true);setError('');
    try{
      const parsed=normalizeGeometry(JSON.parse(geometryText));
      const r=await fetch(`${api}/api/v1/analysis`,{
        method:'POST',headers:{'content-type':'application/json'},
        body:JSON.stringify({geometry:parsed,year_start:y0,year_end:y1,data_mode:'auto',parent_aoi_id:null,uncertainty_scenario:scenario})
      });
      const data=await r.json();if(!r.ok)throw new Error(data.detail||'analysis failed');
      setResult(data);setSelectedEventId(data.events?.[0]?.event_id||'');
    }catch(e:any){setError(e?.message||String(e));}finally{setLoading(false);}
  }

  async function uploadGeoJSON(file?:File){
    if(!file)return;
    try{
      const parsed=JSON.parse(await file.text());
      const g=normalizeGeometry(parsed);
      setGeometryText(JSON.stringify(g,null,2));setError('');
    }catch(e:any){setError(`GeoJSON: ${e?.message||String(e)}`);}
  }

  function chooseArea(id:string){
    const feature=areas.find(a=>(a.properties?.aoi_id||a.id)===id);
    if(feature)setGeometryText(JSON.stringify(feature.geometry,null,2));
  }

  const stock=result?.stock,credits=result?.credits,unc=result?.uncertainty;
  const startPoint=stock?.yearly?.find(p=>p.year===y0);
  const endPoint=stock?.yearly?.find(p=>p.year===y1);
  const events=result?.events||[];
  const selected=events.find(e=>e.event_id===selectedEventId)||events[0];
  const bestScene=(stage:string)=>selected?.data_quality
    ?.filter(q=>q.stage===stage&&q.reflectance_path)
    .sort((a,b)=>(b.strict_valid_fraction??b.valid_fraction??0)-(a.strict_valid_fraction??a.valid_fraction??0))[0];
  const before=bestScene('before');
  const after=bestScene('after');

  return <main>
    <header><div><p className="eyebrow">Verification-first MRV</p><h1>Satellite Carbon MRV</h1><p>CCI carbon stock + explainable change evidence + correlated uncertainty + auditable potential-unit calculation.</p></div><div className="badge">2019–2024</div></header>
    <section className="grid">
      <aside className="panel controls">
        <h2>Analysis request</h2>
        {areas.length>0&&<label>Demo AOI<select defaultValue="" onChange={e=>chooseArea(e.target.value)}><option value="" disabled>Select official AOI…</option>{areas.map(a=>{const id=a.properties?.aoi_id||String(a.id);return <option key={id} value={id}>{id}</option>;})}</select></label>}
        <label className="upload">Upload GeoJSON<input type="file" accept=".json,.geojson,application/geo+json,application/json" onChange={e=>uploadGeoJSON(e.target.files?.[0])}/></label>
        <label>AOI · WGS84 GeoJSON<textarea value={geometryText} onChange={e=>setGeometryText(e.target.value)}/></label>
        <div className="row"><label>Start<input type="number" min="2019" max="2024" value={y0} onChange={e=>setY0(+e.target.value)}/></label><label>End<input type="number" min="2019" max="2024" value={y1} onChange={e=>setY1(+e.target.value)}/></label></div>
        <label>Uncertainty scenario<select value={scenario} onChange={e=>setScenario(e.target.value)}><option value="independent">Independent sensitivity</option><option value="moderate">Moderate correlation</option><option value="strong">Strong correlation</option></select></label>
        <button onClick={run} disabled={loading}>{loading?'Running verification…':'Run verification'}</button>
        {error&&<div className="error">{error}</div>}
        <p className="hint">Q is withheld when full coverage, baseline or finite uncertainty inputs are unavailable. Evidence gaps reduce confidence instead of being inferred.</p>
      </aside>
      <section>
        <VerifierMap geometry={geometry} events={events} onGeometryDrawn={g=>setGeometryText(JSON.stringify(g,null,2))}/>
        {result&&<>
          <div className="cards">
            <Metric label={`Mean carbon ${y0}`} value={startPoint?`${startPoint.mean_carbon_t_ha.toFixed(2)} tC/ha`:'unavailable'}/>
            <Metric label={`Mean carbon ${y1}`} value={endPoint?`${endPoint.mean_carbon_t_ha.toFixed(2)} tC/ha`:'unavailable'}/>
            <Metric label={`Total stock ${y0}`} value={stock?`${stock.start.total_carbon_t.toFixed(1)} tC`:'unavailable'}/>
            <Metric label={`Total stock ${y1}`} value={stock?`${stock.end.total_carbon_t.toFixed(1)} tC`:'unavailable'}/>
            <Metric label="ΔC" value={stock?`${stock.delta_c_t.toFixed(2)} tC`:'unavailable'}/>
            <Metric label="E" value={`${stock?.E_tco2e?.toFixed(2)} tCO₂e`} sub="positive = stock loss"/>
            <Metric label="e" value={`${stock?.e_tco2e_ha_year?.toFixed(4)} tCO₂e/ha/yr`}/>
            <Metric label="Model interval" value={unc?`${unc.L?.toFixed(1)} … ${unc.U?.toFixed(1)}`:'unavailable'} sub={unc?.method}/>
            <Metric label="Potential Q" value={credits?.Q==null?'unavailable':String(credits.Q)} sub={credits?.status}/>
          </div>
          <div className="split">
            <div className="panel"><h2>Coverage</h2><div className="coverage"><strong>{(result.coverage.coverage_ratio*100).toFixed(2)}%</strong><span>{result.coverage.computed_area_ha.toFixed(2)} / {result.coverage.requested_area_ha.toFixed(2)} ha</span></div></div>
            <div className="panel"><h2>Credit waterfall</h2><pre>{JSON.stringify({Ebase:result.baseline?.Ebase,Eproj:stock?.E_tco2e,R:credits?.R,H:credits?.H,UNC:credits?.UNC,Radj:credits?.Radj,buffer:credits?.buffer,Q:credits?.Q,status:credits?.status,reason:credits?.reason},null,2)}</pre></div>
          </div>
          <div className="panel sensitivity-panel"><h2>Uncertainty sensitivity</h2>
            {unc?.sensitivity?.length?<table><thead><tr><th>Scenario</th><th>L</th><th>U</th><th>Width</th><th>H/R</th><th>UNC</th><th>Q</th></tr></thead><tbody>{unc.sensitivity.map(row=><tr key={row.scenario} className={row.scenario===scenario?'selected-row':''}><td>{row.scenario}</td><td>{row.L==null?'—':row.L.toFixed(1)}</td><td>{row.U==null?'—':row.U.toFixed(1)}</td><td>{row.interval_width_tco2e==null?'—':row.interval_width_tco2e.toFixed(1)}</td><td>{row.H_over_R==null?'—':row.H_over_R.toFixed(3)}</td><td>{row.UNC==null?'—':row.UNC.toFixed(3)}</td><td>{row.Q==null?'—':row.Q}</td></tr>)}</tbody></table>:<p className="hint">Sensitivity unavailable for this run.</p>}
            <p className="hint">Model-based scenario comparison. The selected production scenario is highlighted; the system does not automatically choose the narrowest interval.</p>
          </div>
          <div className="panel"><h2>Price scenarios after Q</h2><pre>{JSON.stringify(credits?.scenario_values_rub||[],null,2)}</pre><p className="hint">{credits?.price_scenario_disclaimer}</p></div>
          <div className="panel"><h2>Annual carbon trajectory</h2><CarbonTimeline points={stock?.yearly||[]} uncertainty={unc}/><table><thead><tr><th>Year</th><th>Mean tC/ha</th><th>Total tC</th><th>Annual ΔC</th><th>Cumulative E</th></tr></thead><tbody>{stock?.yearly?.map(p=><tr key={p.year}><td>{p.year}</td><td>{p.mean_carbon_t_ha.toFixed(4)}</td><td>{p.total_carbon_t.toFixed(2)}</td><td>{p.annual_delta_c_t==null?'—':p.annual_delta_c_t.toFixed(2)}</td><td>{p.cumulative_E_tco2e==null?'—':p.cumulative_E_tco2e.toFixed(2)}</td></tr>)}</tbody></table></div>
          <div className="panel events-panel">
            <div className="panel-title"><h2>Change events</h2><span>{events.length} objects</span></div>
            {events.length===0?<p className="hint">No change objects were emitted for this request, or required optical observations were unavailable.</p>:<>
              <div className="event-tabs">{events.map(e=><button className={e.event_id===selected?.event_id?'active':''} key={e.event_id} onClick={()=>setSelectedEventId(e.event_id)}>{e.direction} · {e.confidence}</button>)}</div>
              {selected&&<>
                <div className="event-summary">
                  <span><b>{selected.event_id}</b></span>
                  <span>{selected.direction}</span><span>{selected.confidence}</span>
                  <span>{selected.cause||'cause not established'}</span>
                  <span>{selected.date_min||'?'} → {selected.date_max||'?'} · {selected.date_precision||'unknown'}</span>
                </div>
                <div className="scene-grid"><SceneImage runId={result.run_id} path={before?.reflectance_path} label="Before" date={before?.date}/><SceneImage runId={result.run_id} path={after?.reflectance_path} label="After" date={after?.date}/></div>
                <div className="event-details">
                  <div><h3>Evidence</h3><pre>{JSON.stringify(selected.evidence||[],null,2)}</pre></div>
                  <div><h3>Carbon contribution</h3><pre>{JSON.stringify(selected.carbon_contribution||{status:'unavailable'},null,2)}</pre></div>
                </div>
                {!!selected.limitations?.length&&<ul className="limitations">{selected.limitations.map(x=><li key={x}>{x}</li>)}</ul>}
              </>}
            </>}
          </div>
          <div className="panel audit"><details><summary>Audit & provenance</summary><pre>{JSON.stringify(result.provenance||{},null,2)}</pre></details></div>
          <div className="panel warning"><b>Verification limits</b><ul>{(result.limitations||[]).map(x=><li key={x}>{x}</li>)}</ul></div>
          <a className="report" href={`${api}/api/v1/analysis/${result.run_id}/report`} target="_blank" rel="noreferrer">Download verification report ↗</a>
        </>}
      </section>
    </section>
  </main>;
}
