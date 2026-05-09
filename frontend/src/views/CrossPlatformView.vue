<template>
  <div class="cross-page-shell">
    <header class="top-bar">
      <div class="brand" @click="goHome">
        <div class="brand-logo">↗</div>
        <div>
          <div class="brand-title">跨平台热点聚合分析器</div>
          <div class="brand-subtitle">Weibo · Douyin · Bilibili Intelligence</div>
        </div>
      </div>

      <nav class="nav-tabs">
        <button class="nav-tab" @click="goHome">首页</button>
        <button class="nav-tab active" @click="reload">跨平台热点</button>
        <button class="nav-tab" @click="goHistory">历史榜单</button>
      </nav>

      <div class="sync-status">
        <span class="status-dot"></span>
        <span>已接入联合热点主题表</span>
      </div>
    </header>

    <main class="cross-page">
      <section class="page-hero">
        <div>
          <div class="eyebrow">Cross-platform Hotspot Collection</div>
          <h1>跨平台热点合集</h1>
          <p>
            基于 cross_platform_topic 与 cross_platform_topic_hotspot 表展示系统识别出的多平台共同热点，
            帮助观察同一事件在微博、抖音、B站中的传播情况。
          </p>
        </div>
        <div class="hero-stat-card">
          <div class="hero-stat-label">当前热点组</div>
          <div class="hero-stat-value">{{ topics.length }}</div>
          <div class="hero-stat-tip">来自后端联合热点接口</div>
        </div>
      </section>

      <section class="filter-card">
        <div class="filter-left">
          <span class="filter-title">平台组合</span>
          <div class="filter-tabs">
            <button
              v-for="option in filterOptions"
              :key="option.key"
              class="filter-tab"
              :class="{ active: activeFilter === option.key }"
              @click="changeFilter(option.key)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="filter-right">
          <span class="filter-title">显示数量</span>
          <select v-model.number="limit" class="sort-select" @change="reload">
            <option :value="30">30 组</option>
            <option :value="50">50 组</option>
            <option :value="100">100 组</option>
          </select>
        </div>
      </section>

      <section class="summary-row">
        <article class="summary-card">
          <span class="summary-icon blue">▥</span>
          <div>
            <div class="summary-label">联合热点组</div>
            <div class="summary-value">{{ topics.length }}</div>
          </div>
        </article>
        <article class="summary-card">
          <span class="summary-icon purple">✣</span>
          <div>
            <div class="summary-label">三平台共同</div>
            <div class="summary-value">{{ threePlatformCount }}</div>
          </div>
        </article>
        <article class="summary-card">
          <span class="summary-icon orange">🔥</span>
          <div>
            <div class="summary-label">最高关联平台数</div>
            <div class="summary-value">{{ maxPlatformCount }}</div>
          </div>
        </article>
      </section>

      <section v-loading="loading" class="group-list">
        <template v-if="topics.length > 0">
          <article
            v-for="(topic, index) in topics"
            :key="topic.id"
            class="group-card"
            @click="goTopicDetail(topic)"
          >
            <div class="group-rank">{{ index + 1 }}</div>

            <div class="group-main">
              <div class="group-head">
                <h2>{{ cleanTitle(topic.mainTitle) }}</h2>
                <span class="analysis-tag">跨平台分析</span>
              </div>

              <div class="platform-badges">
                <span
                  v-for="platform in getTopicPlatforms(topic)"
                  :key="platform"
                  class="platform-badge"
                  :class="platform"
                >
                  {{ getPlatformName(platform) }}
                </span>
              </div>

              <p class="group-summary">
                {{ buildSummary(topic) }}
              </p>

              <div class="source-list">
                <div
                  v-for="item in (topic.hotspots || []).slice(0, 3)"
                  :key="`${topic.id}-${item.hotspotId}`"
                  class="source-item"
                  @click.stop="goDetail(item.hotspotId)"
                >
                  <span class="source-platform">{{ getPlatformName(item.platform) }}</span>
                  <span class="source-title">{{ cleanTitle(item.title) }}</span>
                  <span class="source-heat">{{ formatHotValue(item.hotValue) }}</span>
                </div>
              </div>
            </div>

            <div class="group-side">
              <div class="side-label">关联平台</div>
              <div class="side-value">{{ topic.platformCount || getTopicPlatforms(topic).length }}</div>
              <button class="detail-button" @click.stop="goTopicDetail(topic)">
                查看联合分析
              </button>
            </div>
          </article>
        </template>

        <el-empty
          v-else
          description="暂无跨平台热点数据，请先运行跨平台扫描和 AI worker"
        />
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCrossPlatformTopics } from '../api/hotspot'

