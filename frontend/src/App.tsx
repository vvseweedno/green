import {useEffect, useMemo, useRef, useState} from 'react';
import maplibregl, {Map as MLMap} from 'maplibre-gl';

const api=import.meta.env.VITE_API_URL||'http://localhost:8000';
const defaultGeometry={type:'Polygon',coordinates:[[[37.0,55.0],[37.01,55.0],[37.01,55.01],[37.0,55.01],[37.0,55.0]]]};

type AnalysisResult={
  run_id:string;
  coverage:{requested_area_ha:number;computed_area_ha:number;coverage_ratio:number;missing_area_ha:number};
  stock:{E_tco2e:number;e_tco2e_ha_year:number;yearly:Array<{year:number;mean_carbon_t_ha:number}>};
  uncertainty?:{L:number;U:number;method:string};
  credits:{status:string;reason?:string;R?:number;H?:number;UNC?:number;Radj?:number;buffer?:number;Q?:number};
  baseline?:{Ebase?:number};
  events?:Array<{geometry:any;event_id:string;direction:string;confidence:string;cause?:string}>;
  limitations?:string[];
  warnings?:string[];
};

function VerifierMap({geometry,events}:{geometry:any;events:any[]}){
  const el=useRef<HTMLDivElement>(null); const mapRef=useRef<MLMap|null>(null);
  const eventsFc=useMemo(()=>({type:'FeatureCollection',features:(events||[]).filter(e=>e.geometry).map(e=>({type:'Feature',properties:{event_id:e.event_id,direction:e.direction,confidence:e.confidence,cause:e.cause||'unknown'},geometry:e.geometry}))}),[events]);
  useEffect(()=>{
    if(!el.current||mapRef.current)return;
    const map=new maplibregl.Map({container:el.current,style:'https://demotiles.maplibre.org/style.json',center:[37,55],zoom:8});
    mapRef.current=map;
    map.on('load',()=>{
      map.addSource('aoi',{type:'geojson',data:{type:'Feature',properties:{},geometry}} as any);
      map.addLayer({id:'aoi-fill',type:'fill',source:'aoi',paint:{'fill-color':'#176b3a','fill-opacity':0.13}});
      map.addLayer({id:'aoi-line',type:'line',source:'aoi',paint:{'line-color':'#176b3a','line-width':3}});
      map.addSource('events',{type:'geojson',data:eventsFc as any});
      map.addLayer({id:'event-fill',type:'fill',source:'events',paint:{'fill-color':['match',['get','direction'],'disturbance','#cf4a2c','recovery','#3182bd','#777'],'fill-opacity':0.36}});
      map.addLayer({id:'event-line',type:'line',source:'events',paint:{'line-color':'#222','line-width':1.5}});
    });
    return()=>{map.remove();mapRef.current=null};
  },[]);
  useEffect(()=>{
    const map=mapRef.current;if(!map||!map.isStyleLoaded())return;
    (map.getSource('aoi') as any)?.setData({type:'Feature',properties:{},geometry});
  },[geometry]);
  useEffect(()=>{
    const map=mapRef.current;if(!map||!map.isStyleLoaded())return;
    (map.getSource('events') as any)?.setData(eventsFc);
  },[eventsFc]);
  return <div className="map" ref={el}/>;
}

function Metric({label,value,sub}:{label:string;value:string;sub?:string}){
  return <article><b>{label}</b><span>{value}</span>{sub&&<small>{sub}</small>}</article>;
}

