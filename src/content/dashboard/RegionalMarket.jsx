import React,{useMemo} from 'react';
import {DataComponent,DataTable,EvidenceChart,Section,Dropdown,Button,useDataApp} from '../../data-app-public.jsx';
import {inPeriod,indexed,downloadCSV} from './macro.js';
import {COUNTRIES,REGIONS,PRIMARY_INDEX,marketScope,observationPeriod,chartPeriod,latestPair,seriesLabel,checkedTime} from './regions.js';

const fmt=(value,digits=2)=>value==null?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const col=(field,label,renderCell)=>({field,label,...(renderCell?{renderCell}:{})});
const select=(rows,ids)=>rows.filter(r=>ids.includes(r.series_id));

function RegionalKpi({id,title,rows,meta}){
  const {current,previous,delta}=latestPair(rows);
  const percent=meta?.unit?.startsWith('Percent');
  return <DataComponent id={id} queryId="globalObservations" variant="card" kind="metric" title={title}
    sourceRows={[previous,current].filter(Boolean)} displayRows={current?[current]:[]} description={meta?.definition}>
    <div data-reviewed-rows>
      <div className="macro-value">{fmt(current?.value)}<small>{percent?'%':meta?.unit||'Index'}</small></div>
      <div className="macro-caption">{observationPeriod(current?.date,meta?.frequency)}</div>
      <div className="macro-small">{delta==null?'No earlier comparison in range':`${delta>0?'+':''}${fmt(delta)} ${percent?'percentage points':'points'} vs ${observationPeriod(previous.date,meta.frequency).split(' · ')[0]}`}</div>
    </div>
  </DataComponent>;
}

function RegionalChart({id,title,rows,metadata,type='line',description,sourceRows=rows,height=310}){
  const shown=rows.map(r=>({...r,period:chartPeriod(r.date,metadata.get(r.series_id)?.frequency),indicator:seriesLabel(metadata.get(r.series_id))}));
  return <EvidenceChart id={id} queryId="globalObservations" variant="card" title={title} rows={shown} sourceRows={sourceRows}
    description={description} height={height} spec={{type,x:'period',y:'value',series:'indicator',stackable:false,startAtZero:type==='bar',valueDecimals:2,showXAxisLabel:false,showYAxisLabel:false}}>
    {!shown.some(r=>r.value!=null)&&<p className="macro-small" data-reviewed-rows>No observations in the selected reference period.</p>}
  </EvidenceChart>;
}

