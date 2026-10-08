<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { apiError, pathLabel } from '@/utils/apiTesting'
const props=defineProps({runId:String})
const emit=defineEmits(['jump-step'])
const available=ref(false),open=ref(false),busy=ref(false),data=ref(null),error=ref('')
let alive=true,requestRevision=0
watch(()=>props.runId,()=>{requestRevision++;data.value=null;error.value='';busy.value=false;open.value=false},{flush:'sync'})
onMounted(async()=>{try{const result=await api.apiTesting.get('/ai/status');if(alive)available.value=result.data.available}catch{if(alive)available.value=false}})
onBeforeUnmount(()=>{alive=false;requestRevision++})
async function explain(){
  if(!alive||!props.runId)return
  open.value=true
  if(data.value||busy.value)return
  const revision=++requestRevision,runId=props.runId
  const current=()=>alive&&revision===requestRevision&&runId===props.runId
  busy.value=true;error.value=''
  try{const result=await api.apiTesting.post('/ai/explain-failure',{run_id:runId},{timeout:95000});if(current())data.value=result.data}
  catch(e){if(current())error.value=apiError(e)}finally{if(current())busy.value=false}
}
function jump(fact){emit('jump-step',fact.step_id);open.value=false}
</script>
<template><el-button v-if="available" :loading="busy" @click="explain">AI 解释失败</el-button><el-drawer class="ad-drawer" v-model="open" title="AI 失败解释" size="min(600px,95vw)"><p class="hint">基于本次报告提供排查建议，测试结果保持不变。</p><el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error" :loading="busy" @click="explain">重试</el-button><div v-loading="busy" class="explanation"><template v-if="data"><h3>已知事实</h3><article v-for="fact in data.facts" :key="fact.id" class="fact"><div><p><b>{{ fact.id }}</b> · {{ fact.message }}</p><code v-if="fact.path?.length">{{ pathLabel(fact.path) }}</code></div><el-button v-if="fact.step_id" link type="primary" @click="jump(fact)">定位步骤</el-button></article><h3>可能原因</h3><article v-for="(item,i) in data.possible_causes" :key="i"><p>{{ item.text }}</p><small>依据：{{ item.evidence_ids.join('、') }}</small></article><h3>下一步排查</h3><article v-for="(item,i) in data.next_steps" :key="i"><p>{{ item.text }}</p><small>依据：{{ item.evidence_ids.join('、') }}</small></article><p v-for="warning in data.warnings" :key="warning" class="hint">{{ warning }}</p></template></div></el-drawer></template>
<style scoped>.explanation{min-height:120px}h3{font-size: 13px;margin-top:24px}article{border-bottom:1px solid var(--ad-border);padding:8px 0}p{font-size:13px;line-height:1.7;overflow-wrap:anywhere}.hint,small{color:var(--ad-muted);font-size:12px}.fact{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.fact>div{min-width:0}.fact p{margin:0 0 4px}.fact code{font-size:12px;color:var(--ad-muted);overflow-wrap:anywhere}.fact .el-button{flex:none;margin-top:2px}@media(max-width:760px){p,.hint,small,.fact code,h3{font-size:14px}.fact{flex-wrap:wrap}}
</style>
