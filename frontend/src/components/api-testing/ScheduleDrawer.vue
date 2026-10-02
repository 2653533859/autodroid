<script setup>
import {ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {apiError} from '@/utils/apiTesting'
const props=defineProps({modelValue:Boolean,scenario:Object,environments:Array,envId:Number,notificationConfigured:Boolean})
const emit=defineEmits(['update:modelValue'])
const items=ref([]),saving=ref(false),editing=ref(null),form=ref({})
function reset(){editing.value=null;form.value={name:`${props.scenario?.name||'接口场景'} · 定时`,env_id:props.envId||null,strategy:'DAILY',time:'08:00',days:[],interval_value:30,interval_unit:'minutes',run_date:'',notify:false}}
async function load(){try{items.value=(await api.apiTesting.get(`/scenarios/${props.scenario.id}/schedules`)).data.items}catch(e){ElMessage.error(apiError(e))}}
watch(()=>props.modelValue,open=>{if(open){reset();load()}})
function edit(item){editing.value=item.id;const c=item.strategy_config;form.value={name:item.name,env_id:c.env_id||null,strategy:item.strategy,time:`${String(c.hour||0).padStart(2,'0')}:${String(c.minute||0).padStart(2,'0')}`,days:c.days||[],interval_value:c.interval_value||30,interval_unit:c.interval_unit||'minutes',run_date:c.run_date||'',notify:item.enable_notification}}
async function save(){
 if(!form.value.name.trim())return ElMessage.warning('请输入任务名称')
 if(form.value.strategy==='WEEKLY'&&!form.value.days.length)return ElMessage.warning('请选择星期')
 if(form.value.strategy==='ONCE'&&(!form.value.run_date||new Date(form.value.run_date)<=new Date()))return ElMessage.warning('请选择未来的执行时间')
 saving.value=true
 try{const f=form.value,[hour,minute]=f.time.split(':').map(Number),config={_task_type:'api',api_scenario_id:props.scenario.id,env_id:f.env_id,hour,minute,days:f.days,interval_value:f.interval_value,interval_unit:f.interval_unit,run_date:f.run_date};const payload={name:f.name,scenario_id:null,device_serials:[],strategy:f.strategy,strategy_config:config,enable_notification:f.notify};if(editing.value)await api.updateTask(editing.value,payload);else await api.createTask(payload);ElMessage.success('定时任务已保存');reset();await load()}catch(e){ElMessage.error(apiError(e))}finally{saving.value=false}
}
async function toggle(item){try{await api.toggleTask(item.id);await load()}catch(e){ElMessage.error(apiError(e))}}
</script>
<template><el-drawer :model-value="modelValue" title="定时与通知" size="min(620px,95vw)" @update:model-value="emit('update:modelValue',$event)">
  <el-alert :title="notificationConfigured?'接口自动化飞书通知已配置':'接口自动化飞书通知尚未配置，可由管理员在系统设置中配置'" :type="notificationConfigured?'success':'info'" :closable="false" />
  <h3>已有定时任务</h3><div v-for="item in items" :key="item.id" class="task"><b>{{ item.name }}</b><p>{{ item.formatted_schedule }} · {{ item.is_active?'已启用':'已暂停' }}</p><p>下次运行：{{ item.next_run_time?.replace('T',' ').slice(0,19)||'暂无' }} · 通知：{{ item.enable_notification?'开启':'关闭' }}</p><el-button link type="primary" @click="edit(item)">编辑</el-button><el-button link @click="toggle(item)">{{ item.is_active?'暂停':'启用' }}</el-button></div><p v-if="!items.length" class="hint">尚未创建定时任务</p>
  <h3>{{ editing?'编辑任务':'新建定时任务' }}</h3><el-form label-position="top"><el-form-item label="任务名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="运行环境"><el-select v-model="form.env_id" clearable><el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" /></el-select></el-form-item><el-form-item label="执行频率"><el-radio-group v-model="form.strategy"><el-radio-button value="DAILY">每天</el-radio-button><el-radio-button value="WEEKLY">每周</el-radio-button><el-radio-button value="INTERVAL">间隔</el-radio-button><el-radio-button value="ONCE">一次</el-radio-button></el-radio-group></el-form-item><el-form-item v-if="form.strategy==='WEEKLY'" label="星期"><el-checkbox-group v-model="form.days"><el-checkbox v-for="(day,i) in ['一','二','三','四','五','六','日']" :key="i" :value="i">周{{ day }}</el-checkbox></el-checkbox-group></el-form-item><el-form-item v-if="['DAILY','WEEKLY'].includes(form.strategy)" label="执行时间"><el-time-picker v-model="form.time" format="HH:mm" value-format="HH:mm" :clearable="false" /></el-form-item><el-form-item v-if="form.strategy==='INTERVAL'" label="间隔"><el-input-number v-model="form.interval_value" :min="1" :max="1440" /><el-select v-model="form.interval_unit" style="width:100px"><el-option label="分钟" value="minutes" /><el-option label="小时" value="hours" /></el-select></el-form-item><el-form-item v-if="form.strategy==='ONCE'" label="执行时间"><el-date-picker v-model="form.run_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item><el-checkbox v-model="form.notify" :disabled="!notificationConfigured">运行后发送飞书摘要和报告链接</el-checkbox></el-form>
  <template #footer><el-button v-if="editing" @click="reset">取消编辑</el-button><el-button type="primary" :loading="saving" @click="save">保存定时任务</el-button></template>
</el-drawer></template>
<style scoped>h3{font-size:14px;margin-top:24px}.task{padding:12px;border:1px solid #ebeef5;border-radius:4px;margin-bottom:8px}.task p,.hint{font-size:12px;color:#909399}.el-select{width:100%}</style>
