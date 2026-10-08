<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { apiError } from '@/utils/apiTesting'

const props=defineProps({modelValue:Boolean,variables:{type:Array,default:()=>[]},envName:String,envId:{type:Number,default:null},environments:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:modelValue','refresh'])
const environments=ref([]),variables=ref([]),activeId=ref(null),loading=ref(false),saving=ref(false)
const revealed=ref(new Set())
function toggleReveal(id){const next=new Set(revealed.value);next.has(id)?next.delete(id):next.add(id);revealed.value=next}
const envDialog=ref(false),variableDialog=ref(false),editingEnv=ref(null),editingVariable=ref(null)
const envForm=ref({name:'',description:''}),variableForm=ref({key:'',value:'',description:'',is_secret:false})
const activeEnv=computed(()=>environments.value.find(env=>env.id===activeId.value))
let revision=0
async function loadVariables(){
  const current=++revision,environment=activeId.value
  if(!environment){variables.value=[];loading.value=false;return}
  loading.value=true
  try{const {data}=await api.getVariables(environment);if(current===revision)variables.value=data}
  catch(error){if(current===revision)ElMessage.error(apiError(error))}
  finally{if(current===revision)loading.value=false}
}
async function open(){
  revealed.value=new Set()
  activeId.value=props.envId
  environments.value=props.environments
  variables.value=props.variables
  try{environments.value=(await api.getEnvironments()).data;await loadVariables()}
  catch(error){ElMessage.error(apiError(error))}
}
watch(()=>props.modelValue,value=>{if(value)open();else revision++})
function selectEnvironment(){loadVariables();emit('refresh',activeId.value)}
function editEnvironment(environment=null){
  editingEnv.value=environment
  envForm.value={name:environment?.name||'',description:environment?.description||''}
  envDialog.value=true
}
async function saveEnvironment(){
  if(saving.value)return
  if(!envForm.value.name.trim())return ElMessage.warning('请输入环境名称')
  saving.value=true
  try{
    const payload={name:envForm.value.name.trim(),description:envForm.value.description}
    const {data}=editingEnv.value?await api.updateEnvironment(editingEnv.value.id,payload):await api.createEnvironment(payload)
    activeId.value=data.id
    environments.value=(await api.getEnvironments()).data
    await loadVariables()
    emit('refresh',activeId.value)
    envDialog.value=false
    ElMessage.success(editingEnv.value?'环境已更新':'环境已创建')
  }catch(error){ElMessage.error(apiError(error))}finally{saving.value=false}
}
function editVariable(variable=null){
  if(!activeId.value)return ElMessage.warning('请先选择或创建环境')
  editingVariable.value=variable
  variableForm.value={key:variable?.key||'',value:variable?.value||'',description:variable?.description||'',is_secret:variable?.is_secret||false}
  variableDialog.value=true
}
async function saveVariable(){
  if(saving.value)return
  const key=variableForm.value.key.trim()
  if(!/^[A-Z0-9_]+$/.test(key))return ElMessage.warning('变量名仅允许大写字母、数字和下划线')
  if(!activeId.value)return ElMessage.warning('请先选择环境')
  saving.value=true
  try{
    const payload={...variableForm.value,key}
    if(editingVariable.value)await api.updateVariable(editingVariable.value.id,payload)
    else await api.createVariable(activeId.value,payload)
    await loadVariables()
    emit('refresh',activeId.value)
    variableDialog.value=false
    ElMessage.success('变量已保存，可直接在请求中选择')
  }catch(error){ElMessage.error(apiError(error))}finally{saving.value=false}
}
</script>
<template>
  <el-drawer class="ad-drawer" :model-value="modelValue" title="环境与变量" size="min(650px,95vw)" @update:model-value="emit('update:modelValue',$event)">
    <div class="environment-tools"><el-select v-model="activeId" clearable placeholder="选择运行环境" @change="selectEnvironment"><el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" /></el-select><el-button @click="editEnvironment()">新建环境</el-button><el-button v-if="activeEnv" link @click="editEnvironment(activeEnv)">编辑</el-button></div>
    <p v-if="activeEnv?.description" class="hint">{{ activeEnv.description }}</p>
    <template v-if="activeId"><div class="variables-heading"><b>{{ activeEnv?.name||envName }} 的变量</b><el-button type="primary" plain @click="editVariable()">添加变量</el-button></div><p class="hint">环境变量由团队共享，保存后在使用此环境的请求中生效。</p><el-table class="ad-table" v-loading="loading" :data="variables"><el-table-column prop="key" label="变量" min-width="120" show-overflow-tooltip /><el-table-column label="值" min-width="150"><template #default="{row}"><div class="variable-value"><span>{{ row.is_secret&&!revealed.has(row.id)?'••••••':row.value }}</span><el-button v-if="row.is_secret" link :aria-label="revealed.has(row.id)?'隐藏变量值':'显示变量值'" @click="toggleReveal(row.id)">{{ revealed.has(row.id)?'隐藏':'显示' }}</el-button></div></template></el-table-column><el-table-column prop="description" label="说明" min-width="110" show-overflow-tooltip /><el-table-column width="60"><template #default="{row}"><el-button link type="primary" @click="editVariable(row)">编辑</el-button></template></el-table-column><template #empty><div class="empty-hint">添加 BASE_URL、账号或凭证，随后可在请求中直接引用。</div></template></el-table></template>
    <p v-else class="empty-hint">选择一个环境查看变量，或创建第一个环境。</p>
    <template #footer><el-button type="primary" @click="emit('update:modelValue',false)">完成</el-button></template>
  </el-drawer>
  <el-dialog class="ad-dialog" v-model="envDialog" :title="editingEnv?'编辑环境':'新建环境'" width="min(480px,94vw)" append-to-body><el-form label-position="top" @submit.prevent="saveEnvironment"><el-form-item label="环境名称" required><el-input v-model="envForm.name" placeholder="例如：测试环境" maxlength="100" /></el-form-item><el-form-item label="说明"><el-input v-model="envForm.description" type="textarea" :rows="2" /></el-form-item></el-form><template #footer><el-button @click="envDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveEnvironment">保存环境</el-button></template></el-dialog>
  <el-dialog class="ad-dialog" v-model="variableDialog" :title="editingVariable?'编辑变量':'添加变量'" width="min(520px,94vw)" append-to-body><el-form label-position="top" @submit.prevent="saveVariable"><el-form-item label="变量名" required><el-input v-model="variableForm.key" placeholder="例如：BASE_URL 或 TOKEN" /></el-form-item><el-form-item label="变量值"><el-input v-model="variableForm.value" type="textarea" :rows="3" placeholder="输入实际值" /></el-form-item><el-form-item label="说明"><el-input v-model="variableForm.description" /></el-form-item><el-checkbox v-model="variableForm.is_secret">标记为敏感变量</el-checkbox></el-form><template #footer><el-button @click="variableDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveVariable">保存变量</el-button></template></el-dialog>
</template>
<style scoped>
.environment-tools{display:flex;align-items:center;gap:8px}.environment-tools>.el-select{flex:1;min-width:0}.environment-tools .el-button+.el-button{margin-left:0}.variables-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:26px;font-size: 13px}.hint{font-size:12px;color:var(--ad-muted);line-height:20px}.empty-hint{font-size:13px;color:var(--ad-muted);line-height:22px;padding:20px 0;white-space:normal}
.variable-value{display:flex;gap:8px;align-items:center;min-width:0}.variable-value>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}.variables-heading{margin-top:16px}.environment-tools{flex-wrap:wrap}
@media(max-width:760px){.environment-tools>.el-select{flex-basis:100%;min-width:160px}.hint,.empty-hint,.variables-heading{font-size:14px}}
</style>
