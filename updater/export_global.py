"""Publish one consistent, validated global dataset in portable research formats."""
from __future__ import annotations
import csv,gzip,hashlib,json,math,os,sqlite3,tempfile,zipfile
from pathlib import Path
from datetime import date,datetime,timezone
import pandas as pd
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment

ROOT=Path(__file__).resolve().parents[1]
OBS=['series_id','country','date','value','is_missing','frequency','unit','seasonal_adjustment','retrieved_at_utc','release_date','update_status']
META=['series_id','country','country_name','indicator_zh','asset_class','category','frequency','unit','seasonal_adjustment','source_title','source_url','download_url','first_observation','last_observation','valid_rows','missing_rows','retrieved_at_utc','source_last_updated','update_status','definition','usage_note']
LIMITS=['Latest-revised observations, not complete historical point-in-time data.',
 'date identifies the observation period, NOT the publication date. release_date is NULL when unverified.',
 'Raw frequencies and units are retained. No interpolation, winsorization, forward-fill or automatic frequency conversion.',
 'OECD monthly share-price indices are normalized broad-market series, not daily FTSE/DAX/etc. index closes.',
 'Source retrieval time records this system acquisition, not the historical first public release.',
 'Country coverage and history differ. See dictionary and coverage.csv before joining features.']

def prepare(us,international):
    metadata=[];records=[];seen=set()
    for entry in us['entries']+international['entries']:
        spec=entry['spec'];m=entry['meta'];sid=spec['id']
        if sid in seen:raise ValueError('Duplicate series ID: '+sid)
        seen.add(sid)
        country=spec.get('country',m.get('country','US'))
        equity=sid in ['NASDAQCOM','NASDAQ100','NASDAQSOX','SP500']
        meta={k:m.get(k) for k in META}
        meta.update(series_id=sid,country=country,country_name=spec.get('country_name',m.get('country_name','United States')),
                    asset_class=spec.get('asset_class',m.get('asset_class','equity_index' if equity else 'macro')),
                    indicator_zh=spec.get('label',m.get('indicator_zh',sid)),category=spec.get('group',m.get('category','macro')))
        days=set();last=None;valid=[]
        for day,value,missing in entry['rows']:
            date.fromisoformat(day)
            if day in days or (last is not None and day<=last):raise ValueError('Dates must be unique and sorted: '+sid)
            if missing not in [0,1] or int(missing)!=int(value is None):raise ValueError('Invalid missing flag: '+sid)
            if value is not None and (isinstance(value,bool) or not math.isfinite(value)):raise ValueError('Invalid value: '+sid)
            days.add(day);last=day
            if value is not None:valid.append(day)
            records.append(dict(series_id=sid,country=country,date=day,value=value,is_missing=int(missing),
              frequency=meta['frequency'],unit=meta['unit'],seasonal_adjustment=meta['seasonal_adjustment'],
              retrieved_at_utc=meta['retrieved_at_utc'],release_date=None,update_status=meta['update_status']))
        meta.update(valid_rows=len(valid),missing_rows=len(days)-len(valid),first_observation=valid[0] if valid else None,last_observation=valid[-1] if valid else None)
        metadata.append(meta)
    return pd.DataFrame(records,columns=OBS),pd.DataFrame(metadata,columns=META)

