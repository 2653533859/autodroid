<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { apiError, copy, requestPreview } from '@/utils/apiTesting'
const props = defineProps({ modelValue:Boolean })
const emit = defineEmits(['update:modelValue','import'])
const command=ref(''), parsed=ref(null), busy=ref(false)
watch(command,()=>{parsed.value=null})
watch(()=>props.modelValue,open=>{if(open){command.value='';parsed.value=null}})
async function parse(){
  const original=command.value
  busy.value=true
  try { const {data}=await api.apiTesting.post('/imports/curl',{command:original}); if(command.value===original)parsed.value=data }
  catch(e){ElMessage.error(apiError(e))}finally{busy.value=false}
}
function apply(){emit('import',copy(parsed.value.config));emit('update:modelValue',false)}
</script>
<template>
  <el-dialog :model-value="modelValue" title="粘贴 cURL" width="min(720px,95vw)" @update:model-value="emit('update:modelValue',$event)">
    <el-input v-model="command" type="textarea" :rows="7" placeholder="粘贴浏览器 Copy as cURL 的内容" aria-label="cURL 请求" />
    <el-button class="parse" :loading="busy" :disabled="!command.trim()" @click="parse">解析预览</el-button>
    <template v-if="parsed"><p class="hint">仅导入配置，不发送请求。</p><pre>{{ JSON.stringify(requestPreview(parsed.config.request),null,2) }}</pre></template>
    <template #footer><el-button @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" :disabled="!parsed||busy" @click="apply">使用此请求</el-button></template>
  </el-dialog>
</template>
<style scoped>.parse{margin-top:12px}.hint{font-size:12px;color:#909399}pre{max-height:260px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:12px;font-size:12px}</style>
