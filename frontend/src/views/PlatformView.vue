<template>
  <div class="platform-page">
    <!-- 顶部导航：先写在页面内，后续可再抽成组件 -->
    <header class="app-header">
      <div class="brand" @click="goHome">
        <div class="brand-logo">
          <span class="logo-wave">↗</span>
        </div>
        <div>
          <div class="brand-title">跨平台热点聚合分析器</div>
          <div class="brand-subtitle">Weibo · Douyin · Bilibili Intelligence</div>
        </div>
      </div>

      <nav class="nav-menu">
        <button class="nav-item" @click="goHome">⌂ 首页</button>
        <button class="nav-item" @click="goCrossPlatform">▥ 跨平台热点</button>
        <button class="nav-item active">◴ 历史榜单</button>
      </nav>

      <div class="header-search">
        <el-input
          v-model="keyword"
          placeholder="搜索热点关键词、事件或话题..."
          :prefix-icon="Search"
          clearable
          @keyup.enter="handleSearch"
        />
      </div>
    </header>

    <main class="page-shell">
      <!-- 平台头部区 -->
      <section class="hero-panel">
        <div class="platform-mark" :class="platformClass">
          <span>{{ platformIcon }}</span>
        </div>

        <div class="hero-main">
          <h1>{{ platformLabel }}热点榜单</h1>
          <p>{{ pageDesc }}</p>

          <div class="hero-metas">
            <span class="meta-pill">🔥 当前榜单 {{ currentNormalCount }} 条</span>
            <span class="meta-pill">📈 今日出现 {{ todayCountText }} 条</span>
          </div>
        </div>

        <div class="hero-illustration">
          <div class="soft-card">
            <div class="bar bar-1"></div>
            <div class="bar bar-2"></div>
            <div class="bar bar-3"></div>
            <div class="flame">🔥</div>
          </div>
        </div>

        <div class="platform-switch">
          <div class="switch-label">切换平台</div>
          <div class="switch-buttons">
            <button
              v-for="item in platformOptions"
              :key="item.value"
              class="platform-button"
              :class="{ active: platform === item.value }"
              @click="switchPlatform(item.value)"
            >
              <span>{{ item.icon }}</span>
              {{ item.label }}
            </button>
          </div>
        </div>
      </section>

      <!-- 主内容区 -->
      <section class="content-panel" v-loading="loading">
        <div class="control-row">
          <div class="mode-tabs">
            <button
              class="mode-tab"
              :class="{ active: mode === 'current' }"
              @click="setMode('current')"
            >
              当前榜单
            </button>
            <button
              class="mode-tab"
              :class="{ active: mode === 'daily' }"
              @click="setMode('daily')"
            >
              今日榜单
            </button>
          </div>

          <div v-if="mode === 'daily'" class="daily-tools">
            <el-date-picker
              v-model="selectedDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              :clearable="false"
            />
            <el-button type="primary" @click="loadDailyAndReset">查询</el-button>
          </div>
        </div>

        <!-- 当前榜单 -->
        <template v-if="mode === 'current'">
          <section v-if="specialHotspots.length" class="special-section">
            <div class="section-heading">
              <span class="section-icon">♛</span>
              平台置顶 / 特殊展示
            </div>

            <div
              v-for="item in specialHotspots"
              :key="'special-' + item.id"
              class="special-row"
              @click="goDetail(item.id)"
            >
              <span class="special-badge">置顶</span>
              <strong>{{ cleanTitle(item.title) }}</strong>
              <span class="special-desc">平台特殊展示，不参与普通排名</span>
              <span class="detail-link">查看详情 ›</span>
            </div>
          </section>

          <section class="list-section">
            <div class="list-title-row">
              <h2>当前热点榜单</h2>
              <span>按平台最新榜单排名展示，每页 {{ pageSize }} 条</span>
            </div>

            <div class="ranking-list">
              <div
                v-for="item in pagedCurrentNormal"
                :key="item.id"
                class="ranking-row"
                @click="goDetail(item.id)"
              >
                <div class="rank-badge" :class="rankClass(item.rankNum)">
                  {{ item.rankNum ?? '-' }}
                </div>

                <div class="row-title-area">
                  <div class="hot-title">
                    {{ cleanTitle(item.title) }}
                    <span
                      v-if="normalizeTag(item.tags, item.title) !== '无'"
                      class="tag-chip"
                    >
                      {{ normalizeTag(item.tags, item.title) }}
                    </span>
                  </div>
                </div>

                <div class="row-metric">
                  <span class="metric-icon">🔥</span>
                  当前热度：<strong>{{ formatHotValue(item.hotValue) }}</strong>
                </div>

                <div class="row-metric rank-metric">
                  <span class="metric-icon">▥</span>
                  平台排名：<strong>{{ item.rankNum ?? '暂无' }}</strong>
                </div>

                <div class="detail-link">查看详情 ›</div>
              </div>
            </div>

            <el-empty
              v-if="!loading && !specialHotspots.length && !normalHotspots.length"
              description="暂无当前榜单数据"
            />

            <div v-if="normalHotspots.length > pageSize" class="pagination-wrap">
              <el-pagination
                v-model:current-page="currentPage"
                :page-size="pageSize"
                layout="total, prev, pager, next, jumper"
                :total="normalHotspots.length"
                background
              />
            </div>
          </section>
        </template>

        <!-- 今日/指定日期榜单 -->
        <template v-else>
          <section v-if="!isSelectedToday && dailySpecial.length" class="special-section">
            <div class="section-heading">
              <span class="section-icon">♛</span>
              平台置顶 / 特殊展示
            </div>

            <div
              v-for="item in dailySpecial"
              :key="'daily-special-' + getItemId(item)"
              class="special-row"
              @click="goDetail(getItemId(item))"
            >
              <span class="special-badge">置顶</span>
              <strong>{{ cleanTitle(item.title) }}</strong>
              <span class="special-desc">平台特殊展示，不参与普通排名</span>
              <span class="detail-link">查看详情 ›</span>
            </div>
          </section>

          <section class="list-section">
            <div class="list-title-row">
              <h2>{{ dailyTitle }}</h2>
              <span>按当日最高热度排序，每页 {{ pageSize }} 条</span>
            </div>

            <div class="ranking-list">
              <div
                v-for="(item, index) in pagedDailyNormal"
                :key="'daily-' + getItemId(item)"
                class="ranking-row"
                @click="goDetail(getItemId(item))"
              >
                <div class="rank-badge" :class="rankClass(getDailyRank(index))">
                  {{ getDailyRank(index) }}
                </div>

                <div class="row-title-area">
                  <div class="hot-title">
                    {{ cleanTitle(item.title) }}
                    <span
                      v-if="normalizeTag(item.tags, item.title) !== '无'"
                      class="tag-chip"
                    >
                      {{ normalizeTag(item.tags, item.title) }}
                    </span>
                  </div>
                </div>

                <div class="row-metric">
                  <span class="metric-icon">🔥</span>
                  {{ isSelectedToday ? '今日最高热度' : '当日最高热度' }}：
                  <strong>{{ formatHotValue(item.maxHotValue) }}</strong>
                </div>

                <div class="row-metric rank-metric">
                  <span class="metric-icon">▥</span>
                  最佳排名：<strong>{{ item.bestRankNum ?? '暂无' }}</strong>
                </div>

                <div class="detail-link">查看详情 ›</div>
              </div>
            </div>

            <el-empty
              v-if="!loading && !dailyList.length"
              :description="isSelectedToday ? '暂无今日榜单数据' : '该日期暂无历史榜单数据'"
            />

            <div v-if="dailyNormal.length > pageSize" class="pagination-wrap">
              <el-pagination
                v-model:current-page="dailyPage"
                :page-size="pageSize"
                layout="total, prev, pager, next, jumper"
                :total="dailyNormal.length"
                background
              />
            </div>
          </section>
        </template>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import {
  getHotspotsByPlatform,
  getDailyTop,
  getHistoryHotspots
} from '../api/hotspot'