def write_excel(path,obs,meta):
    # The user requested a portable Python updater: use the same engine as the US workbook.
    wb=Workbook();catalog=wb.active;catalog.title='Catalog'
    catalog.append(['sheet','series_id','country','indicator','frequency','unit','first','latest','valid','missing','status'])
    navy='17324D';teal='176B74'
    groups={sid:g for sid,g in obs.groupby('series_id',sort=False)}
    for i,m in enumerate(meta.to_dict('records'),1):
        name=f"{m['country']}_{i:03d}_{m['series_id']}"[:31]
        catalog.append([name,m['series_id'],m['country'],m['indicator_zh'],m['frequency'],m['unit'],m['first_observation'],m['last_observation'],m['valid_rows'],m['missing_rows'],m['update_status']])
        catalog.cell(i+1,1).hyperlink=f"#'{name}'!A1"
        ws=wb.create_sheet(name);ws.append(['observation_date','value','is_missing'])
        g=groups.get(m['series_id'])
        if g is not None:
            for r in g.itertuples(index=False):ws.append([date.fromisoformat(r.date),None if pd.isna(r.value) else r.value,r.is_missing])
        for n,k in enumerate(['series_id','country','indicator_zh','frequency','unit','seasonal_adjustment','source_url','retrieved_at_utc','update_status'],1):
            ws.cell(n,5,k);c=ws.cell(n,6,m[k]);c.data_type='s' if isinstance(m[k],str) else c.data_type
        for row in ws.iter_rows(min_row=2,max_col=2):row[0].number_format='yyyy-mm-dd';row[1].number_format='#,##0.0000'
        ws.column_dimensions['A'].width=20;ws.column_dimensions['B'].width=21;ws.column_dimensions['C'].width=16
        ws.column_dimensions['E'].width=24;ws.column_dimensions['F'].width=68
        ws.freeze_panes='A2';ws.auto_filter.ref=f'A1:C{len(g)+1 if g is not None else 1}'
    dictionary=wb.create_sheet('Dictionary');dictionary.append(META)
    for r in meta.where(pd.notna(meta),None).itertuples(index=False,name=None):dictionary.append(r)
    readme=wb.create_sheet('ReadMe');readme.append(['Topic','Definition'])
    for text in LIMITS:readme.append(['Research limits',text])
    readme.append(['Schedule','Monday 08:00 Asia/Hong_Kong. Cloud execution may queue. Each series retains its original frequency.'])
    readme.append(['Training','Fit scaling/imputation only on the training split. Validate release dates/vintages before historical backtests.'])
    for ws in wb:
        ws.sheet_view.showGridLines=False;ws.freeze_panes='A2'
        for c in ws[1]:c.font=Font(name='Arial',bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor=navy)
        ws.row_dimensions[1].height=26
        if ws.title in ['Catalog','Dictionary','ReadMe']:
            for col in ws.columns:
                letter=col[0].column_letter;ws.column_dimensions[letter].width=24 if letter!='D' else 46
            ws.auto_filter.ref=ws.dimensions
    readme.column_dimensions['B'].width=110
    for row in readme.iter_rows(min_row=2):row[1].alignment=Alignment(wrap_text=True,vertical='top');readme.row_dimensions[row[0].row].height=34
    wb.save(path)

