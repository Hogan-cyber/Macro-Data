import React,{useState} from 'react';
import {useDataApp,Dropdown,Button,Section,DataComponent,DataTable,EvidenceChart} from '../../data-app-public.jsx';
import {inPeriod,downloadCSV} from './macro.js';
const formats=[['global_macro.xlsx','Excel'],['dataset.sqlite','SQLite database'],['dataset.sql.gz','SQL dump (.gz)'],['observations.parquet','Parquet'],['observations.csv.gz','CSV (.gz)'],['observations.jsonl.gz','JSON Lines (.gz)'],['bundle.zip','Complete bundle'],['dictionary.csv','Data dictionary'],['manifest.json','Version & checksums']];
const col=(field,label,renderCell)=>({field,label,...(renderCell?{renderCell}:{})});
export function GlobalData({range}){
 const{snapshot,queries}=useDataApp();const m=snapshot.globalDataset;
 const dictionary=queries.globalDictionary?.rows||[];const all=queries.globalObservations?.rows||[];
 const[country,setCountry]=useState('JP');const[selected,setSelected]=useState('SPASTT01JPM661N');
 if(!m)return <p>Global dataset has not been built for this snapshot.</p>;
 const countries=[...new Set(dictionary.map(x=>x.country))].sort();
 const activeCountry=countries.includes(country)?country:countries[0];
 const catalog=dictionary.filter(x=>x.country===activeCountry);
 const metric=catalog.find(x=>x.series_id===selected)||catalog[0];
 const series=inPeriod(all.filter(r=>r.series_id===metric?.series_id),range);
 const display=series.map(r=>({...r,unit:metric.unit,frequency:metric.frequency}));
 return <><div className="macro-data-toolbar">{formats.map(([file,label])=><a key={file} className="macro-link" href={'data/global/'+file} download>{label}</a>)}</div>
 <p className="macro-scope" data-reviewed-rows>{m.series_count} series · {m.countries.length} economies · {m.valid_observation_count.toLocaleString()} numeric observations · Version {m.dataset_version}. Downloads contain all countries and all available dates; the chart and selected-series export follow Reference period.</p>
 <p className="macro-small" data-reviewed-rows>Global refresh: {m.generated_at_utc} · {m.status}. Country coverage is uneven. Monthly OECD share-price indices are not daily benchmark closes. International GDP, inflation and unemployment use annual World Bank observations; see each series frequency.</p>
 {m.failures.length>0&&<p role="alert" className="macro-warning">Some international or US requests failed. Last valid data is retained where available; inspect the catalog status and version manifest.</p>}
 <Section id="global-explore" title="Global data explorer" filters={<><Dropdown label="Economy" showLabel searchable value={activeCountry} choices={countries} formatChoice={c=>`${c} · ${dictionary.find(x=>x.country===c)?.country_name}`} onChange={setCountry}/><Dropdown label="Indicator" showLabel searchable value={metric?.series_id} choices={catalog.map(x=>x.series_id)} formatChoice={id=>`${catalog.find(x=>x.series_id===id)?.indicator_zh} · ${id}`} onChange={setSelected}/><Button disabled={!display.length} onClick={()=>downloadCSV(metric.series_id+'.csv',display)}>Download selected series</Button></>}>
 <EvidenceChart id="global-series-chart" queryId="globalObservations" variant="card" rows={display} sourceRows={display} title={`${metric?.indicator_zh} · ${metric?.unit}`} height={380} spec={{type:metric?.frequency==='Annual'?'bar':'line',x:'date',y:'value',stackable:false,startAtZero:metric?.frequency==='Annual',valueDecimals:3,showXAxisLabel:false,showYAxisLabel:false}} description={`${metric?.frequency} · ${metric?.seasonal_adjustment}. ${metric?.definition||''}`}>
 <p className="macro-small" data-reviewed-rows><a href={metric?.source_url} target="_blank" rel="noreferrer">Original source</a> · Available history {metric?.first_observation} – {metric?.last_observation} · {metric?.update_status}</p></EvidenceChart>
 </Section>
 <Section id="global-coverage" title="Available series in this economy"><DataComponent id="global-catalog" queryId="globalDictionary" variant="card" kind="table" sourceRows={catalog} displayRows={catalog}><DataTable caption="Full source coverage, independent of the reference-period filter" rows={catalog} columns={[col('series_id','Series ID'),col('indicator_zh','Indicator'),col('asset_class','Type'),col('frequency','Frequency'),col('unit','Unit'),col('first_observation','From'),col('last_observation','Through'),col('update_status','Status')]}/></DataComponent></Section>
 <Section id="python-access" title="Use in Python"><div className="macro-scope"><p>Install the wheel or install directly from GitHub. Use country, series and date filters; query SQLite with SQL; pin a Git commit for reproducible research.</p><a className="macro-link" href="packages/hogan_macro_data-0.1.0-py3-none-any.whl" download>Download Python package</a>{' '}<a href="https://github.com/Hogan-cyber/Macro-Data/blob/main/PACKAGE_GUIDE.md" target="_blank" rel="noreferrer">Installation & examples</a><p>Observation dates are not release dates. Unverified release dates stay empty. Latest-revised historical macro values require vintage and release-time handling before real-time backtesting.</p></div></Section></>;
}
