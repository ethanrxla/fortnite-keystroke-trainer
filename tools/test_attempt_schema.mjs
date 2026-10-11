// Node 22+ type stripping: node tools/test_attempt_schema.mjs
// Exercises the exact Edge Function validator without credentials or network.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {errors,keySummaryErrors} from '../supabase/functions/_shared/validate.ts';
const schema=JSON.parse(readFileSync(new URL('../shared/schemas/edit_attempt.v2.json',import.meta.url)));
const mirror=JSON.parse(readFileSync(new URL('../supabase/functions/_shared/edit_attempt.v2.json',import.meta.url)));
assert.deepEqual(schema,mirror);
const base={schema:'edit_attempt.v2',attempt_id:'00000000-0000-4000-8000-000000000001',session_id:'s',
 map_id:'keystroke_trainer',piece:'wall',piece_evidence:'observed',source:'screen',
 t_edit_open:100,t_close:101,final_tiles:[4],outcome:'selection_matched',
 auto_label_confidence:.8,label_status:'auto',selection_available:true,complete_observation:true,
 record_revision:1,result_confirmed:false,result_evidence:'unknown'};
assert.deepEqual(errors(base,schema),[]);
for(const change of [{t_close:99},{piece:'floor',final_tiles:[8]},{outcome:'result_verified'},
                    {final_tiles:[[0]]},{selection_trace:{}},{record_revision:0}]){
 assert.ok(errors({...base,...change},schema).length,JSON.stringify(change));
}
assert.deepEqual(errors({...base,outcome:'result_verified',result_confirmed:true,result_evidence:'authored'},schema),[]);
console.log('Schema mirror and 8 server-side validation cases passed.');
assert.deepEqual(keySummaryErrors({verdicts:{ok:2,unmapped:3}}),[]);
for(const value of [{keys:{secret:3}}, {verdicts:{'private-letter':1}}, {verdicts:{ok:-1}}, {verdicts:{ok:1.5}}])
  assert.ok(keySummaryErrors(value).length);
console.log('Anonymous key-summary privacy cases passed.');
