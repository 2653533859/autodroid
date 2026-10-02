import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref, computed, watch, effectScope, nextTick, reactive } from 'vue'
import * as utilities from '../src/utils/apiTesting.js'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
async function settle() { await nextTick(); for (let i = 0; i < 18; i++) await Promise.resolve() }

// Exercise the production setup functions with Vue reactivity. Route changes
// are observed explicitly because the app keys editor instances by fullPath.
function setup(t, name = 'ScenarioEditor', overrides = {}) {
  const source = readFileSync(new URL(`../src/views/api-testing/${name}.vue`, import.meta.url), 'utf8')
    .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*\n/gm, '')
  const calls = [], navigation = [], messages = [], lifecycle = [], mounted = [], timeline = [], scope = effectScope()
  const route = reactive({ params: {}, query: {}, path: name === 'ScenarioEditor' ? '/api-testing/scenarios/create' : '/api-testing/interfaces/create', ...overrides.route })
  const router = Object.fromEntries(['replace', 'push'].map(method => [method, async target => {
    navigation.push({ method, target: utilities.copy(target) }); timeline.push(`router.${method}`)
  }]))
  let sequence = 0
  const savedRows = new Map()
  const api = {
    getEnvironments: async () => ({ data: [{ id: 1, name: '默认环境' }, { id: 2, name: '临时环境' }] }),
    getVariables: async () => ({ data: [] }),
    apiTesting: {
      async get(path) {
        if (path === '/folders') return { data: [] }
        if (path === '/notification-status') return { data: { configured: true } }
        return { data: utilities.copy(savedRows.get(path)) }
      },
      async post(path, payload) {
        calls.push({ method: 'post', path, payload: utilities.copy(payload) }); timeline.push(`post:${path}`)
        const custom = overrides.post?.(path, payload)
        if (custom !== undefined) return custom
        if (path === '/precheck') return { data: { errors: [] } }
        if (path === '/scenarios' || path === '/interfaces') {
          const data = { ...utilities.copy(payload), id: 41, version: 1, sample: payload.sample || null, sample_fields: [] }
          savedRows.set(`${path}/41`, data)
          return { data }
        }
        if (path.endsWith('/runs')) return { data: { id: 'run-created' } }
        return { data: {} }
      },
      async put(path, payload) {
        calls.push({ method: 'put', path, payload: utilities.copy(payload) }); timeline.push(`put:${path}`)
        const data = { ...utilities.copy(payload), id: 41, version: payload.version + 1, sample: payload.sample || null, sample_fields: [] }
        savedRows.set(path, data); return { data }
      },
    },
  }
  const debugCalls = []
  const debug = { id: ref(null), editorId: 'debug-editor', running: ref(false), rechecking: ref(false),
    displayResults: ref({}), results: ref({}), staleIds: ref(new Set()), pendingIds: ref(new Set()),
    close: async () => {}, run: (...args) => debugCalls.push(args), recheck: async () => {} }
  const dependencies = { ...utilities, ref, computed, watch, nextTick, provide: () => {},
    onMounted: fn => mounted.push(fn), onBeforeUnmount: fn => lifecycle.push(fn),
    useRoute: () => route, useRouter: () => router, useUnsavedGuard: () => {}, useApiDebug: () => debug,
    createUuid: () => `uuid-${++sequence}`, api,
    ElMessage: Object.fromEntries(['error', 'warning', 'success'].map(kind => [kind, text => messages.push({ kind, text })])),
    ElMessageBox: { confirm: async (...args) => { timeline.push('confirm'); return overrides.confirm?.(...args) } },
  }
  const common = ['form', 'saved', 'id', 'dirty', 'loading', 'envId', 'load', 'save']
  const exports = name === 'ScenarioEditor' ? [...common, 'run', 'runStarting', 'temporaryEnvironment', 'temporaryEnvId', 'notify', 'selectedId', 'runStep'] : [...common, 'joinScenario', 'joinOpen']
  const script = new Function(...Object.keys(dependencies), `${source}\nreturn {${exports.join(',')}};`)
  const state = scope.run(() => script(...Object.values(dependencies)))
  const unmount = () => { lifecycle.forEach(fn => fn()); scope.stop() }
  t.after(unmount)
  state.saved.value = JSON.stringify(state.form.value)
  state.form.value.name = '首次创建'
  if (name === 'ScenarioEditor') {
    const step = utilities.localRequestStep(); step.id = 'first'; step.snapshot.request.url = utilities.literal('https://example.test')
    state.form.value.steps = [step]; state.selectedId.value = step.id; state.form.value.env_id = 1
  } else state.form.value.config.request.url = utilities.literal('https://example.test')
  return { state, calls, navigation, messages, timeline, route, debugCalls, mounted, unmount }
}

test('first save-and-run has no intermediate editor remount and locks repeated clicks through submission', async t => {
  const confirm = deferred(), run = deferred()
  const context = setup(t, 'ScenarioEditor', { confirm: () => confirm.promise,
    post: path => path.endsWith('/runs') ? run.promise : undefined })
  const pending = context.state.run(); await settle()
  assert.equal(context.state.runStarting.value, true)
  assert.equal(context.calls.filter(call => call.path === '/scenarios').length, 1)
  assert.equal(context.navigation.length, 0, 'saving before run must not remount the editor')
  await context.state.run()
  assert.equal(context.calls.filter(call => call.path === '/precheck').length, 1)
  confirm.resolve(); await settle()
  assert.equal(context.calls.filter(call => call.path.endsWith('/runs')).length, 1)
  assert.equal(context.navigation.length, 0)
  await context.state.run()
  assert.equal(context.calls.filter(call => call.path.endsWith('/runs')).length, 1)
  run.resolve({ data: { id: 'only-run' } }); await pending
  assert.ok(context.navigation.some(item => item.method === 'push' && item.target === '/execution/reports/api/only-run'))
  assert.equal(context.state.runStarting.value, false)
})