def export(root=ROOT):
    data=root/'data';dest=data/'global';dest.mkdir(exist_ok=True)
    us=json.loads((data/'latest_snapshot.json').read_text());international=json.loads((data/'international_snapshot.json').read_text())
    obs,meta=prepare(us,international)
    generated=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    version=hashlib.sha256((us['run_id']+'|'+international['run_id']).encode()).hexdigest()[:20]
    with tempfile.TemporaryDirectory(prefix='global-export-',dir=data) as scratch:
        out=Path(scratch)
        obs.to_csv(out/'observations.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        obs.to_parquet(out/'observations.parquet',engine='pyarrow',index=False)
        obs.to_json(out/'observations.jsonl.gz',orient='records',lines=True,compression={'method':'gzip','mtime':0},double_precision=15)
        meta.to_csv(out/'dictionary.csv',index=False)
        meta.to_json(out/'dictionary.json',orient='records',force_ascii=False,indent=2)
        meta[['series_id','country','indicator_zh','asset_class','frequency','first_observation','last_observation','valid_rows','missing_rows','update_status']].to_csv(out/'coverage.csv',index=False)
        connection=sqlite3.connect(out/'dataset.sqlite');connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('CREATE TABLE series ('+', '.join(f'"{c}" '+('INTEGER' if c in ['valid_rows','missing_rows'] else 'TEXT')+(' PRIMARY KEY' if c=='series_id' else '') for c in META)+')')
        connection.execute('CREATE TABLE observations (series_id TEXT NOT NULL REFERENCES series(series_id),country TEXT NOT NULL,date TEXT NOT NULL,value REAL,is_missing INTEGER NOT NULL CHECK(is_missing IN (0,1)),frequency TEXT,unit TEXT,seasonal_adjustment TEXT,retrieved_at_utc TEXT,release_date TEXT,update_status TEXT,PRIMARY KEY(series_id,date),CHECK((is_missing=1 AND value IS NULL) OR (is_missing=0 AND value IS NOT NULL)))')
        meta.to_sql('series',connection,if_exists='append',index=False);obs.to_sql('observations',connection,if_exists='append',index=False,chunksize=5000)
        connection.execute('CREATE INDEX observations_country_date ON observations(country,date)')
        # Rows are detected revisions, never claimed to be original publication vintages.
        rev=[dict(zip(us['revision_headers'],r)) for r in us['revisions']]+international.get('revisions',[])
        fields=['run_id','detected_at_utc','series_id','observation_date','old_value','new_value','change_type']
        pd.DataFrame(rev,columns=fields).to_sql('revisions',connection,index=False)
        pd.DataFrame([{'dataset_version':version,'generated_at_utc':generated,'us_run_id':us['run_id'],'international_run_id':international['run_id'],'history_type':'latest_revised'}]).to_sql('dataset_info',connection,index=False)
        connection.commit()
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        assert connection.execute('SELECT COUNT(*) FROM observations').fetchone()[0]==len(obs)
        with gzip.open(out/'dataset.sql.gz','wt',encoding='utf-8') as f:
            for line in connection.iterdump():f.write(line+'\n')
        connection.close()
        write_excel(out/'global_macro.xlsx',obs,meta)
        (out/'README.txt').write_text('Global macro and equity research dataset\n'+f'Version: {version}\nGenerated: {generated}\n'+'\n'.join(LIMITS)+'\nSQLite tables: observations, series, revisions, dataset_info.\nSQL dump uses SQLite SQL syntax; gunzip before import.\n',encoding='utf-8')
        # Round-trip core formats; SQL dump is checked in integration tests.
        check=pd.read_parquet(out/'observations.parquet');pd.testing.assert_frame_equal(obs,check,check_dtype=False)
        manifest={'schema_version':1,'dataset_version':version,'generated_at_utc':generated,
          'countries':sorted(meta.country.unique().tolist()),'series_count':len(meta),'observation_count':len(obs),
          'valid_observation_count':int(obs.value.notna().sum()),'status':'PARTIAL' if us['failures'] or international['failures'] else 'SUCCESS',
          'failures':us['failures']+international['failures'],'limitations':LIMITS,
          'files':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(out.iterdir())}}
        # The archive contains a manifest for its contents, so extraction is a
        # complete offline SDK dataset. Its manifest excludes the archive itself.
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(out/'bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.iterdir()):
                if p.name!='bundle.zip':z.write(p,p.name)
        bundle=out/'bundle.zip'
        manifest['files']['bundle.zip']={'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),'bytes':bundle.stat().st_size}
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        for p in out.iterdir():
            if p.name!='manifest.json':os.replace(p,dest/p.name)
        os.replace(out/'manifest.json',dest/'manifest.json')
    # Append global queries without changing existing US chart scope, identity or period filter.
    path=root/'src/data.json';app=json.loads(path.read_text())
    app['title']='Global Macro Monitor';app['globalDataset']=manifest
    app['generatedAt']=generated
    for definition in app.get('filters',[]):
        if definition['id']=='date':
            definition['queryIds']=['observations','globalObservations']
            definition['defaultValue']=definition['defaultValue'].split('..')[0]+'..'+obs.date.max()
    slim=obs[['series_id','country','date','value','is_missing']].astype(object).where(pd.notna(obs),None).to_dict('records')
    app['queries']['globalObservations']={'rows':slim,'source':{'label':'FRED / OECD and World Bank official data','executedAt':generated,'caveats':LIMITS,'evidenceFlow':[{'title':'Reproduce','detail':'python updater/international.py; python updater/export_data.py; python updater/export_global.py. Exact URLs, units, frequencies and acquisition timestamps are in dictionary.csv.'}]}}
    app['queries']['globalDictionary']={'rows':meta.astype(object).where(pd.notna(meta),None).to_dict('records'),'source':{'label':'Global series catalog','executedAt':generated}}
    path.write_text(json.dumps(app,ensure_ascii=False,allow_nan=False,separators=(',',':')))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['files','limitations','failures']},ensure_ascii=False))
    return manifest

if __name__=='__main__':export()