const router = useRouter()

const filterOptions = [
  { key: 'all', label: '全部' },
  { key: 'weibo,douyin', label: '微博 + 抖音' },
  { key: 'weibo,bilibili', label: '微博 + B站' },
  { key: 'douyin,bilibili', label: '抖音 + B站' },
  { key: 'three', label: '三平台共同' }
]

const topics = ref([])
const loading = ref(false)
const activeFilter = ref('all')
const limit = ref(50)

const threePlatformCount = computed(() =>
  topics.value.filter(topic => (topic.platformCount || getTopicPlatforms(topic).length) >= 3).length
)

const maxPlatformCount = computed(() => {
  if (!topics.value.length) return 0
  return Math.max(...topics.value.map(topic => topic.platformCount || getTopicPlatforms(topic).length || 0))
})

async function reload() {
  loading.value = true
  try {
    const params = { limit: limit.value }
    if (activeFilter.value !== 'all') {
      params.platformCombo = activeFilter.value
    }
    topics.value = await getCrossPlatformTopics(params)
  } finally {
    loading.value = false
  }
}

function changeFilter(key) {
  activeFilter.value = key
  reload()
}

function getTopicPlatforms(topic) {
  if (topic.relatedPlatforms) {
    return topic.relatedPlatforms
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)
  }

  const set = new Set()
  ;(topic.hotspots || []).forEach(item => {
    if (item.platform) set.add(item.platform)
  })
  return Array.from(set)
}

function buildSummary(topic) {
  const text = (topic.summary || '').replace(/\s+/g, ' ').trim()
  if (text) return text.length > 150 ? `${text.slice(0, 150)}...` : text

  const platforms = getTopicPlatforms(topic).map(getPlatformName).join('、')
  return `该热点被识别为跨平台共同话题，已关联 ${platforms || '多个平台'} 的相关热点。系统后续可继续补充联合简介和平台差异分析。`
}

function goTopicDetail(topic) {
  const primary = (topic.hotspots || []).find(item => item.primary) || (topic.hotspots || [])[0]
  if (primary?.hotspotId) {
    router.push(`/detail/${primary.hotspotId}`)
  }
}

function goDetail(id) {
  if (!id) return
  router.push(`/detail/${id}`)
}

function goHome() {
  router.push('/')
}

function goHistory() {
  router.push('/platform/weibo?mode=history')
}

