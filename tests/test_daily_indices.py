import copy,json,tempfile,unittest,sys
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'updater'))
import daily_indices as d

SPEC={'id':'HSI','symbol':'^HSI','country':'HK','country_name':'Hong Kong','label':'Hang Seng Index','provider':'yahoo','timezone':'Asia/Hong_Kong','currency':'HKD','return_type':'price','expected_name':'HANG SENG'}
SPEC.update(source_url='https://finance.yahoo.com/quote/%5EHSI/history/',definition='Daily price index close')
NOW=datetime(2026,11,4,5,tzinfo=timezone.utc)
def payload():
 return {'chart':{'error':None,'result':[{'meta':{'symbol':'^HSI','instrumentType':'INDEX','exchangeTimezoneName':'Asia/Hong_Kong','currency':'HKD','shortName':'HANG SENG INDEX'},'timestamp':[1793669400,1793755800],'indicators':{'quote':[{'close':[26000,26100]}]}}]}}

class DailyTests(unittest.TestCase):
 def test_excludes_current_local_session_and_uses_close(self):
  rows,meta=d.parse_yahoo(payload(),SPEC,NOW)
  self.assertEqual(rows,[['2026-11-03',26000,0]])
 def test_identity_and_lengths_checked(self):
  for mutate in [lambda x:x['chart']['result'][0]['meta'].update(symbol='WRONG'),lambda x:x['chart']['result'][0]['indicators']['quote'][0].update(close=[])]:
   p=payload();mutate(p)
   with self.assertRaises(ValueError):d.parse_yahoo(p,SPEC,NOW)
 def test_missing_zero_and_nonfinite(self):
  p=payload();p['chart']['result'][0]['indicators']['quote'][0]['close'][0]=None
  with self.assertRaises(ValueError):d.parse_yahoo(p,SPEC,NOW)
  for value in [0,True,float('nan')]:
   p=payload();p['chart']['result'][0]['indicators']['quote'][0]['close'][0]=value
   with self.assertRaises(ValueError):d.parse_yahoo(p,SPEC,NOW)
 def test_duplicate_dates_rejected(self):
  p=payload();p['chart']['result'][0]['timestamp']=[1793669400,1793669400]
  with self.assertRaises(ValueError):d.parse_yahoo(p,SPEC,NOW)
 def test_eastmoney_close_not_open(self):
  spec={**SPEC,'id':'CSI300','symbol':'1.000300','provider':'eastmoney','expected_name':'沪深300','timezone':'Asia/Shanghai','currency':'CNY'}
  p={'rc':0,'data':{'code':'000300','market':1,'name':'沪深300','klines':['2026-11-03,4000,4010,4020,3990,1,1,1,1,1,1','2026-11-04,4020,4030,4040,4000,1,1,1,1,1,1']}}
  rows,meta=d.parse_eastmoney(p,spec,NOW);self.assertEqual(rows,[['2026-11-03',4010,0]])
  p['data']['code']='000905'
  with self.assertRaises(ValueError):d.parse_eastmoney(p,spec,NOW)
 def test_retains_prior_values_on_error_or_truncation(self):
  for fetched in [RuntimeError('offline'),([['2026-11-03',26000,0]],{})]:
   with self.subTest(fetched=fetched),tempfile.TemporaryDirectory() as t:
    root=Path(t);old={'spec':SPEC,'meta':{'retrieved_at_utc':'2026-11-01T00:00:00Z'},'rows':[['2026-11-02',25000,0],['2026-11-03',26000,0]]}
    (root/'daily_snapshot.json').write_text(json.dumps({'schema_version':1,'entries':[old],'revisions':[]}))
    with patch.object(d,'fetch_one',return_value=fetched) if not isinstance(fetched,Exception) else patch.object(d,'fetch_one',side_effect=fetched):
     result=d.collect([SPEC],root,now=NOW)
    self.assertEqual(result['entries'][0]['rows'],old['rows'])
    self.assertEqual(result['entries'][0]['meta']['retrieved_at_utc'],old['meta']['retrieved_at_utc'])
    self.assertEqual(result['status'],'partial_failure')

if __name__=='__main__':unittest.main()
