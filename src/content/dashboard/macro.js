export const inPeriod=(rows,range)=>{const[a,b]=range.split('..');return rows.filter(r=>r.date>=a&&r.date<=b);};
export const latest=rows=>rows.filter(r=>r.value!=null).reduce((a,r)=>!a||r.date>a.date?r:a,null);
export function indexed(rows,ids){
  const common=new Map();
  for(const r of rows)if(ids.includes(r.series_id)&&r.value!=null)common.set(r.date,(common.get(r.date)||new Set()).add(r.series_id));
  const base=[...common.keys()].sort().find(d=>common.get(d).size===ids.length);
  if(!base)return [];
  const values=Object.fromEntries(rows.filter(r=>r.date===base).map(r=>[r.series_id,r.value]));
  return rows.filter(r=>ids.includes(r.series_id)&&r.date>=base).map(r=>({...r,raw_value:r.value,baseline_value:values[r.series_id],value:r.value==null?null:100*r.value/values[r.series_id],base_date:base}));
}
export function yieldCurve(rows){
  const maturities={DGS3MO:0.25,DGS2:2,DGS5:5,DGS10:10,DGS30:30};
  const days=new Map();
  for(const r of rows)if(r.series_id in maturities&&r.value!=null)days.set(r.date,(days.get(r.date)||new Set()).add(r.series_id));
  const day=[...days.keys()].sort().reverse().find(d=>days.get(d).size===5);
  return rows.filter(r=>r.date===day&&r.series_id in maturities).map(r=>({...r,maturity:maturities[r.series_id]})).sort((a,b)=>a.maturity-b.maturity);
}
export function downloadCSV(name,rows){
  if(!rows.length)return;
  const keys=[...new Set(rows.flatMap(Object.keys))],esc=x=>'"'+String(x??'').replaceAll('"','""')+'"';
  const body='\uFEFF'+[keys.map(esc).join(','),...rows.map(r=>keys.map(k=>esc(r[k])).join(','))].join('\r\n');
  const url=URL.createObjectURL(new Blob([body],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
