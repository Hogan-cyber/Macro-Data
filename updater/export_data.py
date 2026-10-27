"""Export one validated snapshot to native CSV, dashboard and revision files."""
import csv
import json
import math
import os
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]

def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def export(root=ROOT):
    data = root/'data'
    snapshot = json.loads((data/'latest_snapshot.json').read_text())
    rows, dictionary, statuses = [], [], []
    for e in snapshot['entries']:
        m=e['meta']; sid=e['spec']['id']; seen=set()
        for day,value,missing in e['rows']:
            date.fromisoformat(day)
            if day in seen or missing != int(value is None): raise ValueError(f'Invalid row: {sid} {day}')
            if value is not None and (isinstance(value,bool) or not math.isfinite(value)): raise ValueError('Invalid value')
            seen.add(day)
            rows.append(dict(series_id=sid,date=day,value=value,is_missing=missing))
        valid=[r for r in e['rows'] if r[1] is not None]
        dictionary.append(m)
        statuses.append({**m,'latest_value':valid[-1][1] if valid else None})
    if len({m['series_id'] for m in dictionary}) != len(dictionary): raise ValueError('Duplicate series')
    write_csv(data/'observations.csv',rows,['series_id','date','value','is_missing'])
    write_csv(data/'dictionary.csv',dictionary,snapshot['dictionary_headers'])
    write_csv(data/'revisions.csv',[dict(zip(snapshot['revision_headers'],r)) for r in snapshot['revisions']],snapshot['revision_headers'])
    write_csv(data/'refresh_log.csv',[dict(zip(snapshot['log_headers'],r)) for r in snapshot['logs']],snapshot['log_headers'])
    status={k:snapshot[k] for k in ['run_id','completed_at_utc','status','failures']}
    status['schedule']='Monday 08:00 Asia/Hong_Kong (00:00 UTC)'
    status['workflow_run_url']=f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}" if os.getenv('GITHUB_RUN_ID') else None
    (data/'refresh_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
    prior=json.loads((root/'src/data.json').read_text())
    upper=max(r['date'] for r in rows)
    source={'label':'FRED official downloads and source metadata','url':'https://fred.stlouisfed.org/',
      'executedAt':snapshot['completed_at_utc'],'coverage':{'startDate':min(r['date'] for r in rows),'endDate':upper},
      'caveats':['Latest revised values. Observation date is not publication date. No complete point-in-time history.',
                 'Units and seasonal adjustment vary by series. Missing values are retained.'],
      'evidenceFlow':[{'title':'Retrieve and verify','detail':'updater/update_us_macro.py; GET each dictionary.download_url and dictionary.source_url. Exact requested dates and SHA256 are archived in data/raw. Validate metadata, dates, duplicates and numeric values.'},
                      {'title':'Derive and export','detail':'CPI/PCE YoY uses exact same calendar month last year; PAYEMS_CHANGE subtracts the previous calendar month. Export without interpolation using updater/export_data.py.'}]}
    app={'id':prior['id'],'surface':'dashboard','title':'US Macro Monitor','status':'reviewed','buildStatus':'complete',
      'asOf':snapshot['completed_at_utc'][:10],'generatedAt':snapshot['completed_at_utc'],
      'exportPreferences':{'selected':None,'destinations':[]},
      'filters':[{'id':'date','field':'date','label':'Reference period','mode':'through','defaultValue':f'2020-01-01..{upper}','queryIds':['observations']}],
      'refresh':status,'queries':{'observations':{'rows':rows,'source':source},
        'dictionary':{'rows':statuses,'source':{'label':'Verified series metadata','executedAt':snapshot['completed_at_utc']}},
        'log':{'rows':[dict(zip(snapshot['log_headers'],r)) for r in snapshot['logs']],'source':{'label':'Refresh audit log'}},
        'revisions':{'rows':[dict(zip(snapshot['revision_headers'],r)) for r in snapshot['revisions']],'source':{'label':'Observed revisions since collection began'}}}}
    (root/'src/data.json').write_text(json.dumps(app,ensure_ascii=False,separators=(',',':'),allow_nan=False))
    (data/'dictionary.json').write_text(json.dumps(dictionary,ensure_ascii=False,indent=2))
    print(f'Validated {len(dictionary)} series, {len(rows)} observations; exported CSV and dashboard snapshot.')

if __name__=='__main__': export()