export default function App(){
  const [geometryText,setGeometryText]=useState(JSON.stringify(defaultGeometry,null,2));
  const [y0,setY0]=useState(2020),[y1,setY1]=useState(2022),[scenario,setScenario]=useState('moderate');
  const [result,setResult]=useState<AnalysisResult|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  let geometry:any=defaultGeometry;try{geometry=JSON.parse(geometryText)}catch{}
  async function run(){
    setLoading(true);setError('');
    try{
      const r=await fetch(`${api}/api/v1/analysis`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({geometry,year_start:y0,year_end:y1,data_mode:'auto',parent_aoi_id:null,uncertainty_scenario:scenario})});
      const data=await r.json();if(!r.ok)throw new Error(data.detail||'analysis failed');setResult(data);
    }catch(e:any){setError(e.message)}finally{setLoading(false)}
  }
  const stock=result?.stock,credits=result?.credits,unc=result?.uncertainty;
  return <main>
    <header><div><p className="eyebrow">Verification-first MRV</p><h1>Satellite Carbon MRV</h1><p>CCI carbon stock + explainable change evidence + correlated uncertainty + auditable potential-unit calculation.</p></div><div className="badge">2019–2024</div></header>
    <section className="grid">
      <aside className="panel controls"><h2>Analysis request</h2><label>AOI · WGS84 GeoJSON<textarea value={geometryText} onChange={e=>setGeometryText(e.target.value)}/></label>
        <div className="row"><label>Start<input type="number" min="2019" max="2024" value={y0} onChange={e=>setY0(+e.target.value)}/></label><label>End<input type="number" min="2019" max="2024" value={y1} onChange={e=>setY1(+e.target.value)}/></label></div>
        <label>Uncertainty scenario<select value={scenario} onChange={e=>setScenario(e.target.value)}><option value="independent">Independent sensitivity</option><option value="moderate">Moderate correlation</option><option value="strong">Strong correlation</option></select></label>
        <button onClick={run} disabled={loading}>{loading?'Running verification…':'Run verification'}</button>
        {error&&<div className="error">{error}</div>}
        <p className="hint">Q is withheld when full coverage, baseline or finite uncertainty inputs are unavailable.</p>
      </aside>
      <section>
        <VerifierMap geometry={geometry} events={result?.events||[]}/>
        {result&&<><div className="cards">
          <Metric label="E" value={`${stock?.E_tco2e?.toFixed(2)} tCO₂e`} sub="positive = stock loss"/>
          <Metric label="e" value={`${stock?.e_tco2e_ha_year?.toFixed(4)} /ha/yr`}/>
          <Metric label="Model interval" value={unc?`${unc.L?.toFixed(1)} … ${unc.U?.toFixed(1)}`:'unavailable'} sub={unc?.method}/>
          <Metric label="Potential Q" value={credits?.Q==null?'unavailable':String(credits.Q)} sub={credits?.status}/>
        </div>
        <div className="split">
          <div className="panel"><h2>Coverage</h2><div className="coverage"><strong>{(result.coverage.coverage_ratio*100).toFixed(2)}%</strong><span>{result.coverage.computed_area_ha.toFixed(2)} / {result.coverage.requested_area_ha.toFixed(2)} ha</span></div></div>
          <div className="panel"><h2>Credit waterfall</h2><pre>{JSON.stringify({Ebase:result.baseline?.Ebase,Eproj:stock?.E_tco2e,R:credits?.R,H:credits?.H,UNC:credits?.UNC,Radj:credits?.Radj,buffer:credits?.buffer,Q:credits?.Q,status:credits?.status,reason:credits?.reason},null,2)}</pre></div>
        </div>
        <div className="panel"><h2>Annual carbon trajectory</h2><table><thead><tr><th>Year</th><th>Mean tC/ha</th></tr></thead><tbody>{stock?.yearly?.map(p=><tr key={p.year}><td>{p.year}</td><td>{p.mean_carbon_t_ha.toFixed(4)}</td></tr>)}</tbody></table></div>
        <div className="panel warning"><b>Verification limits</b><ul>{(result.limitations||[]).map(x=><li key={x}>{x}</li>)}</ul></div>
        <a className="report" href={`${api}/api/v1/analysis/${result.run_id}/report`} target="_blank" rel="noreferrer">Open audit report ↗</a>
        </>}</section>
    </section>
  </main>;
}
