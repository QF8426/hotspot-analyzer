<template>
  <div class="request-state">
    <div
      v-if="loading"
      class="request-state__panel request-state__panel--loading"
      :class="{ 'request-state__panel--compact': compact }"
    >
      <el-skeleton animated :rows="skeletonRows">
        <template #template>
          <el-skeleton-item variant="h1" style="width: 38%; height: 20px; margin-bottom: 16px" />
          <el-skeleton-item variant="text" style="width: 100%; height: 14px; margin-bottom: 10px" />
          <el-skeleton-item variant="text" style="width: 90%; height: 14px; margin-bottom: 10px" />
          <el-skeleton-item variant="text" style="width: 76%; height: 14px" />
        </template>
      </el-skeleton>
    </div>

    <el-result
      v-else-if="error"
      icon="error"
      :title="errorTitle"
      :sub-title="error"
      class="request-state__panel request-state__panel--result"
      :class="{ 'request-state__panel--compact': compact }"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('retry')">重新加载</el-button>
      </template>
    </el-result>

    <el-empty
      v-else-if="empty"
      :description="emptyDescription"
      class="request-state__panel request-state__panel--empty"
      :class="{ 'request-state__panel--compact': compact }"
    >
      <template v-if="$slots.extra" #default>
        <slot name="extra" />
      </template>
    </el-empty>

    <slot v-else />
  </div>
</template>

<script setup>
defineProps({
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  errorTitle: {
    type: String,
    default: '数据加载失败'
  },
  empty: {
    type: Boolean,
    default: false
  },
  emptyDescription: {
    type: String,
    default: '暂无数据'
  },
  skeletonRows: {
    type: Number,
    default: 4
  },
  compact: {
    type: Boolean,
    default: false
  }
})

defineEmits(['retry'])
</script>

<style scoped>
.request-state__panel {
  min-height: 176px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 20px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(47, 107, 255, 0.05), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(247, 250, 255, 0.88));
  border: 1px solid rgba(135, 160, 206, 0.12);
}

.request-state__panel--compact {
  min-height: 116px;
  padding: 18px 14px;
  border-radius: 18px;
}

.request-state__panel--loading {
  align-items: stretch;
  justify-content: stretch;
}

.request-state__panel--empty {
  background:
    radial-gradient(circle at top right, rgba(47, 107, 255, 0.04), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(248, 251, 255, 0.8));
}

.request-state__panel :deep(.el-result__title) {
  margin-top: 4px;
}

.request-state__panel :deep(.el-result__title p) {
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 800;
}

.request-state__panel :deep(.el-result__subtitle p),
.request-state__panel :deep(.el-empty__description p) {
  color: var(--text-secondary);
  line-height: 1.7;
}

.request-state__panel :deep(.el-result__icon),
.request-state__panel :deep(.el-empty__image) {
  margin-bottom: 12px;
}

.request-state__panel--compact :deep(.el-result__icon svg) {
  width: 44px;
  height: 44px;
}

.request-state__panel--compact :deep(.el-empty__image) {
  width: 68px;
}

.request-state__panel--compact :deep(.el-result__title p) {
  font-size: 16px;
}
</style>
