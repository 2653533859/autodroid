<script setup>
import { computed, inject, ref, watch } from 'vue'
import ValueEditor from './ValueEditor.vue'
import { fromJson, toPlainJson, previewValue } from '@/utils/apiTesting'

const props = defineProps({ modelValue: { type: Object, required: true }, sources: Array, variables: Array, location: Array })
const emit = defineEmits(['update:modelValue', 'invalid-change'])
const allowStepReferences = inject('apiAllowStepReferences', computed(() => true))
const mode = ref('json'), draft = ref(''), error = ref(''), bound = ref(false)
let emitted = ''
watch(() => JSON.stringify(props.modelValue), serialized => {
  if (serialized === emitted) { emitted = ''; return }
  const value = props.modelValue
  error.value = ''; emit('invalid-change', false)
  try { draft.value = JSON.stringify(toPlainJson(value), null, 2); bound.value = false }
  catch { bound.value = true; mode.value = 'fields' }
}, { immediate: true })
function edit(text) {
  draft.value = text
  try {
    const value = fromJson(JSON.parse(text))
    emitted = JSON.stringify(value); error.value = ''; emit('invalid-change', false)
    emit('update:modelValue', value)
  } catch {
    error.value = 'JSON 格式不正确，请修正后保存或调试。'
    emit('invalid-change', true)
  }
}
function format() { if (!error.value) draft.value = JSON.stringify(JSON.parse(draft.value), null, 2) }
defineExpose({showFields:()=>{if(!error.value)mode.value='fields'}})
</script>
<template>
  <div class="json-body">
    <div class="json-toolbar">
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="json" :disabled="bound">JSON</el-radio-button>
        <el-radio-button value="fields" :disabled="!!error">{{ allowStepReferences ? '字段与引用' : '字段与变量' }}</el-radio-button>
        <el-radio-button value="preview" :disabled="!!error">请求预览</el-radio-button>
      </el-radio-group>
      <el-button v-if="mode === 'json'" link type="primary" :disabled="!!error" @click="format">格式化</el-button>
    </div>
    <template v-if="mode === 'json'">
      <el-input :model-value="draft" type="textarea" :autosize="{ minRows: 10, maxRows: 24 }" placeholder='{"name": "示例", "enabled": true}' aria-label="JSON 请求体" @update:model-value="edit" />
      <div v-if="error" class="json-error" role="alert">{{ error }}</div>
      <p class="hint">直接粘贴 JSON，保留数字、布尔、空值、对象和数组类型。</p>
    </template>
    <template v-else-if="mode==='preview'"><pre>{{ JSON.stringify(previewValue(modelValue,sources),null,2) }}</pre><p class="hint">变量和引用标记将在运行时取值，此预览不会修改已配置的引用。</p></template>
    <template v-else>
      <p class="hint">{{ allowStepReferences ? '按字段选择环境变量或前序步骤输出；完整对象和数组引用会保留原始类型。' : '按字段配置环境变量。跨接口的返回值引用请在场景编排中设置。' }}</p>
      <ValueEditor :model-value="modelValue" :location="location" :sources="sources" :variables="variables" @update:model-value="emit('update:modelValue', $event)" />
    </template>
  </div>
</template>
<style scoped>
.json-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.json-body :deep(textarea){font-family:monospace;line-height:1.6}
.hint{font-size:12px;color:var(--el-text-color-secondary)}
.json-error{margin-top:8px;font-size:12px;color:var(--el-color-danger)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;background:#f5f7fa;padding:12px;font-size:12px}
</style>
