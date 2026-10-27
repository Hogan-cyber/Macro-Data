"""Load data, construct weekly inputs and prepare chronological train/validation/test sets.

Default: daily market series only. Macro features require --include-revised-macro.
These are research examples, not a claim of historical point-in-time data.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
MARKETS=['NASDAQCOM','NASDAQ100','NASDAQSOX','SP500','DGS3MO','DGS2','DGS5','DGS10','DGS30','DFII10','T10Y2Y','T10Y3M','DFF','VIXCLS','DTWEXBGS','DEXCHUS','DCOILWTICO','DCOILBRENTEU','BAMLC0A0CM','BAMLH0A0HYM2']
PRICES=['NASDAQCOM','NASDAQ100','NASDAQSOX','SP500','DTWEXBGS','DEXCHUS']

def load_native(base=None):
    """base: local data directory or HTTPS directory; no credentials in code."""
    base=str(base or ROOT/'data').rstrip('/')
    obs=pd.read_csv(base+'/observations.csv',parse_dates=['date'])
    meta=pd.read_csv(base+'/dictionary.csv').set_index('series_id')
    if obs.duplicated(['series_id','date']).any(): raise ValueError('Duplicate observations')
    if not (obs.value.isna().astype(int)==obs.is_missing).all(): raise ValueError('Missing flag mismatch')
    return obs,meta

def make_weekly(obs,meta,include_macro=False,cutoff=None):
    # Exclude an incomplete current week; information cutoff is Saturday 00:00 UTC,
    # which is after the US Friday close. This does not claim exact source release time.
    cutoff=pd.Timestamp(cutoff or pd.Timestamp.now(tz='UTC').date())
    fridays=pd.date_range(obs.date.min(),cutoff-pd.Timedelta(days=1),freq='W-FRI')
    weekly=pd.DataFrame(index=fridays)
    for sid in MARKETS:
        rs=obs.loc[obs.series_id.eq(sid)].sort_values('date')
        if rs.empty: continue
        valid=rs.loc[rs.value.notna()].set_index('date').value
        # No bridging of a missing week. Each value must be observed that week.
        weekly[sid]=valid.resample('W-FRI').last().reindex(fridays)
    if include_macro:
        for sid,m in meta.iterrows():
            if sid in MARKETS: continue
            rs=obs.loc[obs.series_id.eq(sid),['date','value']].copy().sort_values('date')
            if rs.empty: continue
            frequency=str(m.frequency)
            if frequency.startswith('Monthly'):
                rs['assumed_available']=rs.date+pd.offsets.MonthEnd(0)+pd.Timedelta(days=45); age=120
            elif frequency.startswith('Quarterly'):
                rs['assumed_available']=rs.date+pd.offsets.QuarterEnd(0)+pd.Timedelta(days=100); age=240
            elif frequency.startswith('Weekly'):
                rs['assumed_available']=rs.date+pd.Timedelta(days=7); age=28
            else: continue
            merged=pd.merge_asof(pd.DataFrame({'week':fridays}),rs.sort_values('assumed_available'),
                left_on='week',right_on='assumed_available',direction='backward',tolerance=pd.Timedelta(days=age))
            weekly[sid]=merged.value.to_numpy()
    weekly.index.name='date'
    return weekly

def make_features(weekly,target='NASDAQCOM',horizon=4):
    if target not in weekly or horizon<1: raise ValueError('Invalid target or horizon')
    out=pd.DataFrame(index=weekly.index)
    for sid in weekly:
        base=weekly[sid].pct_change(fill_method=None)*100 if sid in PRICES else weekly[sid]
        out[sid+'_return_1w' if sid in PRICES else sid+'_level']=base
        for lag in [1,4,12]: out[f'{sid}_lag{lag}']=base.shift(lag)
        if sid not in PRICES: out[sid+'_change_1w']=base.diff()
    # Future return is the target, never a feature. Caller may choose another target definition.
    out['target']=100*(weekly[target].shift(-horizon)/weekly[target]-1)
    out['target_end']=pd.Series(weekly.index,index=weekly.index).shift(-horizon)
    out=out.replace([np.inf,-np.inf],np.nan)
    return out.loc[out.target.notna() & weekly[target].notna()]

def prepare_splits(frame,outdir):
    if len(frame)<50: raise ValueError('Need at least 50 labelled weeks')
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    a,b=int(len(frame)*.70),int(len(frame)*.85)
    val_start,test_start=frame.index[a],frame.index[b]
    train=frame.loc[(frame.index<val_start)&(frame.target_end<val_start)]
    val=frame.loc[(frame.index>=val_start)&(frame.index<test_start)&(frame.target_end<test_start)]
    test=frame.loc[frame.index>=test_start]
    features=[c for c in frame if c not in ['target','target_end'] and train[c].notna().any()]
    med=train[features].median(); filled=train[features].fillna(med)
    mean=filled.mean();std=filled.std(ddof=0).replace(0,1)
    params={c:{'median':float(med[c]),'mean':float(mean[c]),'std':float(std[c])} for c in features}
    for name,part in [('train',train),('validation',val),('test',test)]:
        missing=part[features].isna().astype(int).add_suffix('_missing')
        scaled=(part[features].fillna(med)-mean)/std
        pd.concat([scaled,missing,part[['target','target_end']]],axis=1).to_csv(outdir/f'{name}.csv',index_label='date')
    manifest={'rows':{'train':len(train),'validation':len(val),'test':len(test)},'validation_start':str(val_start.date()),
      'test_start':str(test_start.date()),'features':features,'train_only_parameters':params,
      'split_policy':'Chronological 70/15/15; purge labels ending on or after the next split start. Train-only median and population standard deviation.',
      'limitations':'Latest revised data, not full PIT. Macro availability, when enabled, is assumed rather than verified. No random split.'}
    (outdir/'preprocessing.json').write_text(json.dumps(manifest,indent=2,allow_nan=False))
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',help='Local data directory or HTTPS base URL')
    p.add_argument('--out',default=str(ROOT/'ml/output/python'))
    p.add_argument('--target',default='NASDAQCOM');p.add_argument('--horizon',type=int,default=4)
    p.add_argument('--include-revised-macro',action='store_true')
    a=p.parse_args();obs,meta=load_native(a.base)
    weekly=make_weekly(obs,meta,a.include_revised_macro)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    weekly.to_csv(out/'weekly_inputs.csv',index_label='date')
    frame=make_features(weekly,a.target,a.horizon)
    frame.to_csv(out/'features_before_split.csv',index_label='date')
    result=prepare_splits(frame,out)
    print(json.dumps({'rows':result['rows'],'features':len(result['features']),'macro_research_mode':a.include_revised_macro}))

if __name__=='__main__':main()
