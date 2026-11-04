import test from 'node:test';
import assert from 'node:assert/strict';
import {inPeriod,indexed,yieldCurve} from '../src/content/dashboard/macro.js';
import {marketScope,observationPeriod,chartPeriod,latestPair,seriesLabel} from '../src/content/dashboard/regions.js';
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
test('market scope separates mainland China and Hong Kong and bounds Europe',()=>{
 const countries=['US','CN','HK','DE','FR','GB','JP'];
 const catalog=countries.map(country=>({country,series_id:country+'-A'}));
 const rows=catalog.map(m=>({...m,date:'2026-11-03',value:100}));
 assert.deepEqual(marketScope('china',catalog,rows).rows.map(r=>r.country),['CN']);
 assert.deepEqual(marketScope('hong-kong',catalog,rows).catalog.map(r=>r.country),['HK']);
 assert.deepEqual(marketScope('europe',catalog,rows).rows.map(r=>r.country),['DE','FR','GB']);
 assert.equal(marketScope('unknown',catalog,rows).rows.length,0);
});
test('period labels identify native frequency rather than suggesting publication dates',()=>{
 assert.equal(observationPeriod('2025-01-01','Annual'),'2025 · Annual');
 assert.equal(observationPeriod('2026-09-01','Monthly'),'Sep 2026 · Monthly');
 assert.equal(observationPeriod('2026-07-01','Quarterly'),'2026 Q3 · Quarterly');
 assert.equal(observationPeriod('2026-11-03','Daily, Close'),'3 Nov 2026 · Daily close');
 assert.equal(observationPeriod(null,'Annual'),'No data in selected period');
});
test('latest comparisons retain zero, ignore missing and remain within the chosen period',()=>{
 const rows=[{date:'2024-01-01',value:-2},{date:'2026-01-01',value:null},{date:'2025-01-01',value:0},{date:'2023-01-01',value:3}];
 assert.deepEqual(latestPair(rows),{current:rows[2],previous:rows[0],delta:2});
 assert.deepEqual(latestPair(inPeriod(rows,'2026-01-01..2026-12-31')),{current:null,previous:null,delta:null});
 assert.equal(latestPair(inPeriod(rows,'2025-01-01..2025-12-31')).previous,null);
 assert.deepEqual(rows.map(r=>r.date),['2024-01-01','2026-01-01','2025-01-01','2023-01-01']);
});
test('macro names retain national scope and the ILO estimate definition',()=>{
 assert.equal(seriesLabel({series_id:'WB_HK_UNEMPLOYMENT',country:'HK'}),'Hong Kong · Unemployment (ILO estimate)');
 assert.equal(seriesLabel({series_id:'DAX'}),'DAX (gross total return)');
});
test('chart periods retain annual years and monthly periods without changing source dates',()=>{
 assert.equal(chartPeriod('2025-01-01','Annual'),'2025');
 assert.equal(chartPeriod('2026-09-01','Monthly'),'2026-09');
 assert.equal(chartPeriod('2026-11-03','Daily, Close'),'2026-11-03');
});
