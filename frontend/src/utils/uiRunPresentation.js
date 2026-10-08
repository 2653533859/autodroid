// A batch may contain both running and queued devices. Do not label queued work
// as already started; preserve its earliest known queue position.
export function describeRunSubmission(data, deviceCount) {
  const runs = Array.isArray(data?.runs) ? data.runs : []
  const queued = runs.filter(run => run.queued || String(run.status || '').toUpperCase() === 'QUEUED')
  const started = runs.length ? runs.length - queued.length : deviceCount
  const positions = queued.map(run => run.queue_position).filter(Number.isFinite)
  const queueSuffix = positions.length ? `（最前第 ${Math.min(...positions)} 位）` : ''
  if (!queued.length) return `已在 ${started} 台设备开始执行`
  if (!started) return `已加入执行队列：${queued.length} 台${queueSuffix}`
  return `已开始 ${started} 台；${queued.length} 台排队中${queueSuffix}`
}
