<script setup>
import { ref, computed, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { pathLabel, fieldName, shortValue, mergeResponseFields, flattenFields, sourceLabel } from '@/utils/apiTesting'
const props = defineProps({ modelValue: Boolean, sources: { type: Array, default: () => [] }, variables: { type: Array, default: () => [] }, textOnly: Boolean, allowStepReferences: { type: Boolean, default: true }, fieldOnly: Boolean, stepOnly:Boolean, preferredTab:String })
const emit = defineEmits(['update:modelValue', 'select'])
const editEnvironment=inject('apiEditEnvironment',null)
const tab = ref(props.allowStepReferences ? 'steps' : 'env'), selected = ref(null), filter = ref('')
const hasExample=field=>Object.hasOwn(field,'example')&&!['object','array'].includes(field.type)
const tree = computed(() => props.sources.map(source => {
  const build = fields => fields.map(field => ({ ...field, key: `${source.id}:${JSON.stringify(field.path)}`, source: source.id,
    label: fieldName(field.path), origin:source.origin, children: build(field.children || []),
    disabled: props.textOnly && ['object', 'array'].includes(field.type),
  })).filter(row => !filter.value || pathLabel(row.path).toLowerCase().includes(filter.value.toLowerCase()) || row.children.length)
  return { key: source.id, label: source.name, description: sourceLabel(source), children: build(mergeResponseFields(source.fields)), disabled: true }
}))
const expanded = computed(() => props.sources.flatMap(s=>[s.id,...flattenFields(mergeResponseFields(s.fields)).filter(f=>filter.value || (f.path[0]==='body' && f.path.length<3)).map(f=>`${s.id}:${JSON.stringify(f.path)}`)]))
function choose() {
  if (!selected.value || selected.value.disabled) return
  emit('select', { kind: 'ref', step_id: selected.value.source, path: selected.value.path }, selected.value)
  emit('update:modelValue', false)
}
function chooseVariable(name) {
  emit('select', { kind: 'env', name }); emit('update:modelValue', false)
}
function manageEnvironment(){emit('update:modelValue',false);editEnvironment?.()}
async function copyExample(){try{await navigator.clipboard.writeText(typeof selected.value.example==='string'?selected.value.example:JSON.stringify(selected.value.example,null,2));ElMessage.success('已复制')}catch{ElMessage.error('复制失败，请手动选择复制')}}
</script>
<template>
  <el-dialog class="ad-dialog" :model-value="modelValue" :title="fieldOnly ? '选择响应字段' : allowStepReferences ? '插入引用' : '选择环境变量'" width="min(680px, 94vw)" append-to-body @update:model-value="emit('update:modelValue', $event)" @open="selected = null; filter = ''; tab = allowStepReferences ? preferredTab || 'steps' : 'env'">
    <el-tabs v-model="tab">
      <el-tab-pane v-if="allowStepReferences" :label="fieldOnly ? '当前接口响应' : '前序步骤的输出'" name="steps">
        <el-input v-model="filter" placeholder="搜索字段" clearable />
        <div class="reference-tree"><el-tree :key="filter" :data="tree" node-key="key" :default-expanded-keys="expanded" highlight-current @node-click="selected = $event">
          <template #default="{ data }"><div class="field-row" :class="{ muted: data.disabled && data.path }"><span>{{ data.label }}</span><small v-if="data.description">{{ data.description }}</small><small v-else-if="data.path && hasExample(data)">{{ shortValue(data.example) }}</small></div></template>
        </el-tree></div>
        <div v-if="selected?.path" class="selection"><b>{{ pathLabel(selected.path) }}</b><p v-if="selected.disabled" class="hint">此位置仅支持文本或单个值，不能使用整个对象或数组，请展开选择其中的字段。</p><details v-if="hasExample(selected)"><summary>查看完整示例值</summary><pre>{{ JSON.stringify(selected.example,null,2) }}</pre><el-button link @click="copyExample">复制示例值</el-button></details></div>
        <p v-if="!sources.length" class="empty-hint">没有可引用的前序步骤。先添加接口并调试，或保存响应样例。</p>
        <p class="hint">选择字段路径，不固定示例值。数组下标从 0 开始，顺序变化可能影响引用。</p>
      </el-tab-pane>
      <el-tab-pane v-if="!fieldOnly&&!stepOnly" label="环境变量" name="env">
        <p v-if="!variables.length" class="empty-hint">当前环境暂无变量。<el-button v-if="editEnvironment" link type="primary" @click="manageEnvironment">配置环境与变量</el-button><span v-else>请先选择环境并配置变量。</span></p>
        <div v-for="variable in variables" :key="variable.key" class="variable"><el-button link type="primary" @click="chooseVariable(variable.key)">{{ variable.key }}</el-button><span>{{ variable.is_secret ? '敏感变量' : variable.description }}</span></div>
        <el-button v-if="variables.length&&editEnvironment" link type="primary" @click="manageEnvironment">管理环境变量</el-button>
      </el-tab-pane>
    </el-tabs>
    <template #footer><el-button @click="emit('update:modelValue', false)">取消</el-button><el-button v-if="tab === 'steps'" type="primary" :disabled="!selected || selected.disabled" @click="choose">{{ fieldOnly ? '选择此字段' : '引用此字段' }}</el-button></template>
  </el-dialog>
</template>
<style scoped>.reference-tree{max-height:320px;overflow:auto;margin-top:12px}.hint,.muted,small{color:var(--ad-muted);font-size:12px}.empty-hint{padding:16px 0;font-size:13px;color:var(--ad-muted);line-height:22px}.variable{display:flex;gap:16px;margin:12px 0}.field-row{display:flex;gap:14px;align-items:center;min-width:0}.field-row small{overflow:hidden;text-overflow:ellipsis}.selection{border-top:1px solid var(--ad-border);margin-top:12px;padding-top:12px;overflow-wrap:anywhere}.selection pre{max-height:140px;overflow:auto;white-space:pre-wrap}summary{cursor:pointer;font-size:12px;margin-top:8px}@media(max-width:760px){.hint,.muted,small,.empty-hint,.variable{font-size:14px}.variable{flex-wrap:wrap;gap:4px 12px}.field-row{flex-wrap:wrap;gap:4px}.field-row small{max-width:100%}.reference-tree :deep(.el-tree-node__content){height:auto;min-height:44px}}
</style>
