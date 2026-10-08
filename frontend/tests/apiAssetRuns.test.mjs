import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref, computed, watch, effectScope } from 'vue'
import * as utilities from '../src/utils/apiTesting.js'

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve() }
function setup(t, post) {
  const source = readFileSync(new URL('../src/views/api-testing/AssetList.vue', import.meta.url), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*\n/gm, '')
  const calls = [], navigation = [], messages = [], lifecycle = [], scope = effectScope()
  const dependencies = {
    ...utilities, ref, computed, watch, onMounted: () => {}, onBeforeUnmount: fn => lifecycle.push(fn), useRoute: () => ({ path: '/api-testing/scenarios' }),
    useRouter: () => ({ push: async path => navigation.push(path) }), useUserStore: () => ({ isAdmin: false, userInfo: { id: 1 } }),
    ElMessage: Object.fromEntries(['error', 'warning', 'success'].map(kind => [kind, text => messages.push({ kind, text })])),
    api: { apiTesting: { post: async (path, payload) => { calls.push({ path, payload: utilities.copy(payload) }); return post?.(path, payload) || { data: path === '/precheck' ? { errors: [] } : { id: 'run-1' } } } } },
  }
  const factory = new Function(...Object.keys(dependencies), source + '\nreturn {run,runItem,runEnv,runNotify,running,runDialog,runStage};')
  const state = scope.run(() => factory(...Object.values(dependencies)))
  t.after(() => scope.stop())
  state.runItem.value = { id: 41, name: 'Checkout', version: 7, steps: [], env_id: 1 }
  state.runEnv.value = 2; state.runNotify.value = true; state.runDialog.value = true
  return { state, calls, navigation, messages, unmount: () => lifecycle.forEach(fn => fn()) }
}

test('list run freezes the selected scenario, environment and notification and rejects repeated clicks', async t => {
  const check = deferred(), submission = deferred()
  const context = setup(t, path => path === '/precheck' ? check.promise : submission.promise)
  const pending = context.state.run(); await flush()
  assert.equal(context.state.running.value, true)
  await context.state.run()
  assert.equal(context.calls.length, 1)
  assert.deepEqual(context.calls[0].payload,{name:'Checkout',steps:[],env_id:2,validation_mode:'run'})
  context.state.runItem.value.id = 90; context.state.runItem.value.version = 9
  context.state.runEnv.value = 3; context.state.runNotify.value = false
  check.resolve({ data: { errors: [] } }); await flush()
  assert.deepEqual(context.calls[1], { path: '/scenarios/41/runs', payload: { version: 7, env_id: 2, notify: true } })
  await context.state.run()
  assert.equal(context.calls.length, 2)
  submission.resolve({ data: { id: 'frozen-run' } }); await pending
  assert.deepEqual(context.navigation, ['/execution/reports/api/frozen-run'])
  assert.equal(context.state.running.value, false)
})

test('failed list precheck retains dialog and prevents a run request', async t => {
  const context = setup(t, () => ({ data: { errors: [{ message: '缺少断言' }] } }))
  await context.state.run()
  assert.equal(context.calls.length, 1)
  assert.equal(context.state.runDialog.value, true)
  assert.equal(context.state.running.value, false)
  assert.equal(context.state.runStage.value, '')
  assert.equal(context.messages[0].text, '缺少断言')
})

test('failed run submission unlocks retry without losing the selected environment', async t => {
  let attempts = 0
  const context = setup(t, path => {
    if (path === '/precheck') return { data: { errors: [] } }
    if (++attempts === 1) return Promise.reject(new Error('temporary error'))
    return { data: { id: 'retry-run' } }
  })
  await context.state.run()
  assert.equal(context.state.running.value, false)
  assert.equal(context.state.runDialog.value, true)
  assert.equal(context.state.runEnv.value, 2)
  await context.state.run()
  assert.equal(attempts, 2)
  assert.deepEqual(context.navigation, ['/execution/reports/api/retry-run'])
})

test('leaving the list while precheck is pending never launches a late run', async t => {
  const checking=deferred()
  const context=setup(t,()=>checking.promise)
  const pending=context.state.run()
  context.unmount()
  checking.resolve({data:{errors:[]}})
  await pending
  assert.equal(context.calls.length,1)
  assert.equal(context.state.running.value,false)
  assert.deepEqual(context.navigation,[])
})