function cleanTitle(title) {
  return String(title || '').replace(/^#+|#+$/g, '')
}

function getPlatformName(platform) {
  const map = {
    weibo: '微博',
    douyin: '抖音',
    bilibili: 'B站'
  }
  return map[platform] || platform || '未知平台'
}

function formatHotValue(value) {
  const num = Number(value || 0)
  if (!num) return '—'
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)}亿`
  if (num >= 10000) return `${(num / 10000).toFixed(1)}万`
  return String(num)
}

onMounted(reload)
</script>

<style scoped>
.cross-page-shell {
  min-height: 100vh;
  background: linear-gradient(180deg, #f7f9ff 0%, #eef3ff 42%, #f8fafc 100%);
  color: #18233f;
}

.top-bar {
  height: 64px;
  padding: 0 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.86);
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  backdrop-filter: blur(18px);
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.brand-logo {
  width: 38px;
  height: 38px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 900;
  background: linear-gradient(135deg, #3b82f6, #7c3aed);
  box-shadow: 0 10px 24px rgba(59, 130, 246, 0.24);
}

.brand-title {
  font-size: 17px;
  font-weight: 800;
}

.brand-subtitle {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}

.nav-tabs {
  display: flex;
  gap: 10px;
  padding: 5px;
  border-radius: 999px;
  background: rgba(241, 245, 249, 0.92);
}

.nav-tab {
  border: 0;
  padding: 9px 16px;
  border-radius: 999px;
  background: transparent;
  color: #64748b;
  font-weight: 700;
  cursor: pointer;
}

.nav-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
}

.sync-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.12);
}

.cross-page {
  width: min(1240px, calc(100% - 48px));
  margin: 0 auto;
  padding: 24px 0 50px;
}

.page-hero {
  min-height: 150px;
  padding: 26px 30px;
  border-radius: 28px;
  display: flex;
  justify-content: space-between;
  gap: 28px;
  background:
    radial-gradient(circle at 85% 20%, rgba(124, 58, 237, 0.16), transparent 28%),
    linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-hero h1 {
  margin: 10px 0 8px;
  font-size: 36px;
  line-height: 1.15;
  letter-spacing: -0.04em;
}

.page-hero p {
  width: min(680px, 100%);
  margin: 0;
  color: #64748b;
  line-height: 1.7;
  font-size: 15px;
}

.hero-stat-card {
  min-width: 190px;
  padding: 22px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
}

.hero-stat-label,
.summary-label,
.side-label {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.hero-stat-value {
  margin-top: 8px;
  font-size: 38px;
  font-weight: 900;
  color: #2563eb;
}

.hero-stat-tip {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}

.filter-card,
.summary-row,
.group-card {
  margin-top: 18px;
}

.filter-card {
  padding: 16px 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.05);
}

.filter-left,
.filter-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-title {
  white-space: nowrap;
  color: #475569;
  font-size: 14px;
  font-weight: 800;
}

.filter-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-tab {
  border: 0;
  padding: 8px 13px;
  border-radius: 999px;
  color: #64748b;
  background: #f1f5f9;
  font-weight: 700;
  cursor: pointer;
}

.filter-tab.active {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
}

.sort-select {
  height: 34px;
  border-radius: 999px;
  padding: 0 12px;
  border: 1px solid #dbe4f0;
  color: #475569;
  font-weight: 700;
  outline: none;
  background: #fff;
}

.summary-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.summary-card {
  min-height: 82px;
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.05);
  display: flex;
  align-items: center;
  gap: 14px;
}

.summary-icon {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 15px;
  font-size: 18px;
}

.summary-icon.blue { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
.summary-icon.purple { background: rgba(124, 58, 237, 0.12); color: #7c3aed; }
.summary-icon.orange { background: rgba(245, 158, 11, 0.14); color: #d97706; }

.summary-value {
  margin-top: 4px;
  color: #0f172a;
  font-size: 24px;
  font-weight: 900;
}

.group-list {
  margin-top: 8px;
}

.group-card {
  position: relative;
  padding: 22px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.06);
  display: grid;
  grid-template-columns: 48px 1fr 160px;
  gap: 18px;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}

.group-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 54px rgba(37, 99, 235, 0.12);
}

.group-rank {
  width: 42px;
  height: 42px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 900;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
}

.group-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.group-head h2 {
  margin: 0;
  font-size: 20px;
  color: #0f172a;
}

.analysis-tag {
  padding: 5px 9px;
  border-radius: 999px;
  color: #6d28d9;
  background: rgba(124, 58, 237, 0.1);
  font-size: 12px;
  font-weight: 800;
}

.platform-badges {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platform-badge {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  background: #f1f5f9;
  color: #475569;
}

.platform-badge.weibo { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.platform-badge.douyin { background: rgba(15, 23, 42, 0.1); color: #0f172a; }
.platform-badge.bilibili { background: rgba(14, 165, 233, 0.12); color: #0284c7; }

.group-summary {
  margin: 12px 0 0;
  color: #64748b;
  line-height: 1.7;
  font-size: 14px;
}

.source-list {
  margin-top: 14px;
  display: grid;
  gap: 8px;
}

.source-item {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 14px;
  display: grid;
  grid-template-columns: 62px 1fr 88px;
  gap: 8px;
  align-items: center;
  background: #f8fafc;
}

.source-platform {
  font-size: 12px;
  font-weight: 900;
  color: #2563eb;
}

.source-title {
  min-width: 0;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-heat {
  text-align: right;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 800;
}

.group-side {
  border-left: 1px solid rgba(148, 163, 184, 0.16);
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 12px;
}

.side-value {
  color: #0f172a;
  font-size: 28px;
  font-weight: 900;
}

.detail-button {
  border: 0;
  padding: 9px 14px;
  border-radius: 999px;
  color: #fff;
  font-weight: 800;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  cursor: pointer;
}

@media (max-width: 980px) {
  .top-bar,
  .filter-card,
  .page-hero {
    flex-direction: column;
    height: auto;
    align-items: flex-start;
  }

  .summary-row,
  .group-card {
    grid-template-columns: 1fr;
  }

  .group-side {
    border-left: 0;
    border-top: 1px solid rgba(148, 163, 184, 0.16);
    padding-left: 0;
    padding-top: 14px;
  }
}
</style>
