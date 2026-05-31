<template>
  <header class="app-header">
    <div class="app-container app-header__inner">
      <button class="app-brand" type="button" @click="goHome">
        <span class="app-brand__mark">HA</span>
        <span class="app-brand__copy">
          <strong>跨平台热点聚合分析器</strong>
          <small>Spring Boot · Vue 3 · Weibo / Douyin / Bilibili</small>
        </span>
      </button>

      <nav class="app-nav" aria-label="主导航">
        <button class="app-nav__item" :class="{ active: isHome }" type="button" @click="goHome">
          首页
        </button>
        <button
          class="app-nav__item"
          :class="{ active: isCrossPlatform }"
          type="button"
          @click="goCrossPlatform"
        >
          跨平台热点
        </button>
        <button
          class="app-nav__item"
          :class="{ active: isHistory }"
          type="button"
          @click="goHistory"
        >
          历史榜单
        </button>

        <el-dropdown trigger="click" @command="handlePlatformCommand">
          <button class="app-nav__item app-nav__item--dropdown" :class="{ active: isPlatform }" type="button">
            平台榜单
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="platform in platforms"
                :key="platform.key"
                :command="platform.key"
              >
                {{ platform.label }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>

      <div class="app-header__status">
        <span class="status-dot"></span>
        <span>统一展示热榜、趋势与 AI 分析</span>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { PLATFORM_ORDER, getPlatformMeta } from '../utils/hotspot'

const route = useRoute()
const router = useRouter()

const platforms = PLATFORM_ORDER.map(key => getPlatformMeta(key))

const isHome = computed(() => route.name === 'home')
const isCrossPlatform = computed(() => String(route.path || '').startsWith('/cross-platform'))
const isHistory = computed(() => route.name === 'history')
const isPlatform = computed(() => route.name === 'platform')

function goHome() {
  router.push({ name: 'home' })
}

function goCrossPlatform() {
  router.push({ name: 'crossPlatform' })
}

function goHistory() {
  router.push({ name: 'history' })
}

function handlePlatformCommand(platform) {
  router.push({
    name: 'platform',
    params: { platform },
    query: { mode: 'current' }
  })
}
</script>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 30;
  backdrop-filter: blur(20px);
  background: linear-gradient(180deg, rgba(245, 249, 255, 0.88), rgba(245, 249, 255, 0.72));
  border-bottom: 1px solid rgba(140, 167, 214, 0.14);
}

.app-header::after {
  content: '';
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(79, 112, 181, 0.18), transparent);
}

.app-header__inner {
  min-height: 78px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-top: 14px;
  padding-bottom: 14px;
}

.app-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
  color: inherit;
}

.app-brand__mark {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #fff;
  background: linear-gradient(135deg, #2f6bff, #28b8ff);
  box-shadow:
    0 14px 32px rgba(47, 107, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.26);
}

.app-brand__copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.app-brand__copy strong {
  font-size: 18px;
  line-height: 1.1;
}

.app-brand__copy small {
  color: var(--text-secondary);
  font-size: 12px;
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow:
    inset 0 0 0 1px rgba(140, 167, 214, 0.14),
    0 10px 28px rgba(30, 64, 132, 0.06);
}

.app-nav__item {
  position: relative;
  border: 0;
  padding: 10px 16px;
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease;
}

.app-nav__item::after {
  content: '';
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 6px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, #2f6bff, #28b8ff);
  opacity: 0;
  transform: scaleX(0.6);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.app-nav__item:hover,
.app-nav__item.active {
  color: var(--text-primary);
  background: linear-gradient(135deg, rgba(47, 107, 255, 0.08), rgba(40, 184, 255, 0.06));
}

.app-nav__item:hover::after,
.app-nav__item.active::after {
  opacity: 1;
  transform: scaleX(1);
}

.app-nav__item--dropdown {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.app-header__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: 13px;
  background:
    radial-gradient(circle at left center, rgba(34, 197, 94, 0.1), transparent 36%),
    rgba(255, 255, 255, 0.76);
  box-shadow: inset 0 0 0 1px rgba(140, 167, 214, 0.14);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.12);
}

@media (max-width: 1080px) {
  .app-header__inner {
    flex-wrap: wrap;
  }

  .app-nav {
    order: 3;
    width: 100%;
    overflow-x: auto;
  }

  .app-header__status {
    margin-left: auto;
  }
}

@media (max-width: 720px) {
  .app-brand__copy strong {
    font-size: 16px;
  }

  .app-header__status {
    width: 100%;
    justify-content: center;
  }
}
</style>
