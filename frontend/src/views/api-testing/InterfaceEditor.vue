<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Upload, Download, VideoPlay, CircleClose } from '@element-plus/icons-vue'
import api from '@/api'
import { blankConfig, apiError, copy, sampleTypes, responseFields } from '@/utils/apiTesting'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { useApiDebug } from '@/composables/useApiDebug'
import RequestEditor from '@/components/api-testing/RequestEditor.vue'
import ResultPanel from '@/components/api-testing/ResultPanel.vue'
import AssetMetadata from '@/components/api-testing/AssetMetadata.vue'
import EnvironmentDrawer from '@/components/api-testing/EnvironmentDrawer.vue'
import CurlImportDialog from '@/components/api-testing/CurlImportDialog.vue'
import AddToScenarioDialog from '@/components/api-testing/AddToScenarioDialog.vue'
import AiAssertions from '@/components/api-testing/AiAssertions.vue'
const route = useRoute(), router = useRouter()
const form = ref({ name: '', description: '', folder_id: Number(route.query.folder_id) || null, config: blankConfig(), sample: null }), saved = ref(''), loading = ref(false), metadata = ref({}), requestInvalid = ref(false)
const envId = ref(null), environments = ref([]), variables = ref([]), folders = ref([]), sampleFields = ref([])
const curlDialog = ref(false), joinOpen=ref(false), infoOpen=ref(false), nameInput=ref(null), sampleDialog = ref(false), sampleText = ref('')
const id = ref(route.params.id), steps = computed(() => [{ id: 'interface-debug', name: form.value.name || '接口调试', kind: 'request', snapshot: form.value.config, overrides: {}, seconds: 1 }])
const sendStarting=ref(false)
let alive=true
onBeforeUnmount(()=>{alive=false})
const requestEditor=ref(null), resultPanel=ref(null), envOpen=ref(false)
const envName=computed(()=>environments.value.find(e=>e.id===envId.value)?.name||'未选择环境')
const debug = useApiDebug(envId, steps, { retainDisplay: true, envName:()=>envName.value })
const result = computed(() => debug.displayResults.value['interface-debug'])
const fields = computed(() => result.value?.detail?.fields?.length ? result.value.detail.fields : sampleFields.value)
const fieldSource=computed(()=>({origin:result.value?(debug.staleIds.value.has('interface-debug')?'上次调试':'本次调试'):'接口样例',env_name:result.value?.env_name||'',captured_at:result.value?.captured_at||''}))
function addAssertion(field){requestEditor.value?.addAssertion(field)}
function applyAssertions(assertions){form.value.config.assertions=assertions;requestEditor.value?.focus('assertions')}
provide('apiEditEnvironment',()=>{envOpen.value=true})
async function refreshEnvironment(value){await debug.close();environments.value=(await api.getEnvironments()).data;envId.value=value;await loadVariables(value)}
async function joinScenario(){if((dirty.value||!id.value)&&!await save('join'))return;joinOpen.value=true}
async function send(){
  if(!alive||sendStarting.value||loading.value||debug.running.value||debug.rechecking.value)return
  const signature=JSON.stringify([steps.value,envId.value])
  sendStarting.value=true
  try{const {data}=await api.apiTesting.post('/precheck',{name:form.value.name||'接口调试',steps:copy(steps.value),env_id:envId.value,validation_mode:'debug'});if(!alive||signature!==JSON.stringify([steps.value,envId.value]))return;if(data.errors.length){const first=data.errors[0];requestEditor.value?.focus(first.section,first.location);return ElMessage.warning(first.message)}await debug.run('interface-debug')}catch(e){if(alive)ElMessage.error(apiError(e))}finally{sendStarting.value=false}
}
async function recheck(){await debug.recheck('interface-debug');resultPanel.value?.showAssertions()}
const dirty = computed(() => requestInvalid.value || (!!saved.value && JSON.stringify(form.value) !== saved.value))
useUnsavedGuard(dirty)
let variableRequest=0
async function loadVariables(value){const seq=++variableRequest;try{const data=value?(await api.getVariables(value)).data:[];if(seq===variableRequest)variables.value=data}catch(e){if(seq===variableRequest)ElMessage.error(apiError(e))}}
watch(envId,loadVariables)
async function load() {
  try {
    const [envs, dirs] = await Promise.all([api.getEnvironments(), api.apiTesting.get('/folders')])
    environments.value = envs.data; folders.value = dirs.data.filter(f => f.kind === 'interface')
    if (id.value) {
      const { data } = await api.apiTesting.get(`/interfaces/${id.value}`)
      metadata.value = data
      form.value = { name: data.name, description: data.description, folder_id: data.folder_id, version: data.version, config: data.config, sample: data.sample }
      sampleFields.value = data.sample_fields
    }
    saved.value = JSON.stringify(form.value)
    if(route.query.open==='join')joinOpen.value=true
  } catch (err) { ElMessage.error(apiError(err)) }
}
async function save(openAfter=null) {
  if (!alive||!saved.value||loading.value||sendStarting.value||debug.running.value) return false
  if(!form.value.name.trim()){nameInput.value?.focus();ElMessage.warning('请输入接口名称');return false}
  if (requestInvalid.value) {ElMessage.warning('请先修正请求体 JSON');return false}
  loading.value = true
  try {
    const submitted=copy(form.value)
    const payload = { ...submitted, sample_types: sampleTypes(fields.value) }
    const response = id.value ? await api.apiTesting.put(`/interfaces/${id.value}`, payload) : await api.apiTesting.post('/interfaces', payload)
    if(!alive)return false
    form.value.version = response.data.version; form.value.sample = response.data.sample; sampleFields.value = response.data.sample_fields
    metadata.value = response.data
    saved.value = JSON.stringify({...submitted,version:response.data.version,sample:response.data.sample}); ElMessage.success('接口已保存')
    if (!id.value) { id.value = response.data.id; await router.replace({path:`/api-testing/interfaces/${id.value}/edit`,query:openAfter==='join'?{open:'join'}:{}}) }
    return true
  } catch (err) { ElMessage.error(apiError(err));return false } finally { loading.value = false }
}
async function applyCurl(config) {
  if(form.value.config.request.url.value){try{await ElMessageBox.confirm('替换当前请求配置？名称和目录保持不变。','导入请求')}catch{return}}
  form.value.config=copy(config)
}
function sampleJson() {
  try {
    form.value.sample = { body: JSON.parse(sampleText.value) }
    sampleFields.value = responseFields(form.value.sample)
    sampleDialog.value = false; ElMessage.success('样例已加入草稿，可在断言中选择字段')
  } catch { ElMessage.error('请输入有效 JSON') }
}
onMounted(load)
</script>
<template>
  <div class="interface-editor ad-page" :inert="loading||sendStarting">
    <header class="ad-page-header"><el-button link :icon="ArrowLeft" @click="router.push('/api-testing/interfaces')">返回</el-button><el-input ref="nameInput" v-model="form.name" class="interface-name" placeholder="输入接口名称" aria-label="接口名称" maxlength="200" /><span class="save-state" role="status">{{ loading ? '保存中…' : sendStarting ? '检查请求中…' : dirty ? '未保存' : id ? '已保存' : '新接口' }}</span><el-select v-model="envId" clearable placeholder="调试环境" aria-label="调试环境" class="environment"><el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" /></el-select><el-button link @click="envOpen=true">环境变量</el-button><span class="spacer" /><el-button @click="joinScenario">加入场景</el-button><el-button :icon="Download" @click="curlDialog=true">导入 cURL</el-button><el-button type="primary" :icon="Upload" :loading="loading" @click="save()">保存</el-button><el-button @click="infoOpen=true">接口信息</el-button></header>
    <div class="editor-main">
      <section class="request-section">
        <RequestEditor ref="requestEditor" v-model="form.config" :field-source="fieldSource" :variables="variables" :fields="fields" :allow-step-references="false" @invalid-change="requestInvalid=$event">
          <template #actions><el-button v-if="!debug.running.value" :loading="sendStarting" type="primary" :icon="VideoPlay" :disabled="requestInvalid" @click="send">发送请求</el-button><el-button v-else type="danger" :icon="CircleClose" @click="debug.close">中止</el-button></template>
        </RequestEditor>
      </section>
      <section class="debug-section">
        <div class="response-heading"><b>响应与校验</b><el-button v-if="debug.results.value['interface-debug']?.detail?.response" :type="debug.pendingIds.value.has('interface-debug')||result?.status==='UNCHECKED'?'primary':'default'" :disabled="debug.running.value" :loading="debug.rechecking.value" @click="recheck">重新校验响应</el-button><span v-if="result" class="hint">不重发请求</span></div>
        <el-alert v-if="debug.staleIds.value.has('interface-debug')" class="result-notice" title="上次调试结果仅供参考，配置已改变，请重新发送请求。" type="info" :closable="false" show-icon />
        <el-alert v-if="debug.error.value" :title="debug.error.value" type="error" :closable="false" />
        <ResultPanel ref="resultPanel" :result="result" :pending="debug.pendingIds.value.has('interface-debug')" :show-references="false" editable @add-assertion="addAssertion">
          <template #tools><AiAssertions :steps="steps" step-id="interface-debug" :env-id="envId" :debug-session-id="debug.id.value" :editor-id="debug.editorId" :result="debug.results.value['interface-debug']" :disabled="loading||debug.running.value||requestInvalid" @update-assertions="applyAssertions" /></template>
        </ResultPanel>
        <div class="sample-tools"><el-button link @click="sampleDialog=true">粘贴响应样例</el-button><el-button v-if="result?.detail?.response" link @click="form.sample=copy(result.detail.response);ElMessage.success('已加入草稿，保存后生效')">保存本次响应为样例</el-button><span v-if="form.sample" class="hint">已配置样例 · 不参与执行</span></div>
      </section>
    </div>
    <CurlImportDialog v-model="curlDialog" @import="applyCurl" />
    <AddToScenarioDialog v-model="joinOpen" :interface-id="id" />
    <EnvironmentDrawer v-model="envOpen" :env-id="envId" :environments="environments" :variables="variables" :env-name="envName" @refresh="refreshEnvironment" />
    <el-drawer class="ad-drawer" v-model="infoOpen" title="接口信息" size="min(520px,95vw)"><el-form label-position="top"><el-form-item label="所属目录"><el-select v-model="form.folder_id" clearable placeholder="未分组"><el-option v-for="f in folders" :key="f.id" :label="f.name" :value="f.id" /></el-select></el-form-item><el-form-item label="接口说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></el-form><p class="hint">配置版本：{{ form.version||'尚未保存' }}</p><AssetMetadata :asset="metadata" /></el-drawer>
    <el-dialog class="ad-dialog" v-model="sampleDialog" title="响应体 JSON 样例" width="min(620px,95vw)"><el-alert title="样例只帮助选择字段，不会替代运行时的真实结果。" type="info" :closable="false" /><el-input v-model="sampleText" type="textarea" :rows="12" style="margin-top:12px" /><template #footer><el-button type="primary" @click="sampleJson">使用样例</el-button></template></el-dialog>
  </div>
