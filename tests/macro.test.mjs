import test from 'node:test';
import assert from 'node:assert/strict';
import {inPeriod,indexed,yieldCurve} from '../src/content/dashboard/macro.js';
test('reference period filters all native frequencies and retains null',()=>{
 const rows=[{date:'2020-01-01',value:0},{date:'2024-01-01',value:null},{date:'2024-06-01',value:2}];
 assert.deepEqual(inPeriod(rows,'2024-01-01..2024-03-01'),[rows[1]]);
});
test('index comparisons share the same actual baseline date',()=>{
 const rows=[{series_id:'A',date:'2020-01-01',value:1},{series_id:'A',date:'2020-01-02',value:2},{series_id:'B',date:'2020-01-02',value:5},{series_id:'A',date:'2020-01-03',value:4}];
 const r=indexed(rows,['A','B']);assert.deepEqual(r.map(x=>x.value),[100,100,200]);
});
test('curve uses one common day rather than mixing latest dates',()=>{
 const rows=['DGS3MO','DGS2','DGS5','DGS10','DGS30'].map((id,i)=>({series_id:id,date:'2024-01-02',value:i}));
 rows.push({series_id:'DGS10',date:'2024-01-03',value:99});
 assert.equal(yieldCurve(rows).length,5);assert.ok(yieldCurve(rows).every(r=>r.date==='2024-01-02'));
});
