<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { apiError } from '@/utils/apiTesting'
const props=defineProps({modelValue:Boolean,interfaceId:[Number,String]})
const emit=defineEmits(['update:modelValue'])
const router=useRouter(),mode=ref('new'),chosen=ref(null),rows=ref([]),busy=ref(false)
let request=0
async function search(keyword=''){const seq=++request;busy.value=true;try{const {data}=await api.apiTesting.get('/scenarios',{keyword,limit:30});if(seq===request)rows.value=data.items}catch(e){ElMessage.error(apiError(e))}finally{if(seq===request)busy.value=false}}
watch(()=>props.modelValue,open=>{if(open){mode.value='new';chosen.value=null;search()}})
function add(){emit('update:modelValue',false);router.push({path:mode.value==='new'?'/api-testing/scenarios/create':`/api-testing/scenarios/${chosen.value}/edit`,query:{add_interface:String(props.interfaceId)}})}
</script>
<template><el-dialog :model-value="modelValue" title="加入场景" width="min(480px,95vw)" @update:model-value="emit('update:modelValue',$event)"><p>将此接口加入场景草稿，保存场景后生效。</p><el-radio-group v-model="mode"><el-radio value="new">新建场景</el-radio><el-radio value="existing">已有场景</el-radio></el-radio-group><el-select v-if="mode==='existing'" v-model="chosen" filterable remote :remote-method="search" :loading="busy" placeholder="搜索并选择场景" aria-label="目标场景" style="width:100%;margin-top:16px"><el-option v-for="row in rows" :key="row.id" :label="row.name" :value="row.id" /></el-select><template #footer><el-button @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" :disabled="!interfaceId||(mode==='existing'&&!chosen)" @click="add">加入草稿</el-button></template></el-dialog></template>
