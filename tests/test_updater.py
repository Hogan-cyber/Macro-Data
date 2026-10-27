import unittest, importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1]/'updater/update_us_macro.py'

class MacroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = None
        if SCRIPT.exists():
            spec=importlib.util.spec_from_file_location('update_us_macro',SCRIPT)
            cls.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.mod)
    def subject(self):
        self.assertIsNotNone(self.mod,'The updater has not been implemented')
        return self.mod
    def test_missing_and_zero_stay_distinct_and_dates_sort(self):
        m=self.subject()
        rows=m.parse_csv('observation_date,X\n2020-02-01,.\n2020-01-01,0\n2020-03-01,-2.5\n','X')
        self.assertEqual(rows,[['2020-01-01',0.0,0],['2020-02-01',None,1],['2020-03-01',-2.5,0]])
    def test_conflicting_duplicate_rejected(self):
        m=self.subject()
        with self.assertRaises(ValueError):m.parse_csv('observation_date,X\n2020-01-01,1\n2020-01-01,2\n','X')
    def test_wrong_header_and_infinity_rejected(self):
        m=self.subject()
        for data in ['date,Y\n2020-01-01,1\n','observation_date,X\n2020-01-01,inf\n']:
            with self.assertRaises(ValueError):m.parse_csv(data,'X')
    def test_yoy_uses_exact_month_not_twelve_prior_rows(self):
        m=self.subject()
        rows=[['2019-01-01',100,0],['2019-03-01',110,0],['2020-01-01',120,0],['2020-02-01',130,0]]
        got=m.derive_rows(rows,'yoy')
        self.assertAlmostEqual(got[2][1],20)
        self.assertIsNone(got[3][1])
    def test_nonfarm_difference_needs_adjacent_calendar_month(self):
        m=self.subject()
        rows=[['2020-01-01',100,0],['2020-03-01',150,0],['2020-04-01',0,0]]
        got=m.derive_rows(rows,'diff')
        self.assertIsNone(got[1][1]);self.assertEqual(got[2][1],-150)
    def test_revision_and_new_observation_separated(self):
        m=self.subject()
        old=[['2020-01-01',100,0],['2020-02-01',None,1]]
        new=[['2020-01-01',101,0],['2020-02-01',2,0],['2020-03-01',3,0]]
        counts,revisions=m.compare_rows(old,new)
        self.assertEqual(counts,{'new_rows':1,'changed_rows':2})
        self.assertEqual(revisions[0],['2020-01-01',100,101,'revised'])
        self.assertEqual(revisions[1][3],'filled_missing')
        self.assertEqual(m.compare_rows(new,new),({'new_rows':0,'changed_rows':0},[]))
    def test_truncated_response_rejected(self):
        m=self.subject()
        with self.assertRaises(ValueError):m.compare_rows([['2020-01-01',1,0],['2020-02-01',2,0]],[['2020-02-01',2,0]])
    def test_rolling_source_archives_old_dates_and_updates_new_overlap(self):
        m=self.subject()
        self.assertTrue(hasattr(m,'retain_rolling_history'),'Rolling source history merge is missing')
        old=[['2020-01-01',1,0],['2020-01-02',2,0],['2020-01-03',3,0]]
        new=[['2020-01-02',2,0],['2020-01-03',4,0],['2020-01-04',5,0]]
        merged=m.retain_rolling_history(old,new)
        self.assertEqual(merged,[old[0],*new])
        self.assertEqual(m.compare_rows(old,merged)[0],{'new_rows':1,'changed_rows':1})
    def test_rolling_source_still_rejects_internal_missing_dates(self):
        m=self.subject()
        self.assertTrue(hasattr(m,'retain_rolling_history'),'Rolling source history merge is missing')
        old=[['2020-01-01',1,0],['2020-01-02',2,0],['2020-01-03',3,0]]
        new=[old[0],old[2]]
        with self.assertRaises(ValueError):m.compare_rows(old,m.retain_rolling_history(old,new))

if __name__=='__main__':unittest.main()
