<script setup>
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CirclePlus, CopyDocument, Key, Refresh } from '@element-plus/icons-vue'
import api from '@/api'
import { useUserStore } from '@/stores/useUserStore'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

const loading = ref(false)
const creating = ref(false)
const showAll = ref(false)
const tokens = ref([])

const createDialogVisible = ref(false)
const createFormRef = ref(null)
const createForm = ref({ name: '' })
const createRules = {
  name: [{ required: true, message: '请输入 Token 名称（如 jenkins-regression）', trigger: 'blur' }],
}

// 创建成功后仅本次展示的明文 token
const createdToken = ref('')

const formatDate = (value) => {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

const loadTokens = async () => {
  loading.value = true
  try {
    const params = showAll.value && isAdmin.value ? { all: 1 } : {}
    const res = await api.getApiTokens(params)
    tokens.value = res.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载 API Token 列表失败')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  createForm.value.name = ''
  createdToken.value = ''
  createFormRef.value?.clearValidate()
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    creating.value = true
    try {
      const res = await api.createApiToken(createForm.value.name.trim())
      createdToken.value = res.data?.token || ''
      await loadTokens()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '创建 Token 失败')
    } finally {
      creating.value = false
    }
  })
}

const handleCopy = async () => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(createdToken.value)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = createdToken.value
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    ElMessage.success('Token 已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

const handleCloseCreateDialog = () => {
  createDialogVisible.value = false
  createdToken.value = ''
  createForm.value.name = ''
}

const handleRevoke = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要吊销 Token「${row.name}」（${row.token_prefix}…）吗？吊销后使用该 Token 的 CI 任务将立即失效。`,
      '吊销确认',
      {
        confirmButtonText: '吊销',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch (error) {
    return
  }

  try {
    await api.revokeApiToken(row.id)
    ElMessage.success('Token 已吊销')
    await loadTokens()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '吊销 Token 失败')
  }
}

onMounted(loadTokens)
</script>

<template>
  <div class="tokens-page ad-page" v-loading="loading">
    <div class="page-header ad-page-header">
      <div>
        <h2>API Token</h2>
        <p class="page-desc">
          连接 CI 系统，管理用于自动化调用的机器凭证。
        </p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadTokens">刷新</el-button>
        <el-button type="primary" :icon="CirclePlus" @click="openCreateDialog">创建 Token</el-button>
      </div>
    </div>

    <section class="table-panel ad-surface">
      <div v-if="isAdmin" class="table-toolbar ad-toolbar">
        <el-switch
          v-model="showAll"
          active-text="查看所有人的 Token"
          inactive-text="仅看我的"
          @change="loadTokens"
        />
      </div>

      <el-table :data="tokens" row-key="id" class="token-table ad-table">
        <el-table-column label="名称" prop="name" min-width="160" />
        <el-table-column label="Token 前缀" width="160">
          <template #default="{ row }">
            <code class="token-prefix">{{ row.token_prefix }}…</code>
          </template>
        </el-table-column>
        <el-table-column v-if="showAll" label="属主" prop="username" width="130">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="155">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="最近使用" width="155">
          <template #default="{ row }">{{ formatDate(row.last_used_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
              {{ row.is_active ? '有效' : '已吊销' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              :disabled="!row.is_active"
              @click="handleRevoke(row)"
            >
              吊销
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无 API Token，点击右上角「创建 Token」生成 CI 凭证" :image-size="80" />
        </template>
      </el-table>
    </section>

    <el-dialog class="ad-dialog"
      v-model="createDialogVisible"
      title="创建 API Token"
      width="min(520px, calc(100vw - 32px))"
      :close-on-click-modal="false"
      @closed="handleCloseCreateDialog"
    >
      <!-- 第一步：输入名称 -->
      <el-form
        v-if="!createdToken"
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top" scroll-to-error
        @submit.prevent
      >
        <el-form-item label="Token 名称" prop="name">
          <el-input
            v-model="createForm.name"
            :prefix-icon="Key"
            placeholder="例如：jenkins-regression"
            maxlength="64"
            @keyup.enter="handleCreate"
          />
          <div class="form-tip">建议以「CI 系统 + 用途」命名，便于识别与轮换。</div>
        </el-form-item>
      </el-form>

      <!-- 第二步：展示明文（仅一次） -->
      <div v-else class="token-result">
        <el-alert
          type="warning"
          title="请立即复制并妥善保存，关闭后无法再查看该 Token"
          description="Token 与你的账号权限绑定，请存入 CI 的密钥管理（Credentials / Secrets），不要写入代码仓库。"
          :closable="false"
          show-icon
        />
        <div class="token-display">
          <code class="token-plaintext">{{ createdToken }}</code>
          <el-button type="primary" :icon="CopyDocument" @click="handleCopy">复制</el-button>
        </div>
      </div>

      <template #footer>
        <template v-if="!createdToken">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="handleCreate">生成 Token</el-button>
        </template>
        <template v-else>
          <el-button type="primary" @click="handleCloseCreateDialog">我已保存，关闭</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tokens-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
  background: var(--ad-bg);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 600;
  color: var(--ad-text);
}

.page-desc {
  margin: 0;
  color: var(--ad-muted);
  font-size: 13px;
}

.page-desc code {
  background: var(--ad-bg);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
  color: var(--ad-text);
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.table-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 16px;
  border: 1px solid var(--ad-border);
  border-radius: var(--ad-panel-radius);
  background: var(--ad-surface);
}

.table-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.token-table {
  flex: 1;
  min-height: 0;
}

.token-prefix {
  background: var(--ad-bg);
  padding: 2px 8px;
  border-radius: var(--ad-radius);
  font-size: 12px;
  color: var(--ad-text);
}

.token-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.token-display {
  display: flex;
  align-items: center;
  gap: 10px;
}

.token-plaintext {
  flex: 1;
  min-width: 0;
  background: var(--ad-primary-soft);
  color: var(--ad-text);
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 13px;
  word-break: break-all;
  user-select: all;
}

@media (max-width: 720px) {
  .tokens-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    width: 100%;
  }
}
@media(max-width:760px){.header-actions{flex-wrap:wrap}.page-header h2{font-size:20px}.page-desc,.setting-value,.setting-title,.token-prefix,.token-plaintext{font-size:14px}.token-display{align-items:stretch;flex-direction:column}.table-panel{overflow:auto;flex-shrink:0;min-height:260px}.tokens-page,.admin-page{overflow:auto}.password-panel{padding:16px}.user-cell{flex-wrap:wrap}}
</style>
