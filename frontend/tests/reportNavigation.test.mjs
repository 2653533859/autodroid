import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { runInNewContext } from 'node:vm'
import test from 'node:test'

const reportSource = await readFile(new URL('../src/views/reports/ReportList.vue', import.meta.url), 'utf8')
const taskSource = await readFile(new URL('../src/views/tasks/TaskList.vue', import.meta.url), 'utf8')

function functionFrom(source, name, nextName, bindings) {
  const start = source.indexOf(`const ${name} =`)
  const end = source.indexOf(`const ${nextName} =`, start)
  assert.ok(start >= 0 && end > start)
  return runInNewContext(`${source.slice(start, end)}; ${name}`, bindings)
}

test('single-device report names open the execution and multi-device names open their result drawer', () => {
  const opened = []
  const selectedBatch = { value: null }
  const batchDrawerVisible = { value: false }
  const view = functionFrom(reportSource, 'handleBatchView', 'handleExecutionCommand', {
    selectedBatch, batchDrawerVisible, handleView: id => opened.push(id),
  })
  const single = { batch_id: 'one', executions: [{ id: 91 }] }
  view(single)
  assert.deepEqual(opened, [91])
  assert.equal(batchDrawerVisible.value, false)
  const multi = { batch_id: 'many', executions: [{ id: 92 }, { id: 93 }] }
  view(multi)
  assert.equal(selectedBatch.value, multi)
  assert.equal(batchDrawerVisible.value, true)
  assert.deepEqual(opened, [91])
})

test('schedule saving ignores a second submit and allows retry after a request fails', async () => {
  const saving = { value: false }
  const dialogVisible = { value: true }
  let rejectRequest
  let calls = 0
  const submit = functionFrom(taskSource, 'handleSubmit', 'handleToggle', {
    saving, dialogVisible, form: { name: '每晚回归', task_type: 'api', api_scenario_id: 12, strategy: 'DAILY' },
    editingId: { value: null }, buildPayload: () => ({ name: '每晚回归' }),
    api: { createTask: () => { calls++; return new Promise((resolve, reject) => { rejectRequest = reject }) } },
    ElMessage: { success() {}, error() {}, warning() {} }, fetchTasks() {},
  })
  const first = submit()
  await submit()
  assert.equal(calls, 1)
  assert.equal(saving.value, true)
  rejectRequest(new Error('temporary outage'))
  await first
  assert.equal(saving.value, false)
  assert.equal(dialogVisible.value, true)
  const retry = submit()
  assert.equal(calls, 2)
  rejectRequest(new Error('temporary outage'))
  await retry
  assert.equal(saving.value, false)
})
