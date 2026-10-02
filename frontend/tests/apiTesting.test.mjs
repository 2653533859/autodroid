import test from 'node:test'
import assert from 'node:assert/strict'
import { blankConfig, copy, effectiveStep, overridesFor, stepFromInterface, cloneStep, validateReferences, fromJson, toPlainJson, pathLabel, responseFields, requestSignatures, assertionSignature, mergeResponseFields, businessAssertion, referenceIssues, previewValue, failureSummary } from '../src/utils/apiTesting.js'
import { scheduledTaskExecution } from '../src/utils/scheduledTaskPresentation.js'

test('typed JSON preserves null, booleans and objects with reserved property names', () => {
  const result = fromJson({ kind: 'ref', step_id: 'literal-data', flag: false, nil: null, list: [0] })
  assert.equal(result.kind, 'object')
  assert.equal(result.fields.flag.value, false)
  assert.equal(result.fields.nil.value, null)
  assert.equal(result.fields.list.items[0].value, 0)
})
test('response sample fields retain nested paths, types and plaintext examples', () => {
  const fields = responseFields({ body: { data: { 'a.b': [{ token: 'private-token', count: 0, enabled: false, nil: null }] } } })
  const flatten = nodes => nodes.flatMap(node => [node, ...flatten(node.children)])
  const all = flatten(fields)
  assert.deepEqual(all.find(node => node.path.at(-1) === 'count').path, ['body', 'data', 'a.b', 0, 'count'])
  assert.equal(all.find(node => node.path.at(-1) === 'nil').type, 'null')
  assert.equal(all.find(node => node.path.at(-1) === 'enabled').type, 'boolean')
  assert.equal(all.find(node=>node.path.at(-1)==='token').example,'private-token')
  assert.ok(flatten(responseFields({ body: Array.from({ length: 3000 }, (_, i) => i) })).length < 2000)
})
test('step overrides preserve interface snapshots and replace complete JSON bodies', () => {
  const config = blankConfig()
  config.request.body = fromJson({ keep: 1, remove: 2 })
  const step = stepFromInterface({ id: 1, version: 2, name: '接口', config })
  const changed = copy(config)
  changed.request.body = fromJson({ keep: 3 })
  step.overrides = overridesFor(step.snapshot, changed)
  assert.deepEqual(effectiveStep(step).request.body, changed.request.body)
  assert.deepEqual(step.snapshot.request.body, config.request.body)
  assert.equal(cloneStep(step).interface_id, step.interface_id)
  assert.notEqual(cloneStep(step).id, step.id)
})
test('raw JSON round trips types and special keys without flattening runtime bindings', () => {
  const json = JSON.parse('{"__proto__":{"safe":true},"a.b":[false,0,null,{"kind":"env"}],"text":"{{BASE_URL}}"}')
  assert.deepEqual(toPlainJson(fromJson(json)), json)
  assert.equal(toPlainJson(fromJson(null)), null)
  for (const binding of [{ kind: 'env', name: 'TOKEN' }, { kind: 'ref', step_id: 'login', path: ['body'] }, { kind: 'template', parts: [] }]) {
    assert.throws(() => toPlainJson({ kind: 'object', fields: { credential: binding } }), /绑定/)
  }
})
test('references are stable across rename and rejected after reordering or deletion', () => {
  const first = stepFromInterface({ id: 1, name: '登录', version: 1, config: blankConfig() })
  const next = stepFromInterface({ id: 2, name: '订单', version: 1, config: blankConfig() })
  next.overrides = { request: { body_type:'json', body: { kind: 'ref', step_id: first.id, path: ['body', 'a.b', 0] } } }
  assert.deepEqual(validateReferences([first, next]), [])
  first.name = '已改名'
  assert.deepEqual(validateReferences([first, next]), [])
  assert.equal(validateReferences([next, first]).length, 1)
  assert.equal(validateReferences([next]).length, 1)
  assert.equal(pathLabel(['body', 'a.b', 0]), 'body › a.b › [0]')
})
test('scheduled API task is distinct from UI and does not require a device', () => {
  const summary = scheduledTaskExecution({ scenario_name: '订单回归', strategy_config: { _task_type: 'api', env_id: 2 } }, { environments: [{ id: 2, name: 'stage' }] })
  assert.equal(summary.type, 'api')
  assert.equal(summary.typeLabel, '接口自动化')
  assert.equal(summary.detail, '环境：stage · 无需设备')
})

test('request validity ignores metadata and assertion edits, invalidates changed requests and downstream',()=>{
  const a=stepFromInterface({id:1,name:'登录',version:1,config:blankConfig()}),b=cloneStep(a)
  const before=requestSignatures([a,b]),checks=assertionSignature(a)
  a.name='改名';a.response_schema={fields:[],source:'debug'}
  a.snapshot.assertions.push(businessAssertion({path:['body','id'],example:42},true))
  assert.deepEqual(requestSignatures([a,b]),before)
  assert.notEqual(assertionSignature(a),checks)
  a.snapshot.request.url=fromJson('https://example.test/new')
  const changed=requestSignatures([a,b]);assert.notEqual(changed[a.id],before[a.id]);assert.notEqual(changed[b.id],before[b.id])
  assert.notEqual(requestSignatures([b,a])[a.id],changed[a.id])
})
test('sample body never hides standard response roots and new assertions preserve actual scalar types',()=>{
  const body=responseFields({body:{items:[{flag:false}]}})
  assert.deepEqual(mergeResponseFields(body).map(f=>f.path[0]),['status_code','elapsed_ms','headers','cookies','body','text'])
  for(const value of [0,false,null,{id:2},[1,2]])assert.deepEqual(toPlainJson(businessAssertion({path:['body','value'],example:value},true).expected),value)
  assert.equal(businessAssertion({path:['body','status'],example:'created'},false).expected.value,'')
  for(const name of ['id','order_id','orderId','token','uuid','timestamp','created_at']){
    const recommended=businessAssertion({path:['body',name],example:42},true)
    assert.equal(recommended.op,'not_empty')
    assert.equal(recommended.expected.value,null)
  }
})
test('reference issues locate exact inputs and preview retains bindings without mutation',()=>{
  const step=stepFromInterface({id:1,name:'查询订单',version:1,config:blankConfig()})
  step.snapshot.request.body_type='json'
  step.snapshot.request.body={kind:'object',fields:{'a.b':{kind:'ref',step_id:'absent',path:['body','id']}}}
  const before=copy(step),issue=referenceIssues([step])[0]
  assert.equal(issue.section,'body');assert.deepEqual(issue.location,['request','body','fields','a.b'])
  assert.match(previewValue(step.snapshot.request.body)['a.b'],/运行时取值/)
  assert.deepEqual(step,before)
  assert.match(failureSummary({steps:[{name:'查询订单',status:'FAIL',detail:{assertions:[{path:['body','id'],op:'eq',expected:42,actual:0,passed:false,message:'值不相等'}]}}]}),/查询订单.*42.*0/)
})
test('inactive authentication and disabled parameters do not block scene references',()=>{
  const step=stepFromInterface({id:1,name:'请求',version:1,config:blankConfig()})
  const missing={kind:'ref',step_id:'removed',path:['body','token']}
  step.snapshot.request.auth.token=missing
  step.snapshot.request.headers=[{name:'AT',value:missing,enabled:false}]
  step.snapshot.assertions[0].expected=missing
  assert.deepEqual(referenceIssues([step]),[])
  step.snapshot.request.headers[0].enabled=true
  assert.deepEqual(referenceIssues([step])[0].location,['request','headers',0,'value'])
})
