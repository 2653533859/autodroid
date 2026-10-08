<script setup>
import dayjs from 'dayjs'
defineProps({ asset: { type: Object, default: () => ({}) } })
const time = value => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'
</script>
<template>
  <div class="asset-metadata ad-metadata">
    <span>归属：团队共享</span>
    <template v-if="asset.id">
      <span>ID：{{ asset.id }}</span><span>创建人：{{ asset.creator_name || '-' }}</span>
      <span>创建时间：{{ time(asset.created_at) }}</span>
      <span>最后更新：{{ asset.updater_name || '-' }} · {{ time(asset.updated_at) }}</span>
    </template>
    <el-tooltip content="团队成员可查看和编辑；仅创建人或管理员可删除" placement="top"><el-button link size="small" aria-label="权限说明：团队成员可查看和编辑；仅创建人或管理员可删除">权限说明</el-button></el-tooltip>
  </div>
</template>
<style scoped>.asset-metadata{display:flex;gap:8px 20px;flex-wrap:wrap;align-items:center;color:var(--el-text-color-secondary);font-size:12px;line-height:22px}@media(max-width:760px){.asset-metadata{font-size:14px}}</style>
