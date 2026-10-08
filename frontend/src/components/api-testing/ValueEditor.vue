<script setup>
import { ref, computed, inject } from 'vue'
import { ElMessage } from 'element-plus'
import ReferencePicker from './ReferencePicker.vue'
import { copy, literal, fromJson, referenceLabel, sourceLabel, flattenFields, fieldName } from '@/utils/apiTesting'
defineOptions({name:'ApiValueEditor'})
const props=defineProps({modelValue:{type:Object,required:true},sources:{type:Array,default:()=>[]},variables:{type:Array,default:()=>[]},textOnly:Boolean,compact:Boolean,location:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:modelValue'])
const allowStepReferences=inject('apiAllowStepReferences',computed(()=>true)), jump=inject('apiSelectStep',null)
const picker=ref(false),append=ref(false),preferredTab=ref('steps'),jsonDialog=ref(false),jsonText=ref(''),newKey=ref('')
const partIndex=ref(-1)
const partSource=part=>props.sources.find(s=>s.id===part.step_id)
function repickPart(i,part){partIndex.value=i;append.value=false;preferredTab.value=part.kind==='env'?'env':'steps';picker.value=true}
const val=computed(()=>props.modelValue||literal())
const mode=computed(()=>val.value.kind==='literal'?(val.value.value===null?'null':typeof val.value.value):val.value.kind)
const source=computed(()=>props.sources.find(s=>s.id===val.value.step_id))
const example=computed(()=>flattenFields(source.value?.fields).find(f=>JSON.stringify(f.path)===JSON.stringify(val.value.path)))
const types=[['string','文本'],['number','数字'],['boolean','布尔'],['null','空值'],['object','对象'],['array','数组']]
const typeLabel=computed(()=>types.find(type=>type[0]===mode.value)?.[1]||'类型')
const referenceCaption=value=>value.kind==='env'?value.name:`${props.sources.find(s=>s.id===value.step_id)?.name||'失效步骤'} · ${fieldName(value.path)}`
function set(value){emit('update:modelValue',value)}
function switchMode(type){const options={string:literal(''),number:literal(0),boolean:literal(false),null:literal(null),object:{kind:'object',fields:{}},array:{kind:'array',items:[]}};if(options[type])set(options[type])}
function action(command){
  partIndex.value=-1
  if(command==='fixed'){set(literal(''));return}
  if(command==='json'){jsonDialog.value=true;return}
  append.value=command==='append';preferredTab.value=command==='env'?'env':'steps';picker.value=true
}
function selectRef(value){if(partIndex.value>=0){updateChild(partIndex.value,value);partIndex.value=-1;return}if(append.value){const parts=val.value.kind==='template'?copy(val.value.parts):[copy(val.value)];parts.push(value);parts.push(literal(''));set({kind:'template',parts})}else set(value)}
function updateChild(key,value){const next=copy(val.value);if(next.kind==='object')next.fields[key]=value;else if(next.kind==='array')next.items[key]=value;else next.parts[key]=value;set(next)}
function removeChild(key){const next=copy(val.value);if(next.kind==='object')delete next.fields[key];else if(next.kind==='array')next.items.splice(key,1);else next.parts.splice(key,1);set(next)}
function addField(){const next=copy(val.value);if(next.kind==='object'){if(!newKey.value||Object.hasOwn(next.fields,newKey.value))return ElMessage.warning('字段名为空或已存在');Object.defineProperty(next.fields,newKey.value,{value:literal(),enumerable:true,writable:true,configurable:true});newKey.value=''}else next.items.push(literal());set(next)}
function pasteJson(){try{set(fromJson(JSON.parse(jsonText.value)));jsonDialog.value=false}catch{ElMessage.error('请输入有效 JSON')}}
</script>
<template>
<div class="value-editor" :class="{'value-editor--compact':compact}" :data-config-path="JSON.stringify(location)">
  <div class="value-line">
    <el-input v-if="mode==='string'" :model-value="val.value" placeholder="输入值" @update:model-value="set(literal($event))" />
    <el-input-number v-else-if="mode==='number'" :model-value="val.value" :controls="false" @update:model-value="set(literal($event??0))" />
    <el-switch v-else-if="mode==='boolean'" :model-value="val.value" @update:model-value="set(literal($event))" />
    <span v-else-if="mode==='null'" class="hint">null</span>
    <el-popover v-else-if="['ref','env'].includes(mode)" trigger="click" width="330">
      <template #reference><el-tag class="reference-tag" tabindex="0" role="button" :title="referenceLabel(val,sources)" :type="mode==='ref'&&!source?'danger':'primary'" closable @close.stop="set(literal())">{{ referenceCaption(val) }}</el-tag></template>
      <p>{{ referenceLabel(val,sources) }}</p><p v-if="source" class="hint">{{ sourceLabel(source) }}</p><pre v-if="example && Object.hasOwn(example,'example')">{{ JSON.stringify(example.example,null,2) }}</pre>
      <el-button link type="primary" @click="action(mode==='env'?'env':'ref')">重新选择</el-button><el-button v-if="source&&jump" link @click="jump(source.id)">跳转来源步骤</el-button>
    </el-popover>
    <div v-else-if="mode==='template'" class="inline-template">
      <template v-for="(part,i) in val.parts" :key="i">
        <el-input v-if="part.kind==='literal'" :model-value="String(part.value??'')" placeholder="文字" @update:model-value="updateChild(i,literal($event))" />
        <el-popover v-else trigger="click" width="330"><template #reference><el-tag closable class="reference-tag" tabindex="0" role="button" :title="referenceLabel(part,sources)" @close.stop="removeChild(i)">{{ referenceCaption(part) }}</el-tag></template><p>{{ referenceLabel(part,sources) }}</p><p v-if="partSource(part)" class="hint">{{ sourceLabel(partSource(part)) }}</p><el-button link type="primary" @click="repickPart(i,part)">重新选择</el-button><el-button v-if="partSource(part)&&jump" link @click="jump(part.step_id)">跳转来源步骤</el-button></el-popover>
      </template>
    </div>
    <span v-else class="hint structure-summary">{{ mode==='object'?Object.keys(val.fields).length+' 个字段':val.items.length+' 个元素' }}</span>
    <el-dropdown v-if="!textOnly&&!['ref','env','template'].includes(mode)" trigger="click" @command="switchMode"><el-button link size="small" class="type-trigger" aria-label="值类型">{{ typeLabel }} ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="type in types" :key="type[0]" :command="type[0]">{{ type[1] }}</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
    <el-dropdown trigger="click" @command="action"><el-button size="small" class="source-button" aria-label="选择值来源">取值 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="fixed">固定值</el-dropdown-item><el-dropdown-item command="env">环境变量</el-dropdown-item><el-dropdown-item v-if="allowStepReferences" command="ref">前序步骤输出</el-dropdown-item><el-dropdown-item v-if="textOnly" command="append">在文字中插入变量 / 引用</el-dropdown-item><el-dropdown-item v-if="!textOnly" command="json">粘贴 JSON</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
  </div>
  <div v-if="mode==='object'||mode==='array'" class="children">
    <div v-for="(child,key) in (mode==='object'?val.fields:val.items)" :key="key" class="child"><span class="child-key">{{ mode==='array'?'['+key+']':key }}</span><ApiValueEditor :model-value="child" :sources="sources" :variables="variables" :location="[...location,mode==='object'?'fields':'items',key]" compact @update:model-value="updateChild(key,$event)" /><el-button class="remove-child" :aria-label="'删除字段 ' + key" link type="danger" size="small" @click="removeChild(key)">×</el-button></div>
    <div class="value-line"><el-input v-if="mode==='object'" v-model="newKey" size="small" placeholder="新字段名" style="max-width:160px" @keyup.enter="addField" /><el-button link type="primary" size="small" @click="addField">{{ mode==='array'?'+ 数组元素':'+ 字段' }}</el-button></div>
  </div>
  <ReferencePicker v-model="picker" :preferred-tab="preferredTab" :sources="sources" :variables="variables" :allow-step-references="allowStepReferences" :text-only="textOnly||append" @select="selectRef" />
  <el-dialog class="ad-dialog" v-model="jsonDialog" title="粘贴 JSON" width="min(600px,94vw)" append-to-body><el-input v-model="jsonText" type="textarea" :rows="10" /><template #footer><el-button type="primary" @click="pasteJson">使用 JSON</el-button></template></el-dialog>
</div>
</template>
<style scoped>
.value-editor{min-width:0;flex:1}.value-line{display:flex;align-items:center;gap:8px;min-height:32px;min-width:0}.value-line>.el-input,.value-line>.el-input-number{flex:1;min-width:60px;width:auto}.type-trigger{color:var(--ad-muted);font-size: 12px;font-weight:400}.structure-summary{flex:1}.source-button{margin:0}.reference-tag{cursor:pointer;max-width:100%;height:auto;white-space:normal;padding:5px 8px;overflow-wrap:anywhere;flex:1}.children{border-left:1px solid var(--ad-border);padding:8px 0 0 10px;margin-top:8px}.child{display:flex;align-items:start;gap:8px;margin-bottom:8px}.child-key{width:80px;flex-shrink:0;overflow-wrap:anywhere;font:12px/32px monospace}.hint{color:var(--ad-muted);font-size:12px}.inline-template{display:flex;flex:1;min-width:0;flex-wrap:wrap;gap:4px;border:1px solid var(--ad-border);border-radius: var(--ad-radius);padding:4px}.inline-template>.el-input{flex:1;min-width:65px;width:90px}.inline-template :deep(.el-input__wrapper){box-shadow: none;padding:0 5px}.inline-template .el-tag{max-width:100%;overflow:hidden;text-overflow:ellipsis;height:30px}pre{max-height:160px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}
.value-editor--compact{container-type:inline-size;container-name:api-value}
.value-editor--compact>.value-line{flex-wrap:wrap}
.value-editor--compact>.value-line>.value-type{width:82px}
.value-editor--compact>.value-line>.el-input,.value-editor--compact>.value-line>.el-input-number{flex:1 1 120px;min-width:0;max-width:100%}
.value-editor--compact>.children>.child{min-width:0}
.value-editor--compact .remove-child{margin:0}
@container api-value (max-width:420px){
  .value-editor--compact>.children>.child{display:grid;grid-template-columns:minmax(0,1fr) 20px;gap:4px 8px}
  .value-editor--compact>.children>.child>.child-key{grid-column:1;width:auto;line-height:22px}
  .value-editor--compact>.children>.child>.value-editor{grid-column:1/-1;grid-row:2}
  .value-editor--compact>.children>.child>.remove-child{grid-column:2;grid-row:1}
}
@media(max-width:760px){.value-line{flex-wrap:wrap}.value-line>.el-input{min-width:100px}.child-key,.hint,.type-trigger{font-size:14px}.child{flex-wrap:wrap}.child-key{width:auto;flex-basis:100%}.child>.value-editor{min-width:0}.reference-tag{min-height:36px;display:flex;align-items:center}.children{padding-left:8px}}
</style>
