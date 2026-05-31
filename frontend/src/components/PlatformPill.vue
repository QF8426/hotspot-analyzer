<template>
  <span class="platform-pill" :class="`platform-pill--${meta.accent}`">
    <span class="platform-pill__mark">{{ meta.glyph }}</span>
    <span class="platform-pill__text">{{ label || meta.label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { getPlatformMeta } from '../utils/hotspot'

const props = defineProps({
  platform: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: ''
  }
})

const meta = computed(() => getPlatformMeta(props.platform))
</script>

<style scoped>
.platform-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 11px 6px 7px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  background: rgba(226, 236, 255, 0.86);
  border: 1px solid rgba(135, 160, 206, 0.16);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.46);
}

.platform-pill__mark {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.platform-pill__text {
  line-height: 1;
}

.platform-pill--weibo {
  color: #c93d4f;
  background: linear-gradient(135deg, rgba(255, 242, 243, 0.95), rgba(255, 248, 239, 0.94));
}

.platform-pill--weibo .platform-pill__mark {
  background: linear-gradient(135deg, #ef4444, #f97316);
}

.platform-pill--douyin {
  color: #0f172a;
  background: linear-gradient(135deg, rgba(239, 243, 248, 0.96), rgba(230, 245, 246, 0.94));
}

.platform-pill--douyin .platform-pill__mark {
  background: linear-gradient(135deg, #111827, #0f766e);
}

.platform-pill--bilibili {
  color: #0f7cc0;
  background: linear-gradient(135deg, rgba(236, 247, 255, 0.96), rgba(239, 241, 255, 0.94));
}

.platform-pill--bilibili .platform-pill__mark {
  background: linear-gradient(135deg, #38bdf8, #6366f1);
}
</style>
