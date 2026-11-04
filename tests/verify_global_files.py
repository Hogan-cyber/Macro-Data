"""Integration check of published formats, SQL import and SDK local access."""
from pathlib import Path
import gzip,hashlib,json,sqlite3,zipfile,tempfile
import pandas as pd
from openpyxl import load_workbook
from hogan_macro import MacroData
root=Path(__file__).resolve().parents[1]/'data/global'
m=json.loads((root/'manifest.json').read_text())
for filename,info in m['files'].items():
    raw=(root/filename).read_bytes()
    assert len(raw)==info['bytes'] and hashlib.sha256(raw).hexdigest()==info['sha256'],filename
obs=pd.read_parquet(root/'observations.parquet')
assert len(obs)==m['observation_count'] and obs.value.notna().sum()==m['valid_observation_count']
assert not obs.duplicated(['series_id','date']).any()
assert (obs.value.isna().astype(int)==obs.is_missing).all()
assert obs.release_date.isna().all()
csv=pd.read_csv(root/'observations.csv.gz',keep_default_na=False,na_values=[''])
def equivalent(left,right):
    left=left.astype(object).where(pd.notna(left),None)
    right=right.astype(object).where(pd.notna(right),None)
    pd.testing.assert_frame_equal(left,right,check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-12)
equivalent(obs,csv)
jsonl=pd.read_json(root/'observations.jsonl.gz',lines=True,convert_dates=False,dtype=False)
equivalent(obs,jsonl)
with sqlite3.connect(':memory:') as con:
    with gzip.open(root/'dataset.sql.gz','rt') as f:con.executescript(f.read())
    assert con.execute('SELECT COUNT(*) FROM observations').fetchone()[0]==len(obs)
    assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    equivalent(obs,pd.read_sql_query('SELECT * FROM observations ORDER BY rowid',con))
wb=load_workbook(root/'global_macro.xlsx',read_only=True,data_only=True)
assert len(wb.sheetnames)==m['series_count']+3
catalog=list(wb['Catalog'].iter_rows(min_row=2,values_only=True));counts=0
by_id={sid:rs for sid,rs in obs.groupby('series_id')}
for c in catalog:
    rows=[r for r in wb[c[0]].iter_rows(min_row=2,max_col=3,values_only=True) if r[0] is not None];expected=by_id.get(c[1],pd.DataFrame())
    assert len(rows)==len(expected)
    for (d,v,flag),r in zip(rows,expected.itertuples(index=False)):
        assert d.date().isoformat()==r.date and flag==r.is_missing
        assert (v is None and pd.isna(r.value)) or abs(v-r.value)<=max(1e-10,abs(r.value)*1e-12)
    counts+=len(rows)
wb.close();assert counts==len(obs)
with tempfile.TemporaryDirectory() as scratch,zipfile.ZipFile(root/'bundle.zip') as z:
    assert z.testzip() is None
    z.extractall(scratch)
    offline=MacroData(data_dir=scratch)
    assert len(offline.catalog())==m['series_count']
    assert offline.manifest['dataset_version']==m['dataset_version']
client=MacroData(data_dir=root)
assert len(client.catalog())==m['series_count']
assert len(client.load(country='US'))==len(obs[obs.country=='US'])
assert int(client.sql('SELECT COUNT(*) AS n FROM observations').iloc[0,0])==len(obs)
print(f'Validated hashes, CSV/Parquet/JSONL/SQLite/SQL import/Excel, offline ZIP and SDK: {m["series_count"]} series, {counts} observations.')
