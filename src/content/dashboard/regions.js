export const COUNTRIES = {US:'United States',CN:'Mainland China',HK:'Hong Kong',DE:'Germany',FR:'France',GB:'United Kingdom'};
export const REGIONS = {
  china:{label:'Mainland China',countries:['CN'],indices:['CSI300','CSI500','CSI1000','SSE_COMPOSITE','SZSE_COMPONENT']},
  europe:{label:'Europe',countries:['DE','FR','GB'],indices:['DAX','CAC40','FTSE100']},
  'hong-kong':{label:'Hong Kong',countries:['HK'],indices:['HSI']},
};
export const PRIMARY_INDEX = {CN:'CSI300',HK:'HSI',DE:'DAX',FR:'CAC40',GB:'FTSE100'};
const INDEX_NAMES = {CSI300:'CSI 300',CSI500:'CSI 500',CSI1000:'CSI 1000',SSE_COMPOSITE:'Shanghai Composite',SZSE_COMPONENT:'Shenzhen Component',HSI:'Hang Seng Index',DAX:'DAX (gross total return)',CAC40:'CAC 40',FTSE100:'FTSE 100'};
const MACRO_NAMES = {GDP_GROWTH:'Real GDP growth',CPI_INFLATION:'CPI inflation',UNEMPLOYMENT:'Unemployment (ILO estimate)'};

export function marketScope(market,catalog,rows){
  const countries=new Set(REGIONS[market]?.countries||[]);
  const scoped=catalog.filter(m=>countries.has(m.country));
  const ids=new Set(scoped.map(m=>m.series_id));
  return {catalog:scoped,rows:rows.filter(r=>countries.has(r.country)&&ids.has(r.series_id))};
}

export function observationPeriod(day,frequency=''){
  if(!day)return 'No data in selected period';
  if(frequency==='Annual')return `${day.slice(0,4)} · Annual`;
  if(frequency.startsWith('Quarterly'))return `${day.slice(0,4)} Q${Math.ceil(Number(day.slice(5,7))/3)} · Quarterly`;
  const date=new Date(day+'T00:00:00Z');
  if(frequency.startsWith('Monthly'))return `${date.toLocaleDateString('en-US',{month:'short',year:'numeric',timeZone:'UTC'})} · Monthly`;
  const label=frequency==='Daily, Close'?'Daily close':frequency;
  return `${date.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'})}${label?' · '+label:''}`;
}

export function latestPair(rows){
  const valid=rows.filter(r=>r.value!=null&&Number.isFinite(r.value)).toSorted((a,b)=>a.date.localeCompare(b.date));
  const current=valid.at(-1)||null;
  const previous=valid.findLast(r=>r.date<current?.date)||null;
  return {current,previous,delta:current&&previous?current.value-previous.value:null};
}

export function chartPeriod(day,frequency){
  return frequency==='Annual'?day.slice(0,4):frequency==='Monthly'?day.slice(0,7):day;
}

export function seriesLabel(meta){
  if(!meta)return 'Unavailable series';
  if(INDEX_NAMES[meta.series_id])return INDEX_NAMES[meta.series_id];
  const country=COUNTRIES[meta.country]||meta.country_name||meta.country;
  const suffix=meta.series_id.replace(/^WB_[A-Z]{2}_/,'');
  if(MACRO_NAMES[suffix])return `${country} · ${MACRO_NAMES[suffix]}`;
  if(meta.series_id.startsWith('SPASTT01'))return `${country} · OECD share-price index`;
  return meta.indicator_zh||meta.series_id;
}

export function checkedTime(value){
  if(!value)return 'Not reported';
  return new Date(value).toLocaleString('en-GB',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Hong_Kong'})+' HKT';
}
