<script setup>
defineProps({
    label: { type: String, default: '' },
    value: { type: [String, Number], default: '' },
    tone: { type: String, default: '' },
})
</script>

<template>
    <el-card shadow="never" class="stat-card">
        <div class="stat-label">{{ label }}</div>
        <div class="stat-value" :class="tone">
            <slot>{{ value }}</slot>
        </div>
    </el-card>
</template>

<style scoped>
.stat-card {
    flex: 1;
    min-width: 120px;
    text-align: left;
    border-color: var(--ad-border);
    border-radius: var(--ad-panel-radius);
}

.stat-card :deep(.el-card__body) {
    padding: 12px;
}

.stat-label {
    font-size: 12px;
    color: var(--ad-muted);
    margin-bottom: 6px;
}

.stat-value {
    font-size: 18px;
    font-weight: 600;
    color: var(--ad-text);
}

.stat-value.primary { color: var(--ad-primary); }
.stat-value.success { color: var(--ad-success); }
.stat-value.danger { color: var(--ad-danger); }
.stat-value.warning { color: var(--ad-warning); }

@media (max-width: 767px) {
  :deep(.el-button), :deep(.el-radio-button__inner), :deep(.el-select__wrapper), :deep(.el-collapse-item__header) { min-height: 44px; }
  :deep(.el-input__inner), :deep(.el-textarea__inner) { font-size: 16px; }
  :deep(.el-form-item__label), :deep(.el-table), :deep(.el-descriptions), :deep(.el-tabs__item), :deep(.el-collapse-item__content) { font-size: 14px; }
  :deep(.el-table__cell) { font-size: 14px; }
}
</style>