const route = useRoute()
const router = useRouter()

const platform = ref(route.params.platform || 'weibo')
const mode = ref(route.query.mode || 'current')
const loading = ref(false)
const keyword = ref('')

const hotspots = ref([])
const dailyHotspots = ref([])
const historyHotspots = ref([])
const selectedDate = ref(route.query.date || getToday())

const pageSize = 25
const currentPage = ref(1)
const dailyPage = ref(1)

const platformOptions = [
  { value: 'weibo', label: '微博', icon: '◎' },
  { value: 'douyin', label: '抖音', icon: '♪' },
  { value: 'bilibili', label: 'B站', icon: '▣' }
]

const platformNameMap = {
  weibo: '微博',
  douyin: '抖音',
  bilibili: 'B站',
  baidu: '百度'
}

const platformLabel = computed(() => platformNameMap[platform.value] || platform.value)

const platformIcon = computed(() => {
  const item = platformOptions.find(option => option.value === platform.value)
  return item?.icon || '★'
})

const platformClass = computed(() => `platform-${platform.value}`)

const isSelectedToday = computed(() => selectedDate.value === getToday())

const pageDesc = computed(() => {
  return `追踪${platformLabel.value}平台实时热搜、今日高热话题与历史榜单变化`
})

const dailyTitle = computed(() => {
  if (isSelectedToday.value) return '今日热点榜单'
  return `${selectedDate.value} 历史榜单`
})

