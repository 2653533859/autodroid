<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { activeStatus, apiError, statusLabel, statusType, downloadReport, failureSummary } from '@/utils/apiTesting'
import { useUserStore } from '@/stores/useUserStore'
import ResultPanel from '@/components/api-testing/ResultPanel.vue'
import AiFailureExplanation from '@/components/api-testing/AiFailureExplanation.vue'
const route = useRoute(), router = useRouter(), user = useUserStore(), run = ref(null), expanded = ref([]), loading = ref(true)
let timer, alive = true
const failure = computed(()=>failureSummary(run.value))
const sources = computed(()=>run.value?.snapshot?.steps || run.value?.steps || [])
const firstFailure = computed(()=>run.value?.steps?.find(s=>['FAIL','ERROR'].includes(s.status)))
let followedFailure = null
async function jump(stepId){if(!expanded.value.includes(stepId))expanded.value.push(stepId);await nextTick();document.getElementById('report-step-'+stepId)?.scrollIntoView({block:'nearest',behavior:'smooth'})}
function editStep(stepId){router.push({path:`/api-testing/scenarios/${run.value.scenario_id}/edit`,query:{step_id:stepId}})}
const notificationLabels = { DISABLED: '未启用', PENDING: '待发送', SENT: '已发送', FAILED: '发送失败', SKIPPED: '未发送' }
async function load() {
  try {
    const { data } = await api.apiTesting.get(`/runs/${route.params.id}`)
    if (!alive) return
    if (!run.value) expanded.value = data.steps.filter(s => ['ERROR','FAIL'].includes(s.status)).map(s => s.step_id)
    run.value = data
    const failed=data.steps.find(s=>['FAIL','ERROR'].includes(s.status))
    if(failed && followedFailure!==failed.step_id){followedFailure=failed.step_id;if(!expanded.value.includes(failed.step_id))expanded.value.push(failed.step_id)}
    if (activeStatus(data.status) || data.notification_status === 'PENDING') timer = setTimeout(load, 1000)
  } catch (err) { ElMessage.error(apiError(err)) } finally { loading.value = false }
}
async function stop() {
  try { await ElMessageBox.confirm('停止发送后续请求。已经发送的业务请求可能已生效，不能回滚。', '中止接口运行', { type: 'warning' }); await api.apiTesting.post(`/runs/${run.value.id}/cancel`); ElMessage.success('已请求中止') }
  catch (err) { if (!['cancel','close'].includes(err)) ElMessage.error(apiError(err)) }
}
async function download() { try { await downloadReport(api.apiTesting, run.value.id) } catch (err) { ElMessage.error(apiError(err)) } }
onMounted(load)
onBeforeUnmount(() => { alive = false; clearTimeout(timer) })
</script>
<template>
  <div v-loading="loading" class="api-report"><header><el-button @click="router.push('/execution/reports?tab=api')">报告中心</el-button><h2>接口测试报告</h2><span class="spacer" /><el-button v-if="run && activeStatus(run.status) && (user.isAdmin || user.userInfo?.id === run.executor_id)" type="danger" @click="stop">中止运行</el-button><el-button v-if="run" @click="download">下载 HTML 报告</el-button></header>
    <main v-if="run"><section class="summary"><div class="title"><h1>{{ run.scenario_name }}</h1><el-tag size="large" :type="statusType(run.status)">{{ statusLabel(run.status) }}</el-tag></div><p>{{ run.env_name }} · {{ run.executor_name }} · {{ run.task_id ? '定时执行' : '手动执行' }} · 配置 v{{ run.snapshot.version }}</p><div class="stats"><div><b>{{ run.summary.total }}</b><span>总步骤</span></div><div><b class="pass">{{ run.summary.passed }}</b><span>通过</span></div><div><b class="fail">{{ run.summary.failed }}</b><span>失败</span></div><div><b>{{ run.summary.skipped }}</b><span>跳过</span></div><div><b>{{ (run.duration_ms / 1000).toFixed(2) }}<small> s</small></b><span>总耗时</span></div></div><p>开始：{{ (run.started_at || run.created_at)?.replace('T',' ').slice(0,19) }} · 飞书通知：{{ notificationLabels[run.notification_status] }}<span v-if="run.notification_error">（{{ run.notification_error }}）</span></p><el-alert v-for="warning in run.warnings||[]" :key="warning" :title="warning" type="warning" :closable="false" /><el-alert v-if="failure" :title="failure" type="error" :closable="false" /><div v-if="firstFailure||failure" class="failure-actions"><AiFailureExplanation :run-id="run.id" @jump-step="jump" /><el-button v-if="firstFailure" type="primary" plain @click="jump(firstFailure.step_id)">查看失败步骤</el-button><el-button v-if="run.scenario_id&&firstFailure" @click="editStep(firstFailure.step_id)">返回场景并定位此步骤</el-button></div></section>
      <section><div class="section-heading"><h3>步骤详情</h3><span>测试结果与通知状态独立。</span></div><el-collapse v-model="expanded"><el-collapse-item v-for="(step, index) in run.steps" :key="step.step_id" :name="step.step_id" :id="'report-step-'+step.step_id"><template #title><div class="step-title"><span class="number">{{ index + 1 }}</span><b>{{ step.name }}</b><el-tag :type="statusType(step.status)" size="small">{{ statusLabel(step.status) }}</el-tag><span>{{ Math.round(step.duration_ms) }} ms</span></div></template><el-button v-if="run.scenario_id" link type="primary" @click="editStep(step.step_id)">在场景中编辑此步骤</el-button><ResultPanel :result="step" :sources="sources" @jump-source="jump" /></el-collapse-item></el-collapse></section>
      <section><details><summary>本次运行的配置快照</summary><pre>{{ JSON.stringify(run.snapshot, null, 2) }}</pre></details></section>
    </main>
  </div>
</template>
<style scoped>.failure-actions{margin-top:12px;display:flex;gap:10px;flex-wrap:wrap}.failure-actions .el-button+.el-button{margin:0}.api-report{height:100%;display:flex;flex-direction:column;background:#f3f5f9}header{display:flex;align-items:center;gap:14px;padding:18px 24px;background:white;border-bottom:1px solid #e5e9f1}h2{font-size:18px;margin:0}.spacer{flex:1}main{padding:24px;overflow:auto}section{background:white;border:1px solid #e5e9f1;border-radius:10px;padding:24px;margin:0 auto 20px;max-width:1250px}.title{display:flex;align-items:center;gap:16px}h1{font-size:25px;margin:0}p{font-size:13px;color:#7e8b9c}.stats{display:grid;grid-template-columns:repeat(5,1fr);padding:16px 0;gap:20px}.stats div{display:flex;flex-direction:column;gap:8px}.stats b{font-size:29px;color:#334966}.stats span,.stats small{font-size:12px;color:#8a96a8}.stats .pass{color:#14935c}.stats .fail{color:#d45353}.section-heading{display:flex;justify-content:space-between;align-items:center}.section-heading span{font-size:12px;color:#8a96a8}.step-title{display:flex;gap:12px;align-items:center;width:100%;padding-right:16px}.step-title b{flex:1}.step-title span:last-child{color:#8a96a8;font-size:12px}.number{background:#edf3fb;padding:2px 10px;border-radius:5px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:500px;overflow:auto}summary{cursor:pointer}</style>
