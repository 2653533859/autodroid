<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { apiError, activeStatus, statusLabel, statusType, downloadReport } from '@/utils/apiTesting'
import { useUserStore } from '@/stores/useUserStore'
const router = useRouter(), user = useUserStore(), rows = ref([]), total = ref(0), page = ref(1), keyword = ref(''), status = ref(''), loading = ref(false)
let timer, alive = true
async function load(quiet = false) {
  if (!quiet) loading.value = true
  clearTimeout(timer)
  try {
    const { data } = await api.apiTesting.get('/runs', { keyword: keyword.value, status: status.value || undefined, skip: (page.value - 1) * 20, limit: 20 })
    if (!alive) return
    rows.value = data.items; total.value = data.total
    if (rows.value.some(r => activeStatus(r.status) || r.notification_status === 'PENDING')) timer = setTimeout(() => load(true), 2000)
  } catch (err) { ElMessage.error(apiError(err)) } finally { loading.value = false }
}
function search() { page.value = 1; load() }
async function download(id) { try { await downloadReport(api.apiTesting, id) } catch (err) { ElMessage.error(apiError(err)) } }
async function remove(row) {
  try { await ElMessageBox.confirm(`删除「${row.scenario_name}」的这次报告？`, '删除报告', { type: 'warning' }); await api.apiTesting.delete(`/runs/${row.id}`); load() }
  catch (err) { if (!['cancel','close'].includes(err)) ElMessage.error(apiError(err)) }
}
onMounted(load)
onActivated(() => { alive = true; load() })
onDeactivated(() => { alive = false; clearTimeout(timer) })
onBeforeUnmount(() => { alive = false; clearTimeout(timer) })
</script>
<template>
  <div class="api-run-list"><div class="filters"><el-input v-model="keyword" placeholder="搜索接口场景" clearable style="width:260px" @keyup.enter="search" @clear="search" /><el-select v-model="status" placeholder="全部状态" clearable style="width:150px" @change="search"><el-option v-for="s in ['PASS','FAIL','ERROR','ABORTED','RUNNING','QUEUED']" :key="s" :value="s" :label="statusLabel(s)" /></el-select><el-button @click="search">刷新</el-button><el-button link type="primary" @click="router.push('/api-testing/scenarios')">自动化场景</el-button></div>
    <el-table v-loading="loading" :data="rows"><el-table-column label="场景" min-width="200"><template #default="{row}"><el-button link type="primary" @click="router.push(`/execution/reports/api/${row.id}`)">{{ row.scenario_name }}</el-button><el-tag v-if="row.task_id" size="small" type="info">定时</el-tag></template></el-table-column><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column><el-table-column prop="env_name" label="环境" min-width="110" /><el-table-column prop="executor_name" label="执行人" width="100" /><el-table-column label="耗时" width="100"><template #default="{row}">{{ (row.duration_ms / 1000).toFixed(2) }} s</template></el-table-column><el-table-column label="开始时间" width="170"><template #default="{row}">{{ row.created_at?.replace('T',' ').slice(0,19) }}</template></el-table-column><el-table-column label="操作" width="180"><template #default="{row}"><el-button link type="primary" @click="router.push(`/execution/reports/api/${row.id}`)">详情</el-button><el-button link @click="download(row.id)">下载</el-button><el-button v-if="!activeStatus(row.status) && (user.isAdmin || user.userInfo?.id === row.executor_id)" link type="danger" @click="remove(row)">删除</el-button></template></el-table-column><template #empty><el-empty description="运行接口场景后，报告会出现在这里" /></template></el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load()" />
  </div>
</template>
<style scoped>.api-run-list{padding:12px 0}.filters{display:flex;gap:12px;margin-bottom:18px;align-items:center}.el-pagination{margin-top:18px;justify-content:flex-end}</style>