const specialHotspots = computed(() =>
  hotspots.value.filter(item => item.isSpecial)
)

const normalHotspots = computed(() =>
  hotspots.value.filter(item => !item.isSpecial)
)

const currentNormalCount = computed(() => normalHotspots.value.length)

const dailyList = computed(() =>
  isSelectedToday.value ? dailyHotspots.value : historyHotspots.value
)

const dailySpecial = computed(() =>
  dailyList.value.filter(item => item.isSpecial)
)

const dailyNormal = computed(() =>
  dailyList.value.filter(item => !item.isSpecial)
)

const todayCountText = computed(() => {
  if (dailyHotspots.value.length > 0) return dailyHotspots.value.length
  if (isSelectedToday.value && mode.value === 'daily') return dailyNormal.value.length
  return '—'
})

const pagedCurrentNormal = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return normalHotspots.value.slice(start, start + pageSize)
})

const pagedDailyNormal = computed(() => {
  const start = (dailyPage.value - 1) * pageSize
  return dailyNormal.value.slice(start, start + pageSize)
})

watch(currentPage, () => {
  scrollToListTop()
})

watch(dailyPage, () => {
  scrollToListTop()
})

function getToday() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function cleanTitle(title) {
  if (!title) return ''
  return String(title).replace(/^#|#$/g, '')
}

function normalizeTag(tag, title = '') {
  if (!tag) return '无'

  let value = Array.isArray(tag) ? tag.join('、') : String(tag)
  value = value.trim()

  if (!value) return '无'
  if (title && cleanTitle(value) === cleanTitle(title)) return '无'

  value = value
    .replace(/^\[/, '')
    .replace(/\]$/, '')
    .replace(/"/g, '')
    .replace(/'/g, '')
    .trim()

  if (!value) return '无'
  if (value.length > 8) return '无'

  return value
}

function formatHotValue(value) {
  if (value === null || value === undefined || value === '') return '暂无'

  const num = Number(value)
  if (Number.isNaN(num)) return String(value)

  if (num >= 100000000) {
    return (num / 100000000).toFixed(1).replace(/\.0$/, '') + '亿'
  }

  if (num >= 10000) {
    return (num / 10000).toFixed(1).replace(/\.0$/, '') + '万'
  }

  return String(num)
}

function getItemId(item) {
  return item.id ?? item.hotspotId ?? item.hotspot_id
}

function getDailyRank(index) {
  return (dailyPage.value - 1) * pageSize + index + 1
}

function rankClass(rank) {
  const num = Number(rank)
  if (num === 1) return 'rank-top rank-one'
  if (num === 2) return 'rank-top rank-two'
  if (num === 3) return 'rank-top rank-three'
  return 'rank-normal'
}

function goHome() {
  router.push('/')
}

function goCrossPlatform() {
  router.push('/cross-platform')
}

function goDetail(id) {
  if (!id) return
  router.push(`/detail/${id}`)
}

function handleSearch() {
  const text = keyword.value.trim()
  if (!text) return
  router.push({ path: '/search', query: { keyword: text } })
}

function scrollToListTop() {
  requestAnimationFrame(() => {
    const target = document.querySelector('.content-panel')
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function switchPlatform(nextPlatform) {
  if (platform.value === nextPlatform) return

  platform.value = nextPlatform
  currentPage.value = 1
  dailyPage.value = 1

  await router.replace({
    path: `/platform/${nextPlatform}`,
    query: mode.value === 'daily'
      ? { mode: mode.value, date: selectedDate.value }
      : { mode: mode.value }
  })

  if (mode.value === 'current') {
    await loadCurrent()
  } else {
    await loadDaily()
  }
}

async function setMode(nextMode) {
  if (mode.value === nextMode) return
  mode.value = nextMode
  currentPage.value = 1
  dailyPage.value = 1

  await router.replace({
    path: `/platform/${platform.value}`,
    query: nextMode === 'daily'
      ? { mode: nextMode, date: selectedDate.value }
      : { mode: nextMode }
  })

  if (nextMode === 'current') {
    await loadCurrent()
  } else {
    await loadDaily()
  }
}

async function loadCurrent() {
  loading.value = true

  try {
    const result = await getHotspotsByPlatform(platform.value)
    hotspots.value = Array.isArray(result) ? result : []
    currentPage.value = 1
  } finally {
    loading.value = false
  }
}

async function loadDailyAndReset() {
  dailyPage.value = 1
  await loadDaily()
}

async function loadDaily() {
  loading.value = true

  try {
    await router.replace({
      path: `/platform/${platform.value}`,
      query: {
        mode: 'daily',
        date: selectedDate.value
      }
    })

    if (isSelectedToday.value) {
      // 当前阶段用较大的 limit 取全量，再在前端按 25 条分页。
      dailyHotspots.value = await getDailyTop(platform.value, 500)
      historyHotspots.value = []
    } else {
      historyHotspots.value = await getHistoryHotspots(platform.value, selectedDate.value)
      dailyHotspots.value = []
    }

    dailyHotspots.value = Array.isArray(dailyHotspots.value) ? dailyHotspots.value : []
    historyHotspots.value = Array.isArray(historyHotspots.value) ? historyHotspots.value : []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!['current', 'daily'].includes(mode.value)) {
    mode.value = 'current'
  }

  if (mode.value === 'current') {
    await loadCurrent()
    // 预取今日榜单数量，用于头部“今日出现”展示，不影响当前榜单分页。
    try {
      const result = await getDailyTop(platform.value, 500)
      dailyHotspots.value = Array.isArray(result) ? result : []
    } catch (error) {
      dailyHotspots.value = []
    }
  } else {
    await loadDaily()
  }
})
</script>

<style scoped>
.platform-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 18%, rgba(64, 126, 255, 0.10), transparent 26%),
    linear-gradient(180deg, #f7faff 0%, #eef4ff 42%, #f8fbff 100%);
  color: #0f1f3a;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 78px;
  padding: 0 36px;
  display: grid;
  grid-template-columns: 360px 1fr 370px;
  align-items: center;
  gap: 24px;
  background: rgba(255, 255, 255, 0.88);
  border-bottom: 1px solid rgba(75, 110, 180, 0.14);
  backdrop-filter: blur(18px);
  box-shadow: 0 8px 28px rgba(28, 71, 140, 0.06);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
}

.brand-logo {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, #2f84ff, #4f6df5);
  box-shadow: 0 10px 24px rgba(47, 109, 255, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 26px;
  font-weight: 900;
}

.logo-wave {
  transform: rotate(-12deg);
}

.brand-title {
  font-size: 20px;
  font-weight: 800;
  color: #111827;
  letter-spacing: 0.5px;
}

.brand-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #75839c;
}

.nav-menu {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 30px;
}

.nav-item {
  position: relative;
  border: none;
  background: transparent;
  padding: 26px 4px 22px;
  font-size: 16px;
  font-weight: 700;
  color: #2b3a55;
  cursor: pointer;
}

.nav-item.active {
  color: #1f63ff;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  border-radius: 99px;
  background: #1f63ff;
}

.header-search :deep(.el-input__wrapper) {
  height: 42px;
  border-radius: 14px;
  box-shadow: 0 0 0 1px rgba(73, 105, 160, 0.16) inset;
}

.page-shell {
  max-width: 1460px;
  margin: 0 auto;
  padding: 42px 28px 64px;
}

.hero-panel {
  position: relative;
  min-height: 220px;
  padding: 34px 42px;
  display: grid;
  grid-template-columns: 92px minmax(360px, 1fr) 320px 420px;
  align-items: center;
  gap: 28px;
  overflow: hidden;
  border-radius: 30px;
  background:
    linear-gradient(120deg, rgba(255, 255, 255, 0.96) 0%, rgba(234, 243, 255, 0.92) 62%, rgba(240, 246, 255, 0.95) 100%);
  box-shadow: 0 22px 50px rgba(43, 88, 170, 0.10);
  border: 1px solid rgba(112, 145, 210, 0.16);
}

.hero-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 72% 10%, rgba(72, 125, 255, 0.16), transparent 26%);
  pointer-events: none;
}

.platform-mark {
  width: 86px;
  height: 86px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  background: #fff;
  box-shadow: 0 14px 28px rgba(58, 94, 160, 0.14);
  font-size: 36px;
  font-weight: 900;
}

.platform-weibo span {
  color: #f04438;
}

.platform-douyin span {
  color: #0f172a;
}

.platform-bilibili span {
  color: #fb5a9d;
}

.hero-main {
  position: relative;
  z-index: 1;
}

.hero-main h1 {
  margin: 0;
  font-size: 42px;
  line-height: 1.15;
  letter-spacing: 0.5px;
  color: #0b1220;
}

.hero-main p {
  margin: 14px 0 0;
  color: #536178;
  font-size: 17px;
}

.hero-metas {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 24px;
}

.meta-pill {
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 0 0 1px rgba(76, 112, 180, 0.12) inset;
  font-weight: 700;
  color: #25344f;
}

.hero-illustration {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
}

.soft-card {
  position: relative;
  width: 170px;
  height: 126px;
  border-radius: 30px;
  background: linear-gradient(145deg, #e8f0ff, #ffffff);
  box-shadow: 0 24px 50px rgba(45, 101, 220, 0.18);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 12px;
  padding: 24px;
}

.bar {
  width: 22px;
  border-radius: 999px 999px 8px 8px;
  background: linear-gradient(180deg, #7d5cff, #2f7dff);
}

.bar-1 { height: 44px; opacity: 0.65; }
.bar-2 { height: 74px; }
.bar-3 { height: 56px; opacity: 0.8; }

.flame {
  position: absolute;
  top: -20px;
  font-size: 42px;
  filter: drop-shadow(0 14px 16px rgba(47, 109, 255, 0.24));
}

.platform-switch {
  position: relative;
  z-index: 1;
}

.switch-label {
  margin-bottom: 12px;
  color: #66728a;
  font-weight: 700;
}

.switch-buttons {
  display: flex;
  gap: 12px;
}

.platform-button {
  min-width: 112px;
  border: 1px solid rgba(84, 119, 180, 0.14);
  background: rgba(255, 255, 255, 0.74);
  border-radius: 16px;
  padding: 13px 18px;
  color: #19243a;
  font-size: 16px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(32, 75, 150, 0.07);
}

.platform-button.active {
  color: #fff;
  background: linear-gradient(135deg, #1f70ff, #3156f6);
  box-shadow: 0 14px 26px rgba(45, 94, 230, 0.28);
}

.content-panel {
  margin-top: 28px;
  padding: 28px 30px 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(111, 140, 190, 0.14);
  box-shadow: 0 20px 45px rgba(43, 88, 170, 0.08);
}

.control-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(105, 132, 180, 0.18);
}

.mode-tabs {
  display: flex;
  gap: 22px;
}

.mode-tab {
  position: relative;
  border: none;
  background: transparent;
  padding: 10px 0 14px;
  font-size: 17px;
  font-weight: 800;
  color: #34435f;
  cursor: pointer;
}

.mode-tab.active {
  color: #1f63ff;
}

.mode-tab.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -19px;
  height: 3px;
  border-radius: 99px;
  background: #1f63ff;
}

.daily-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.daily-tools :deep(.el-input__wrapper) {
  height: 42px;
  border-radius: 12px;
}

.daily-tools :deep(.el-button) {
  height: 42px;
  min-width: 78px;
  border-radius: 12px;
  font-weight: 800;
}

.special-section {
  margin-top: 22px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 0 14px;
  font-size: 19px;
  font-weight: 900;
  color: #111827;
}

.section-icon {
  color: #1f63ff;
}

.special-row {
  display: grid;
  grid-template-columns: auto minmax(180px, auto) 1fr auto;
  align-items: center;
  gap: 20px;
  min-height: 62px;
  padding: 0 20px;
  border-radius: 14px;
  border: 1px dashed rgba(255, 112, 67, 0.32);
  background: linear-gradient(90deg, rgba(255, 246, 240, 0.96), rgba(255, 255, 255, 0.96));
  cursor: pointer;
}

.special-badge {
  padding: 7px 12px;
  border-radius: 9px;
  background: linear-gradient(135deg, #ff7043, #ff5630);
  color: #fff;
  font-size: 14px;
  font-weight: 900;
}

.special-row strong {
  font-size: 18px;
  color: #111827;
}

.special-desc {
  color: #718098;
}

.list-section {
  margin-top: 24px;
}

.list-title-row {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.list-title-row h2 {
  margin: 0;
  font-size: 20px;
  color: #111827;
}

.list-title-row span {
  color: #7a879d;
  font-size: 14px;
}

.ranking-list {
  overflow: hidden;
  border: 1px solid rgba(112, 145, 210, 0.18);
  border-radius: 18px;
  background: #fff;
}

.ranking-row {
  min-height: 64px;
  display: grid;
  grid-template-columns: 62px minmax(260px, 1fr) 250px 210px 110px;
  align-items: center;
  gap: 18px;
  padding: 9px 18px;
  cursor: pointer;
  border-bottom: 1px solid rgba(112, 145, 210, 0.14);
  transition: background 0.18s ease;
}

.ranking-row:last-child {
  border-bottom: none;
}

.ranking-row:hover {
  background: #f7faff;
}

.rank-badge {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 900;
}

.rank-top {
  background: linear-gradient(135deg, #ff3f32, #ff8a1f);
  box-shadow: 0 8px 18px rgba(255, 90, 45, 0.22);
}

.rank-two,
.rank-three {
  background: linear-gradient(135deg, #ff6a2a, #ffb12a);
}

.rank-normal {
  background: linear-gradient(135deg, #2f8cff, #3158f6);
  box-shadow: 0 8px 18px rgba(47, 109, 255, 0.20);
}

.hot-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  font-size: 17px;
  font-weight: 800;
  color: #152033;
}

.tag-chip {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: 8px;
  background: #fff0f0;
  color: #ff4d4f;
  border: 1px solid #ffd6d6;
  font-size: 12px;
  font-weight: 800;
}

.row-metric {
  color: #5f6f89;
  font-size: 14px;
}

.row-metric strong {
  margin-left: 4px;
  color: #172033;
  font-size: 15px;
}

.metric-icon {
  margin-right: 6px;
}

.detail-link {
  color: #1f63ff;
  font-size: 14px;
  font-weight: 800;
  text-align: right;
  white-space: nowrap;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 22px;
}

@media (max-width: 1200px) {
  .app-header {
    grid-template-columns: 320px 1fr;
    height: auto;
    padding: 14px 24px;
  }

  .header-search {
    grid-column: 1 / -1;
  }

  .hero-panel {
    grid-template-columns: 80px 1fr;
  }

  .hero-illustration,
  .platform-switch {
    display: none;
  }

  .ranking-row {
    grid-template-columns: 54px 1fr 180px 90px;
  }

  .rank-metric {
    display: none;
  }
}

@media (max-width: 768px) {
  .app-header {
    grid-template-columns: 1fr;
  }

  .nav-menu {
    justify-content: flex-start;
    gap: 18px;
    overflow-x: auto;
  }

  .hero-panel {
    grid-template-columns: 1fr;
    padding: 28px;
  }

  .platform-mark {
    display: none;
  }

  .hero-main h1 {
    font-size: 32px;
  }

  .control-row,
  .list-title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .ranking-row {
    grid-template-columns: 48px 1fr;
    gap: 10px;
  }

  .row-metric,
  .detail-link {
    grid-column: 2 / -1;
    text-align: left;
  }

  .special-row {
    grid-template-columns: 1fr;
    padding: 16px;
  }
}
</style>
