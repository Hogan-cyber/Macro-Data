"""Collect public daily index closes without credentials or AI services."""
from __future__ import annotations
import concurrent.futures,hashlib,json,math,ssl,time,urllib.parse,urllib.request
from datetime import date,datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import certifi
try:
 from .international import atomic_json
 from .update_us_macro import compare_rows
except ImportError:
 from international import atomic_json
 from update_us_macro import compare_rows
ROOT=Path(__file__).resolve().parents[1]

def validate(rows):
 if not rows or not any(r[1] is not None for r in rows):raise ValueError('No numeric daily history')
 previous=None
 for day,value,missing in rows:
  date.fromisoformat(day)
  if previous is not None and day<=previous:raise ValueError('Duplicate or unsorted session dates')
  if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0):raise ValueError('Invalid index close')
  if missing!=int(value is None):raise ValueError('Missing flag mismatch')
  previous=day
 return rows

def parse_yahoo(payload,spec,now):
 chart=payload.get('chart',{})
 if chart.get('error') or len(chart.get('result') or [])!=1:raise ValueError('Yahoo chart unavailable')
 result=chart['result'][0];meta=result['meta']
 for field,expected in [('symbol',spec['symbol']),('instrumentType','INDEX'),('exchangeTimezoneName',spec['timezone']),('currency',spec['currency'])]:
  if meta.get(field)!=expected:raise ValueError('Yahoo identity mismatch: '+field)
 if spec['expected_name'].casefold() not in (meta.get('longName') or meta.get('shortName','')).casefold():raise ValueError('Index name changed')
 timestamps=result.get('timestamp',[]);closes=result['indicators']['quote'][0].get('close',[])
 if len(timestamps)!=len(closes):raise ValueError('Timestamp/close length mismatch')
 zone=ZoneInfo(spec['timezone']);cutoff=now.astimezone(zone).date().isoformat();rows=[]
 for stamp,value in zip(timestamps,closes):
  day=datetime.fromtimestamp(stamp,zone).date().isoformat()
  if '2000-01-01'<=day<cutoff:rows.append([day,value,int(value is None)])
 return validate(rows),{'source_title':meta.get('longName') or meta['shortName']}

def parse_eastmoney(payload,spec,now):
 data=payload.get('data');market,code=spec['symbol'].split('.')
 if payload.get('rc')!=0 or not data or data.get('code')!=code or str(data.get('market'))!=market or data.get('name')!=spec['expected_name']:raise ValueError('Eastmoney index identity mismatch')
 cutoff=now.astimezone(ZoneInfo(spec['timezone'])).date().isoformat();rows=[]
 for line in data.get('klines',[]):
  fields=line.split(',')
  if len(fields)!=11:raise ValueError('Unexpected Eastmoney kline schema')
  day=fields[0];date.fromisoformat(day)
  if '2000-01-01'<=day<cutoff:
   value=None if fields[2] in ['','-','null'] else float(fields[2])
   rows.append([day,value,int(value is None)])
 return validate(rows),{'source_title':data['name']}

