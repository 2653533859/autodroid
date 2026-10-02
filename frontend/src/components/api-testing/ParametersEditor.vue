<script setup>
import ValueEditor from './ValueEditor.vue'
import { copy, literal } from '@/utils/apiTesting'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, sources: Array, variables: Array, location: {type:Array,default:()=>[]} })
const emit = defineEmits(['update:modelValue'])
function update(i, key, value) { const rows = copy(props.modelValue); rows[i][key] = value; emit('update:modelValue', rows) }
</script>
<template>
  <div>
    <div v-for="(row, i) in modelValue" :key="i" class="param-row" :data-param-index="i">
      <el-checkbox :model-value="row.enabled" @update:model-value="update(i, 'enabled', $event)" />
      <el-input :model-value="row.name" placeholder="参数名" class="param-name" @update:model-value="update(i, 'name', $event)" />
      <ValueEditor :model-value="row.value" :location="[...location,i,'value']" :sources="sources" :variables="variables" text-only @update:model-value="update(i, 'value', $event)" />
      <el-dropdown trigger="click" @command="emit('update:modelValue', modelValue.filter((_, j) => i !== j))"><el-button link size="small" aria-label="参数操作">···</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="delete">删除参数</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
    </div>
    <el-button link type="primary" @click="emit('update:modelValue', [...modelValue, { name: '', value: literal(), enabled: true }])">+ 添加参数</el-button>
  </div>
</template>
<style scoped>
.param-row{display:grid;grid-template-columns:20px minmax(90px,130px) minmax(0,1fr) 32px;gap:10px;align-items:start;margin-bottom:16px}
.param-row>.el-button{height:32px;margin:0}.param-name{width:100%;min-width:0}
</style>