test('first run submits the frozen temporary environment and notification without saving them as defaults', async t => {
  const confirm = deferred()
  const context = setup(t, 'ScenarioEditor', { confirm: () => confirm.promise })
  context.state.temporaryEnvironment.value = true
  context.state.temporaryEnvId.value = 2
  context.state.notify.value = true
  const pending = context.state.run(); await settle()
  assert.equal(context.calls.find(call => call.path === '/precheck').payload.env_id, 2)
  assert.equal(context.calls.find(call => call.path === '/scenarios').payload.env_id, 1)
  // Simulate a late asynchronous update while the confirmation is open.
  context.state.temporaryEnvId.value = 3
  context.state.notify.value = false
  confirm.resolve(); await pending
  const sent = context.calls.find(call => call.path.endsWith('/runs'))
  assert.deepEqual(sent.payload, { env_id: 2, version: 1, notify: true })
  assert.equal(context.state.form.value.env_id, 1)
})

test('failed initial run normalizes the saved editor only after failure and never starts another run', async t => {
  const failure = deferred()
  const context = setup(t, 'ScenarioEditor', { post: path => path.endsWith('/runs') ? failure.promise : undefined })
  const pending = context.state.run(); await settle()
  assert.equal(context.navigation.length, 0)
  failure.reject(new Error('run endpoint unavailable')); await pending; await settle()
  assert.equal(context.calls.filter(call => call.path === '/scenarios').length, 1)
  assert.equal(context.calls.filter(call => call.path.endsWith('/runs')).length, 1)
  assert.equal(context.navigation.filter(item => item.method === 'push').length, 0)
  assert.ok(context.navigation.some(item => item.method === 'replace' && (item.target.path || item.target) === '/api-testing/scenarios/41/edit'))
  assert.equal(context.state.runStarting.value, false)
})

test('cancel after first save never sends a run and keeps the created scenario available', async t => {
  const context = setup(t, 'ScenarioEditor', { confirm: () => Promise.reject('cancel') })
  await context.state.run(); await settle()
  assert.equal(context.calls.filter(call => call.path === '/scenarios').length, 1)
  assert.equal(context.calls.filter(call => call.path.endsWith('/runs')).length, 0)
  assert.ok(context.navigation.some(item => item.method === 'replace' && (item.target.path || item.target) === '/api-testing/scenarios/41/edit'))
  assert.equal(context.state.runStarting.value, false)
})

test('first interface save carries the join intent to the new editor and rejects reentrant saves', async t => {
  const saving = deferred()
  const context = setup(t, 'InterfaceEditor', { post: path => path === '/interfaces' ? saving.promise : undefined })
  const pending = context.state.joinScenario(); await settle()
  await context.state.joinScenario()
  assert.equal(context.calls.filter(call => call.path === '/interfaces').length, 1)
  const submitted = context.calls.find(call => call.path === '/interfaces').payload
  saving.resolve({ data: { ...submitted, id: 41, version: 1, sample: null, sample_fields: [] } }); await pending
  assert.equal(context.navigation.length, 1)
  assert.deepEqual(context.navigation[0], { method: 'replace', target: { path: '/api-testing/interfaces/41/edit', query: { open: 'join' } } })
  assert.equal(context.state.loading.value, false)
})

test('slow scenario precheck cannot silently switch debugging to another selected step', async t => {
  const checking = deferred()
  const context = setup(t, 'ScenarioEditor', { post: path => path === '/precheck' ? checking.promise : undefined })
  const second = utilities.localRequestStep(); second.id = 'second'; second.snapshot.request.url = utilities.literal('https://example.test/second')
  context.state.form.value.steps.push(second)
  const pending = context.state.runStep('single')
  context.state.selectedId.value = 'second'
  checking.resolve({ data: { errors: [] } }); await pending; await settle()
  assert.equal(context.debugCalls.some(([stepId]) => stepId === 'second'), false)
})

test('failed precheck keeps an incoming interface draft without clearing its route or saving it', async t => {
  const context = setup(t, 'ScenarioEditor', {
    route: { params: { id: '41' }, query: { add_interface: '7' }, path: '/api-testing/scenarios/41/edit' },
    post: path => path === '/precheck' ? { data: { errors: [{ step_id: 'first', section: 'assertions', location: ['assertions'], message: '缺少校验' }] } } : undefined,
  })
  const original = utilities.copy(context.state.form.value)
  await context.state.run()
  assert.deepEqual(context.state.form.value, original)
  assert.deepEqual(context.route.query, { add_interface: '7' })
  assert.equal(context.calls.filter(call => call.path.endsWith('/runs') || call.method === 'put').length, 0)
  assert.equal(context.navigation.length, 0)
})

test('unmount while the first scenario save is pending cannot open confirmation or start a run', async t => {
  const saving = deferred()
  const context = setup(t, 'ScenarioEditor', { post: path => path === '/scenarios' ? saving.promise : undefined })
  const pending = context.state.run(); await settle()
  const submitted = context.calls.find(call => call.path === '/scenarios').payload
  context.unmount()
  saving.resolve({ data: { ...submitted, id: 41, version: 1 } }); await pending
  assert.equal(context.timeline.includes('confirm'), false)
  assert.equal(context.calls.filter(call => call.path.endsWith('/runs')).length, 0)
  assert.equal(context.navigation.length, 0)
})
