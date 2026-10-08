<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { apiError, copy, effectiveStep, referenceIssues, responseFields, sampleTypes } from '@/utils/apiTesting'
import RequestEditor from './RequestEditor.vue'
const props=defineProps({modelValue:Boolean,step:Object,sources:Array,variables:Array,fields:Array,sample:Object})
const emit=defineEmits(['update:modelValue','saved'])
const draft=ref(null),name=ref(''),folder=ref(null),folders=ref([]),busy=ref(false),invalid=ref(false)
const references=computed(()=>draft.value?referenceIssues([{id:'public-copy',name:name.value,kind:'request',snapshot:draft.value,overrides:{}}]):[])
watch(()=>props.modelValue,async open=>{if(!open)return;draft.value=copy(effectiveStep(props.step));name.value=props.step.name;folder.value=null;invalid.value=false;try{folders.value=(await api.apiTesting.get('/folders')).data.filter(f=>f.kind==='interface')}catch(e){ElMessage.error(apiError(e))}})
async function save(){if(busy.value||!name.value.trim()||invalid.value||references.value.length)return;busy.value=true;try{const {data}=await api.apiTesting.post('/interfaces',{name:name.value.trim(),folder_id:folder.value,config:copy(draft.value),sample:props.sample?copy(props.sample):null,sample_types:sampleTypes(props.fields||responseFields({}))});emit('saved',data);emit('update:modelValue',false);ElMessage.success('已另存到接口库，原场景保持不变')}catch(e){ElMessage.error(apiError(e))}finally{busy.value=false}}
</script>
<template><el-dialog class="ad-dialog" :model-value="modelValue" title="另存到接口库" width="min(920px,95vw)" @update:model-value="emit('update:modelValue',$event)"><template v-if="draft"><el-alert v-if="references.length" title="公共接口需要独立配置。请把下方前序步骤引用替换为环境变量或固定输入；这不会修改原场景。" type="warning" :closable="false" /><el-form label-position="top" class="metadata"><el-form-item label="接口名称"><el-input v-model="name" maxlength="200" /></el-form-item><el-form-item label="接口目录"><el-select v-model="folder" clearable><el-option v-for="f in folders" :key="f.id" :value="f.id" :label="f.name" /></el-select></el-form-item></el-form><div class="editor"><RequestEditor v-model="draft" :sources="sources" :variables="variables" :fields="fields" :allow-step-references="false" @invalid-change="invalid=$event" /></div></template><template #footer><el-button @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" :loading="busy" :disabled="!name.trim()||invalid||!!references.length" @click="save">保存公共接口</el-button></template></el-dialog></template>
<style scoped>.metadata{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}.editor{min-width:0;padding-top:12px;border-top:1px solid var(--ad-border)}@media(max-width:760px){.metadata{grid-template-columns:1fr;gap:0}}</style>