</template>
<style scoped>
.interface-editor{padding:0}

.interface-editor{height:100%;display:flex;flex-direction:column;background:var(--ad-bg);min-width:0}header{padding:12px 16px;background:var(--ad-surface);display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--ad-border)}header .el-button+.el-button{margin:0}.interface-name{width:195px}.interface-name :deep(input){font-weight:600}.environment{width:150px}.spacer{flex:1}.editor-main{flex:1;min-height:0;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:12px}section{background:var(--ad-surface);border:1px solid var(--ad-border);border-radius:6px;padding:12px 16px;min-width:0}.request-section{flex-shrink:0}.response-heading{display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap;font-size: 13px}.hint{font-size:12px;color:var(--ad-muted);line-height:20px}.result-notice{margin-bottom:12px}.sample-tools{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:12px;padding-top:10px;border-top:1px solid var(--ad-border)}.sample-tools .el-button+.el-button{margin:0}.el-drawer .el-select{width:100%}@media(max-width:760px){header{padding:10px}.editor-main{padding:10px}section{padding:12px}}
.save-state{font-size:12px;color:var(--ad-muted);white-space:nowrap}.interface-name{width:200px}.editor-main{gap:12px}.response-heading{margin-bottom:8px}.response-heading b{font-weight:600}.interface-editor>header{margin:0;min-height:56px;padding:12px 16px}.interface-editor>header .environment{margin-left:4px}
@media(min-width:1680px){.editor-main{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);align-items:start}.debug-section{max-height:100%;overflow:auto}}
@media(max-width:760px){.interface-editor>header{gap:8px}.interface-name{flex:1;min-width:150px}.environment{width:auto;min-width:150px;flex:1}.editor-main{padding:12px}.save-state,.hint{font-size:14px}.interface-editor>header .spacer{display:none}.sample-tools{gap:8px}section{padding:12px}}
</style>