export function RegionalMarket({market,range}){
  const {queries,viewFocus,setDashboardFocus}=useDataApp();
  const config=REGIONS[market];
  const country=viewFocus?.economy||config.countries[0];
  const selected=viewFocus?.series||config.indices[0];
  const setCountry=economy=>setDashboardFocus({...viewFocus,economy});
  const setSelected=series=>setDashboardFocus({...viewFocus,series});
  const scope=useMemo(()=>marketScope(market,queries.globalDictionary?.rows||[],queries.globalObservations?.rows||[]),[market,queries.globalDictionary,queries.globalObservations]);
  const rows=useMemo(()=>inPeriod(scope.rows,range),[scope.rows,range]);
  const metadata=useMemo(()=>new Map(scope.catalog.map(m=>[m.series_id,m])),[scope.catalog]);
  const activeCountry=config.countries.includes(country)?country:config.countries[0];
  const lead=PRIMARY_INDEX[activeCountry];
  const equityRows=select(rows,config.indices);
  const equityComparison=config.indices.length>1?indexed(equityRows,config.indices):equityRows;
  const oecd=scope.catalog.filter(m=>m.series_id.startsWith('SPASTT01')).map(m=>m.series_id);
  const metric=metadata.get(selected)||scope.catalog[0];
  const selectedRows=select(rows,[metric?.series_id]);
  const checked=scope.catalog.map(m=>m.retrieved_at_utc).filter(Boolean).sort().at(-1);
  const failed=scope.catalog.filter(m=>!['UPDATED','UNCHANGED'].includes(m.update_status));
  const downloadable=rows.map(r=>({...r,frequency:metadata.get(r.series_id)?.frequency,unit:metadata.get(r.series_id)?.unit}));
  const macroCards=[['GDP_GROWTH','Real GDP growth'],['CPI_INFLATION','CPI inflation'],['UNEMPLOYMENT','Unemployment · ILO estimate']];

  if(!scope.catalog.length)return <p role="status">This snapshot has no reviewed data for {config.label}.</p>;
  return <>
    <div className="macro-data-toolbar">
      <Button disabled={!downloadable.length} onClick={()=>downloadCSV(market+'-selected-period.csv',downloadable)}>Download {config.label} CSV</Button>
      <a className="macro-link" href="data/global/global_macro.xlsx" download>All markets · Excel</a>
      <a className="macro-link" href="data/global/dataset.sqlite" download>All markets · SQLite</a>
    </div>
    <p className="macro-scope" data-reviewed-rows>
      {market==='europe'?'Germany, France and the United Kingdom. National macro indicators are shown separately; this page is not a euro-area aggregate. ':''}
      Daily stock closes and annual World Bank macro data. {oecd.length>0?'OECD monthly share-price history is shown separately. ':''}
      Annual CPI inflation and ILO modeled unemployment differ from monthly national releases. Dates below identify the observation period.
    </p>
    <p className="macro-small" data-reviewed-rows>Most recent successful retrieval: {checkedTime(checked)} · Scheduled Monday 08:00 HKT.</p>
    {failed.length>0&&<p role="alert" className="macro-warning" data-reviewed-rows>Source retrieval is incomplete for {failed.map(m=>m.series_id).join(', ')}. Any available prior observations are retained; see source status below.</p>}

    <Section id={market+'-headline-section'} title={COUNTRIES[activeCountry]+' · Latest in selected period'}
      filters={config.countries.length>1?<Dropdown label="Macro economy" showLabel value={activeCountry} choices={config.countries} choiceLabels={COUNTRIES} onChange={setCountry}/>:null}>
      <div className="macro-kpis">
        <RegionalKpi id={market+'-index-kpi'} title={seriesLabel(metadata.get(lead))} rows={select(rows,[lead])} meta={metadata.get(lead)}/>
        {macroCards.map(([suffix,label])=>{
          const id='WB_'+activeCountry+'_'+suffix;
          return <RegionalKpi key={suffix} id={market+'-'+suffix.toLowerCase()+'-kpi'} title={label+' · Annual'} rows={select(rows,[id])} meta={metadata.get(id)}/>;
        })}
      </div>
    </Section>

    <Section id={market+'-equity-section'} title="Stock market">
      {market==='europe'&&<p className="macro-small" data-reviewed-rows>DAX reinvests dividends (gross total return). CAC 40 and FTSE 100 are price indices, so these lines use different return conventions.</p>}
      <RegionalChart id={market+'-equity-comparison'} title={config.indices.length>1?'Daily indices · common start = 100':'Hang Seng Index · daily close'} rows={equityComparison} sourceRows={equityRows} metadata={metadata} height={370}
        description={config.indices.length>1?'Each index is divided by its close on the first common trading date in the selected period and multiplied by 100. No holiday filling. See the data dictionary for return conventions.':'Market-local closing dates; current local sessions are excluded. Price index, excluding dividends.'}/>
      {config.indices.length>1&&equityRows.some(r=>r.value!=null)&&!equityComparison.length&&<p className="macro-small" data-reviewed-rows>No common baseline date across every index in this period. Explore individual series below.</p>}
    </Section>

    <Section id={market+'-macro-section'} title={COUNTRIES[activeCountry]+' · Annual macro indicators'}>
      <div className="macro-grid">
        {macroCards.map(([suffix,label])=>{
          const sid='WB_'+activeCountry+'_'+suffix;
          return <RegionalChart key={suffix} id={market+'-macro-'+suffix.toLowerCase()} title={label+' · Annual (%)'} rows={select(rows,[sid])} metadata={metadata} type={suffix==='GDP_GROWTH'?'bar':'line'} description={metadata.get(sid)?.definition}/>;
        })}
      </div>
    </Section>
    {oecd.length>0&&<Section id={market+'-oecd-section'} title="Monthly OECD stock-market history"><RegionalChart id={market+'-oecd-monthly'} title="OECD share prices · Monthly (2015 = 100)" rows={select(rows,oecd)} metadata={metadata}
      description="Original monthly OECD broad-market series. These are distinct from the named daily closing indices above."/></Section>}

    <Section id={market+'-explore-section'} title="Explore and download a series" filters={<>
      <Dropdown label="Indicator" showLabel searchable value={metric?.series_id} choices={scope.catalog.map(m=>m.series_id)} formatChoice={id=>seriesLabel(metadata.get(id))} onChange={setSelected}/>
      <Button disabled={!selectedRows.length} onClick={()=>downloadCSV(metric.series_id+'-selected-period.csv',selectedRows.map(r=>({...r,frequency:metric.frequency,unit:metric.unit})))}>Download selected series</Button>
    </>}>
      <RegionalChart id={market+'-selected-series'} title={seriesLabel(metric)+' · '+metric.unit} rows={selectedRows} metadata={metadata} type={metric.frequency==='Annual'?'bar':'line'} description={metric.frequency+'. '+metric.definition}/>
      <p className="macro-small" data-reviewed-rows>{metric.frequency} · {metric.seasonal_adjustment} · <a href={metric.source_url} target="_blank" rel="noreferrer">Original source</a></p>
    </Section>

    <Section id={market+'-coverage-section'} title="Source coverage and update status">
      <DataComponent id={market+'-coverage'} queryId="globalDictionary" kind="table" variant="card" title="Available series" sourceRows={scope.catalog} displayRows={scope.catalog}>
        <DataTable caption="Full source coverage, independent of the reference-period filter. A successful check does not imply a new observation period." rows={scope.catalog} columns={[
          col('series_id','Indicator',(_,row)=>seriesLabel(row)),col('frequency','Frequency'),
          col('last_observation','Latest period',(value,row)=>observationPeriod(value,row.frequency)),
          col('source_last_updated','Source updated',value=>value||'Not reported'),
          col('retrieved_at_utc','Retrieved (HKT)',checkedTime),col('update_status','Status'),
          col('source_url','Source',value=><a href={value} target="_blank" rel="noreferrer">Open source</a>)
        ]}/>
      </DataComponent>
    </Section>
  </>;
}
