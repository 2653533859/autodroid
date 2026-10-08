/** Hidden editors/details retain their visible menu selection. */
export function activeMenuPath(path) {
  if (/^\/ui\/cases(?:\/|$)/.test(path)) return '/ui/cases'
  if (/^\/ui\/scenarios(?:\/|$)/.test(path)) return '/ui/scenarios'
  if (/^\/api-testing\/interfaces(?:\/|$)/.test(path)) return '/api-testing/interfaces'
  if (/^\/api-testing\/scenarios(?:\/|$)/.test(path)) return '/api-testing/scenarios'
  if (/^\/execution\/reports(?:\/|$)/.test(path) || /^\/special\/fastbot\/report\//.test(path)) return '/execution/reports'
  return path
}
export function menuAncestors(path) {
  const parts = activeMenuPath(path).split('/').filter(Boolean)
  return parts.slice(0, -1).map((_, index) => '/' + parts.slice(0, index + 1).join('/'))
}
