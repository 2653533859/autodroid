<script setup>
import { chartColors } from '@/utils/chartTheme'
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import api from '@/api'
import { runStatusTagType, runStatusLabel } from '@/utils/statusMeta'

const visible = defineModel({ type: Boolean, default: false })

const loadError = ref('')
const loading = ref(false)
const days = ref(30)
const report = ref(null)

const fetchReport = async () => {
    loading.value = true
    loadError.value = ''
  try {
        const { data } = await api.getFlakyAnalysis({ days: days.value, limit: 20 })
        report.value = data
    } catch (err) {
    loadError.value = '获取稳定性分析失败，请重试'
        ElMessage.error('获取稳定性分析失败：' + (err.response?.data?.detail || err.message))
    } finally {
        loading.value = false
    }
}

watch(visible, (val) => {
    if (val) fetchReport()
})

const handleDaysChange = () => fetchReport()

const scoreTagType = (score) => {
    if (score >= 60) return 'danger'
    if (score >= 30) return 'warning'
    return 'info'
}

const passRateColor = (rate) => {
    if (rate >= 90) return chartColors.success
    if (rate >= 60) return chartColors.warning
    return chartColors.danger
}

const formatTime = (time) => (time ? dayjs(time).format('MM-DD HH:mm') : '-')

// 去掉步骤名里的 "[用例] " 前缀展示为 用例 / 步骤 两行
const parseStepName = (name) => {
    const match = String(name || '').match(/^\[(.*?)\]\s*(.*)$/)
    if (match) return { caseName: match[1], stepDesc: match[2] }
    return { caseName: '', stepDesc: String(name || '') }
}
</script>

<template>
    <el-drawer
        v-model="visible"
        title="稳定性分析（Flaky Top）"
        size="min(960px, 100vw)"
        destroy-on-close
    >
        <el-alert v-if="loadError" :title="loadError" type="error" :closable="false"><el-button link @click="fetchReport()">重新加载</el-button></el-alert>
        <div class="flaky-toolbar">
            <span class="flaky-hint">
                统计近 N 天已完结执行（不含终止），按"状态翻转率 + 失败率接近 50%"加权评分，样本 &lt; {{ report?.min_samples || 5 }} 次的场景不参与排名。
            </span>
            <el-radio-group v-model="days" size="small" @change="handleDaysChange">
                <el-radio-button :value="7">近 7 天</el-radio-button>
                <el-radio-button :value="30">近 30 天</el-radio-button>
                <el-radio-button :value="90">近 90 天</el-radio-button>
            </el-radio-group>
        </div>

        <div v-loading="loading">
            <h4 class="flaky-section-title">不稳定场景 Top</h4>
            <el-table
                v-if="report?.items?.length"
                :data="report.items"
                size="small"
            >
                <el-table-column type="index" label="#" width="46" align="center" />
                <el-table-column prop="scenario_name" label="场景" min-width="180" show-overflow-tooltip />
                <el-table-column label="执行次数" width="90" align="center">
                    <template #default="{ row }">{{ row.total }}</template>
                </el-table-column>
                <el-table-column label="通过率" width="150">
                    <template #default="{ row }">
                        <el-progress
                            :percentage="row.pass_rate"
                            :stroke-width="10"
                            :color="passRateColor(row.pass_rate)"
                        />
                    </template>
                </el-table-column>
                <el-table-column label="翻转次数" width="90" align="center">
                    <template #default="{ row }">
                        <span :class="{ 'flaky-flips': row.flip_count > 0 }">{{ row.flip_count }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="Flaky 分数" width="110" align="center">
                    <template #default="{ row }">
                        <el-tag :type="scoreTagType(row.score)" effect="dark" size="small">{{ row.score }}</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="最近状态" width="100" align="center">
                    <template #default="{ row }">
                        <el-tag :type="runStatusTagType(row.last_status)" size="small" effect="plain">
                            {{ runStatusLabel(row.last_status) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="最近执行" width="110" align="center">
                    <template #default="{ row }">{{ formatTime(row.last_time) }}</template>
                </el-table-column>
            </el-table>
            <el-empty v-else-if="!loading && !loadError" description="当前窗口内未发现不稳定场景" :image-size="80" />

            <template v-if="report?.step_items?.length">
                <el-divider />
                <h4 class="flaky-section-title">时好时坏的步骤 Top</h4>
                <el-table
                    :data="report.step_items"
                    size="small"
                >
                    <el-table-column type="index" label="#" width="46" align="center" />
                    <el-table-column prop="scenario_name" label="场景" min-width="130" show-overflow-tooltip />
                    <el-table-column label="步骤" min-width="200" show-overflow-tooltip>
                        <template #default="{ row }">
                            <span v-if="parseStepName(row.step_name).caseName" class="flaky-case-name">
                                [{{ parseStepName(row.step_name).caseName }}]
                            </span>
                            {{ parseStepName(row.step_name).stepDesc }}
                        </template>
                    </el-table-column>
                    <el-table-column label="出现次数" width="90" align="center">
                        <template #default="{ row }">{{ row.total }}</template>
                    </el-table-column>
                    <el-table-column label="通过 / 失败" width="100" align="center">
                        <template #default="{ row }">
                            <span class="flaky-pass">{{ row.pass_count }}</span>
                            /
                            <span class="flaky-fail">{{ row.fail_count }}</span>
                        </template>
                    </el-table-column>
                    <el-table-column label="翻转次数" width="90" align="center">
                        <template #default="{ row }">{{ row.flip_count }}</template>
                    </el-table-column>
                    <el-table-column label="Flaky 分数" width="110" align="center">
                        <template #default="{ row }">
                            <el-tag :type="scoreTagType(row.score)" effect="dark" size="small">{{ row.score }}</el-tag>
                        </template>
                    </el-table-column>
                </el-table>
            </template>
        </div>
    </el-drawer>
</template>

<style scoped>
.flaky-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 16px;
}

.flaky-hint {
    font-size: 12px;
    color: var(--ad-muted);
    line-height: 1.6;
}

.flaky-section-title {
    margin: 0 0 10px;
    font-size: 13px;
    color: var(--ad-text);
}

.flaky-flips {
    color: var(--ad-warning);
    font-weight: 600;
}

.flaky-case-name {
    color: var(--ad-muted);
    font-size: 12px;
    margin-right: 4px;
}

.flaky-pass { color: var(--ad-success); font-weight: 600; }
.flaky-fail { color: var(--ad-danger); font-weight: 600; }

@media (max-width: 767px) {
  :deep(.el-button), :deep(.el-radio-button__inner), :deep(.el-select__wrapper), :deep(.el-collapse-item__header) { min-height: 44px; }
  :deep(.el-input__inner), :deep(.el-textarea__inner) { font-size: 16px; }
  :deep(.el-form-item__label), :deep(.el-table), :deep(.el-descriptions), :deep(.el-tabs__item), :deep(.el-collapse-item__content) { font-size: 14px; }
  :deep(.el-table__cell) { font-size: 14px; }
}
</style>