def fetch_one(spec,raw_dir,now):
 if spec['provider']=='yahoo':
  url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(spec['symbol'],safe='')+'?'+urllib.parse.urlencode({'period1':946684800,'period2':int(now.timestamp()),'interval':'1d'})
  parse=parse_yahoo
 else:
  url='https://push2his.eastmoney.com/api/qt/stock/kline/get?'+urllib.parse.urlencode({'secid':spec['symbol'],'klt':101,'fqt':0,'beg':'20000101','end':now.astimezone(ZoneInfo(spec['timezone'])).strftime('%Y%m%d'),'fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})
  parse=parse_eastmoney
 for attempt in range(3):
  try:
   request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
   with urllib.request.urlopen(request,timeout=30,context=ssl.create_default_context(cafile=certifi.where())) as response:raw=response.read()
   break
  except (OSError,TimeoutError):
   if attempt==2:raise
   time.sleep(2**attempt)
 (raw_dir/(spec['id']+'.json')).write_bytes(raw)
 rows,meta=parse(json.loads(raw),spec,now)
 last=next(r[0] for r in reversed(rows) if r[1] is not None)
 if (now.astimezone(ZoneInfo(spec['timezone'])).date()-date.fromisoformat(last)).days>21:raise ValueError('Latest completed session is more than 21 calendar days old')
 meta.update(download_url=url,source_url=spec['source_url'],retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),source_last_updated='',raw_sha256=hashlib.sha256(raw).hexdigest())
 return rows,meta

def collect(specs,data_dir,now=None):
 now=now or datetime.now(timezone.utc);run_id=now.strftime('%Y%m%dT%H%M%S%fZ');stamp=now.isoformat(timespec='seconds')
 path=data_dir/'daily_snapshot.json';old=json.loads(path.read_text()) if path.exists() else {'schema_version':1,'entries':[],'revisions':[]}
 if old['schema_version']!=1:raise ValueError('Unknown daily snapshot schema')
 ids=[s['id'] for s in specs];prior={e['spec']['id']:e for e in old['entries']}
 if len(ids)!=len(set(ids)) or set(prior)-set(ids):raise ValueError('Duplicate ID or catalog removal')
 for spec in specs:
  if spec['id'] in prior:
   for key in ['symbol','provider','timezone','currency','return_type']:
    if prior[spec['id']]['spec'].get(key)!=spec[key]:raise ValueError('Saved daily series definition changed: '+spec['id']+' '+key)
 raw_dir=data_dir/'daily_raw'/run_id;raw_dir.mkdir(parents=True,exist_ok=False)
 downloaded={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(fetch_one,s,raw_dir,now):s['id'] for s in specs}
  for future in concurrent.futures.as_completed(futures):
   try:downloaded[futures[future]]=future.result()
   except Exception as exc:downloaded[futures[future]]=exc
 entries=[];failures=[];revisions=list(old.get('revisions',[]))
 for s in specs:
  sid=s['id'];before=prior.get(sid,{'rows':[],'meta':{}})
  defaults={'series_id':sid,'country':s['country'],'country_name':s['country_name'],'indicator_zh':s['label'],'asset_class':'equity_index','frequency':'Daily, Close','unit':'Index','seasonal_adjustment':'Not Seasonally Adjusted','source_url':s['source_url'],'provider':s['provider'],'source_symbol':s['symbol'],'market_timezone':s['timezone'],'currency':s['currency'],'return_type':s['return_type'],'definition':s['definition'],'usage_note':'Public provider data for research. Original provider/index-owner terms apply; this project grants no additional data redistribution rights. Close only; no calendar filling. Current local session excluded.','last_checked_at_utc':stamp}
  try:
   fetched=downloaded[sid]
   if isinstance(fetched,Exception):raise fetched
   rows,meta=fetched
   _,changes=compare_rows(before['rows'],rows)
   for day,a,b,kind in changes:revisions.append({'run_id':run_id,'detected_at_utc':stamp,'series_id':sid,'observation_date':day,'old_value':a,'new_value':b,'change_type':kind})
   meta={**defaults,**meta,'update_status':'UPDATED'}
  except Exception as exc:
   rows=before['rows'];meta={**defaults,**before['meta'],'last_checked_at_utc':stamp,'update_status':'FAILED_RETAINED' if rows else 'FAILED_EMPTY','error':str(exc)}
   failures.append({'series_id':sid,'error':str(exc)})
  valid=[r[0] for r in rows if r[1] is not None]
  meta.update(first_observation=valid[0] if valid else None,last_observation=valid[-1] if valid else None,valid_rows=len(valid),missing_rows=len(rows)-len(valid))
  entries.append({'spec':{**s,'group':'Daily stock indices','asset_class':'equity_index'},'meta':meta,'rows':rows})
  print(sid,meta['update_status'],len(valid),meta.get('error',''),flush=True)
 result={'schema_version':1,'run_id':run_id,'completed_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'partial_failure' if failures else 'success','failures':failures,'entries':entries,'revisions':revisions}
 atomic_json(path,result);return result

if __name__=='__main__':
 specs=json.loads((ROOT/'updater/daily_catalog.json').read_text())['series']
 result=collect(specs,ROOT/'data')
 print(json.dumps({'status':result['status'],'series':len(result['entries']),'failures':result['failures']}))
 raise SystemExit(2 if result['failures'] else 0)
