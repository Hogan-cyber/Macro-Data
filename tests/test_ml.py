import unittest
import sys
from pathlib import Path
import tempfile
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ml'))
from prepare_python import make_weekly,make_features,prepare_splits

class ModelPreparationTests(unittest.TestCase):
    def test_missing_week_not_filled_and_incomplete_week_excluded(self):
        obs=pd.DataFrame({'series_id':['NASDAQCOM']*3,'date':pd.to_datetime(['2024-01-05','2024-01-19','2024-01-22']),'value':[100,110,999]})
        weekly=make_weekly(obs,pd.DataFrame(),cutoff='2024-01-24')
        self.assertTrue(pd.isna(weekly.loc['2024-01-12','NASDAQCOM']))
        self.assertEqual(str(weekly.index[-1].date()),'2024-01-19')
    def test_future_changes_cannot_change_past_features(self):
        dates=pd.date_range('2020-01-03',periods=120,freq='W-FRI')
        x=pd.DataFrame({'NASDAQCOM':np.arange(120)+100.,'DGS10':np.arange(120)/100+2},index=dates)
        a=make_features(x);x.loc[dates[90]:]=99999;b=make_features(x)
        cols=[c for c in a if c not in ['target','target_end']]
        pd.testing.assert_frame_equal(a.loc[:dates[89],cols],b.loc[:dates[89],cols])
    def test_purge_and_training_only_preprocessing(self):
        dates=pd.date_range('2020-01-03',periods=180,freq='W-FRI')
        w=pd.DataFrame({'NASDAQCOM':np.arange(180)+100.,'DGS10':np.arange(180)/100+2},index=dates)
        x=make_features(w)
        with tempfile.TemporaryDirectory() as d:
            a=prepare_splits(x,d);tr=pd.read_csv(Path(d)/'train.csv');va=pd.read_csv(Path(d)/'validation.csv');te=pd.read_csv(Path(d)/'test.csv')
            self.assertLess(tr.target_end.max(),va.date.min());self.assertLess(va.target_end.max(),te.date.min())
            x.loc[pd.Timestamp(a['validation_start']):,'DGS10_level']=999999
            b=prepare_splits(x,d)
            self.assertEqual(a['train_only_parameters'],b['train_only_parameters'])
    def test_macro_not_available_at_month_start(self):
        obs=pd.DataFrame({'series_id':['NASDAQCOM','CPI_YOY'],'date':pd.to_datetime(['2024-01-05','2024-01-01']),'value':[100,3]})
        meta=pd.DataFrame({'frequency':['Monthly']},index=['CPI_YOY'])
        w=make_weekly(obs,meta,True,cutoff='2024-04-01')
        self.assertTrue(w.loc[:'2024-03-15','CPI_YOY'].isna().all())
        self.assertEqual(w.loc['2024-03-22','CPI_YOY'],3)

if __name__=='__main__':unittest.main()
