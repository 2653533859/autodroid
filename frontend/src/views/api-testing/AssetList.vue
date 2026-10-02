<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import AddToScenarioDialog from '@/components/api-testing/AddToScenarioDialog.vue'
import dayjs from 'dayjs'
import { Plus, Search, Refresh, Edit, CopyDocument, Delete, Document, FolderOpened, VideoPlay } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/useUserStore'
import { apiError, authLabel, previewValue, statusLabel, statusType } from '@/utils/apiTesting'
const route = useRoute(), router = useRouter(), user = useUserStore()
const isInterface = computed(() => route.path.includes('/interfaces'))
const kind = computed(() => isInterface.value ? 'interface' : 'scenario')
const endpoint = computed(() => isInterface.value ? '/interfaces' : '/scenarios')
const title = computed(() => isInterface.value ? '接口管理' : '自动化场景')
const rows = ref([]), folders = ref([]), keyword = ref(''), folderId = ref(null), loading = ref(false), page = ref(1), total = ref(0)
const pageSize = ref(20),joinOpen=ref(false),joinId=ref(null)
const environmentName=id=>environments.value.find(env=>env.id===id)?.name||'未选择环境'
function join(row){joinId.value=row.id;joinOpen.value=true}
const runItem=ref(null),runDialog=ref(false),runEnv=ref(null),environments=ref([]),runNotify=ref(false),notificationConfigured=ref(false),running=ref(false)
async function openRun(row){try{runItem.value=row;runEnv.value=row.env_id;runNotify.value=false;const [envs,notice]=await Promise.all([api.getEnvironments(),api.apiTesting.get('/notification-status')]);environments.value=envs.data;notificationConfigured.value=notice.data.configured;runDialog.value=true}catch(e){ElMessage.error(apiError(e))}}
async function run(){running.value=true;try{const {data}=await api.apiTesting.post(`/scenarios/${runItem.value.id}/runs`,{version:runItem.value.version,env_id:runEnv.value,notify:runNotify.value});runDialog.value=false;router.push(`/execution/reports/api/${data.id}`)}catch(e){ElMessage.error(apiError(e))}finally{running.value=false}}
const canDelete = row => user.isAdmin || user.userInfo?.id === row.user_id
const time = value => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'
function create() { router.push({ path: `/api-testing${endpoint.value}/create`, query: { folder_id: folderId.value || undefined } }) }
const folderTree = computed(() => {
  const build = parent => folders.value.filter(f => f.kind === kind.value && f.parent_id === parent).map(f => ({ ...f, children: build(f.id) }))
  return [{ id: null, name: '全部', children: [{ id: 0, name: '未分组' }, ...build(null)] }]
})
async function load() {
  loading.value = true
  try {
    const [items, dirs] = await Promise.all([api.apiTesting.get(endpoint.value, { keyword: keyword.value, folder_id: folderId.value, skip: (page.value - 1) * pageSize.value, limit: pageSize.value }), api.apiTesting.get('/folders')])
    rows.value = items.data.items; total.value = items.data.total; folders.value = dirs.data
  } catch (err) { ElMessage.error(apiError(err)) } finally { loading.value = false }
}
function search() { page.value = 1; load() }
async function createFolder() {
  try {
    const { value } = await ElMessageBox.prompt('目录名称（创建在当前选中目录下）', '新增目录', { inputPattern: /\S/, inputErrorMessage: '请输入名称' })
    await api.apiTesting.post('/folders', { name: value, kind: kind.value, parent_id: folderId.value || null }); load()
  } catch (err) { if (!['cancel','close'].includes(err)) ElMessage.error(apiError(err)) }
}
async function folderAction(action, folder) {
  try {
    if (action === 'rename') {
      const { value } = await ElMessageBox.prompt('目录名称', '重命名目录', { inputValue: folder.name, inputPattern: /\S/ })
      await api.apiTesting.put(`/folders/${folder.id}`, { name: value, kind: folder.kind, parent_id: folder.parent_id })
    } else {
      await ElMessageBox.confirm(`删除目录「${folder.name}」？非空目录不会被删除。`, '删除目录', { type: 'warning' })
      await api.apiTesting.delete(`/folders/${folder.id}`); folderId.value = null
    }
    load()
  } catch (err) { if (!['cancel','close'].includes(err)) ElMessage.error(apiError(err)) }
}
function edit(row) { router.push(`/api-testing${endpoint.value}/${row.id}/edit`) }
async function duplicate(row) {
  try {
    const { data } = await api.apiTesting.get(`${endpoint.value}/${row.id}`)
    const payload = { name: `${data.name} 副本`, description: data.description, folder_id: data.folder_id }
    if (isInterface.value) Object.assign(payload, { config: data.config, sample: data.sample })
    else Object.assign(payload, { steps: data.steps, env_id: data.env_id })
    const created = await api.apiTesting.post(endpoint.value, payload); edit(created.data)
  } catch (err) { ElMessage.error(apiError(err)) }
}
async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除「${row.name}」？被引用的记录无法删除。`, '删除', { type: 'warning' })
    await api.apiTesting.delete(`${endpoint.value}/${row.id}`); load()
  } catch (err) { if (!['cancel','close'].includes(err)) ElMessage.error(apiError(err)) }
}
watch(endpoint, () => { folderId.value = null; keyword.value = ''; search() })
onMounted(async()=>{await load();try{environments.value=(await api.getEnvironments()).data}catch{/* list remains usable */}})
</script>
<template>
  <div class="api-assets">
    <div class="main-layout">
      <aside class="folder-aside">
        <div class="folder-heading"><b>{{ isInterface ? '接口目录' : '场景目录' }}</b><el-tooltip content="新建目录"><el-button link type="primary" :icon="Plus" @click="createFolder" /></el-tooltip></div>
        <el-tree :data="folderTree" node-key="id" :props="{label:'name'}" default-expand-all highlight-current @node-click="folderId = $event.id; search()">
          <template #default="{data}"><div class="folder-node"><el-icon><FolderOpened /></el-icon><span>{{ data.name }}</span><el-dropdown v-if="data.id" trigger="click" @command="folderAction($event, data)"><el-button link size="small" @click.stop>···</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="rename">重命名</el-dropdown-item><el-dropdown-item command="delete" :disabled="!canDelete(data)">删除</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></template>
        </el-tree>
      </aside>
      <main class="content-wrapper">
        <div class="toolbar">
          <div class="left-tools"><el-input v-model="keyword" clearable :placeholder="isInterface ? '搜索接口名称...' : '搜索场景名称...'" :prefix-icon="Search" class="search-input" @keyup.enter="search" @clear="search" /><el-tooltip content="刷新"><el-button :icon="Refresh" circle @click="load" /></el-tooltip></div>
          <div class="right-tools"><el-button :icon="Document" @click="router.push('/execution/reports?tab=api')">测试报告</el-button><el-button type="primary" :icon="Plus" @click="create">{{ isInterface ? '新建接口' : '新建场景' }}</el-button></div>
        </div>
        <div class="table-container">
          <el-table v-loading="loading" :data="rows" height="100%" :header-cell-style="{ background: '#f5f7fa', color: '#606266' }" @row-dblclick="edit">
            <el-table-column :label="isInterface ? '接口名称' : '场景名称'" min-width="190"><template #default="{row}"><el-button link type="primary" @click="edit(row)">{{ row.name }}</el-button><div class="description" :title="isInterface?String(previewValue(row.config.request.url)):row.description">{{ isInterface?previewValue(row.config.request.url):row.description||'暂无说明' }}</div></template></el-table-column>
            <el-table-column v-if="isInterface" label="方法 / 鉴权" width="145" align="center"><template #default="{row}"><el-tag size="small" :type="row.config.request.method === 'GET' ? 'success' : 'primary'">{{ row.config.request.method }}</el-tag><div class="description">{{ authLabel(row.config.request.auth.kind) }}</div></template></el-table-column>
            <el-table-column v-if="!isInterface" label="执行情况" min-width="195"><template #default="{row}"><div>{{ row.step_count }} 个步骤 <el-tag v-if="row.last_run" :type="statusType(row.last_run.status)" size="small">{{ statusLabel(row.last_run.status) }}</el-tag></div><el-button v-if="row.last_run" link size="small" @click="router.push(`/execution/reports/api/${row.last_run.id}`)">{{ time(row.last_run.created_at) }}</el-button><span v-else class="description">尚未运行</span></template></el-table-column>
            <el-table-column v-if="!isInterface" label="默认环境" min-width="120"><template #default="{row}">{{ environmentName(row.env_id) }}</template></el-table-column>
            <el-table-column label="更新" width="145" align="center"><template #default="{row}"><div class="user-info"><span>{{ row.updater_name || '-' }}</span><span class="time">{{ time(row.updated_at) }}</span></div></template></el-table-column>

            <el-table-column label="操作" :width="isInterface?230:185" align="center" fixed="right"><template #default="{row}"><div class="action-buttons"><el-button v-if="isInterface" link type="primary" @click="edit(row)">调试</el-button><el-button v-if="isInterface" link type="primary" @click="join(row)">加入场景</el-button><el-tooltip v-if="!isInterface" content="运行场景"><el-button link type="success" :icon="VideoPlay" @click="openRun(row)" /></el-tooltip><el-tooltip content="编辑"><el-button link type="primary" :icon="Edit" @click="edit(row)" /></el-tooltip><el-tooltip content="克隆"><el-button link type="primary" :icon="CopyDocument" @click="duplicate(row)" /></el-tooltip><el-tooltip :content="canDelete(row) ? '删除' : '仅创建人或管理员可以删除'"><span class="button-tooltip-wrap"><el-button link type="danger" :icon="Delete" :disabled="!canDelete(row)" @click="remove(row)" /></span></el-tooltip></div></template></el-table-column>
            <template #empty><el-empty :description="isInterface ? '暂无接口，点击新建接口开始配置' : '暂无场景，点击新建场景开始编排'" /></template>
          </el-table>
        </div>
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[20,50,100]" :total="total" layout="total, sizes, prev, pager, next, jumper" @current-change="load" @size-change="search" />
      </main>
    </div>
    <AddToScenarioDialog v-model="joinOpen" :interface-id="joinId" />
    <el-dialog v-model="runDialog" :title="`运行 · ${runItem?.name||'场景'}`" width="440px"><el-form label-position="top"><el-form-item label="本次运行环境"><el-select v-model="runEnv" clearable><el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" /></el-select></el-form-item><el-checkbox v-model="runNotify" :disabled="!notificationConfigured">发送飞书摘要和报告链接</el-checkbox></el-form><p class="description">运行会发送真实请求，写入操作会产生业务数据。</p><template #footer><el-button @click="runDialog=false">取消</el-button><el-button type="primary" :loading="running" @click="run">开始运行</el-button></template></el-dialog>
  </div>
</template>
<style scoped>
.api-assets{height:100%;display:flex;flex-direction:column;background:#f2f3f5}
.main-layout{display:flex;flex:1;min-height:0;margin:10px;gap:10px;overflow:hidden}
.folder-aside{width:200px;flex-shrink:0;background:#fff;border-radius:4px;padding:16px 10px;overflow:auto}
.folder-heading,.folder-node{display:flex;align-items:center;gap:8px;width:100%}
.folder-heading{justify-content:space-between;margin-bottom:18px;padding:0 6px;font-size:14px}
.folder-node span{flex:1;overflow:hidden;text-overflow:ellipsis;font-size:13px}
.folder-node .el-icon{color:#909399}
.content-wrapper{flex:1;min-width:0;background:#fff;border-radius:4px;display:flex;flex-direction:column;padding:20px;overflow:hidden}
.toolbar,.left-tools,.right-tools{display:flex;align-items:center;gap:12px}
.toolbar{justify-content:space-between;margin-bottom:20px;flex-wrap:wrap}
.search-input{width:240px}.table-container{flex:1;min-height:0}
.user-info{display:flex;flex-direction:column;gap:5px}.time,.description{font-size:12px;color:#909399}.description{margin-top:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.action-buttons{display:flex;align-items:center;justify-content:center;gap:12px}.action-buttons .el-button{margin-left:0}.button-tooltip-wrap{display:inline-flex}
.el-pagination{margin-top:20px;justify-content:flex-end}
@media(max-width:900px){.folder-aside{width:160px}.content-wrapper{padding:12px}.search-input{width:200px}.el-pagination{justify-content:flex-start;overflow:auto}}
</style>
