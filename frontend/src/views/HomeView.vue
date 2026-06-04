<template>
  <div class="app-container page-stack">
    <section class="page-hero home-hero">
      <div class="home-hero__content">
        <span class="page-hero__eyebrow">热点观察工作台</span>
        <h1 class="page-hero__title">跨平台热点观察台</h1>
        <p class="page-hero__subtitle">
          聚合微博、抖音、B站热点内容，展示趋势变化与热点解读，帮助用户快速了解正在传播的重要事件。
        </p>

        <div class="home-hero__search">
          <el-input
            v-model="keyword"
            clearable
            size="large"
            placeholder="搜索热点关键词、事件名称或主题"
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button type="primary" @click="handleSearch">搜索热点</el-button>
            </template>
          </el-input>
        </div>

        <div class="home-hero__actions">
          <el-button type="primary" @click="goCrossPlatform">查看跨平台热点</el-button>
          <el-button plain @click="goHistory">查看历史榜单</el-button>
        </div>

        <div class="home-hero__chips chip-group">
          <button
            v-for="category in categories"
            :key="category.name"
            type="button"
            class="chip-button home-chip-button"
            :class="{ active: selectedCategory === category.name }"
            @click="handleCategoryClick(category)"
          >
            {{ category.name }}
          </button>
        </div>

        <div class="home-hero__mini-stats">
          <article class="home-hero__mini-stat">
            <span class="home-hero__mini-label">今日热点总数</span>
            <strong>{{ totalTodayCount }}</strong>
            <small>汇总三平台今日热点表现</small>
          </article>

          <article class="home-hero__mini-stat">
            <span class="home-hero__mini-label">跨平台主题数</span>
            <strong>{{ crossTopicCount }}</strong>
            <small>观察多平台共同关注的话题</small>
          </article>
        </div>
      </div>

      <div class="home-hero__aside">
        <div class="home-pipeline">
          <div class="home-pipeline__head">
            <span>系统能力</span>
            <small>实时观察</small>
          </div>

          <div class="home-pipeline__steps">
            <div class="home-pipeline__step">
              <strong>多平台采集</strong>
              <span>同步观察微博、抖音与 B 站热点</span>
            </div>
            <div class="home-pipeline__step">
              <strong>热点解读</strong>
              <span>快速阅读事件摘要与核心信息</span>
            </div>
            <div class="home-pipeline__step">
              <strong>关联分析</strong>
              <span>识别多平台共同升温的话题</span>
            </div>
            <div class="home-pipeline__step">
              <strong>趋势观察</strong>
              <span>查看榜单变化与持续传播情况</span>
            </div>
          </div>

          <p class="home-pipeline__foot">围绕热点发现、聚合与追踪，提供统一的观察入口。</p>
        </div>
      </div>
    </section>

    <RequestState
      :loading="crossLoading"
      :error="crossError"
      :empty="!crossLoading && !crossError && crossPreviewTopics.length === 0"
      empty-description="暂未识别到跨平台共同热点"
      @retry="loadCrossTopics"
    >
      <section class="table-card home-cross-panel">
        <div class="section-head cross-preview-head">
          <div>
            <h2 class="section-title">跨平台热点精选</h2>
            <p class="section-subtitle">聚焦同时在多个平台受到关注的话题，帮助快速发现传播联动。</p>
          </div>
          <el-button type="primary" @click="goCrossPlatform">查看全部主题</el-button>
        </div>

        <div class="cross-preview-carousel-wrap">
          <el-button
            v-if="crossPageCount > 1"
            class="cross-preview-nav cross-preview-nav--prev"
            circle
            :disabled="crossSlideIndex === 0"
            @click.stop="scrollCrossPreview(-1)"
          >
            ‹
          </el-button>

          <div ref="crossScrollerRef" class="cross-preview-carousel">
            <article
              v-for="topic in crossPreviewTopics"
              :key="topic.id"
              class="cross-preview-card cross-preview-card--slide"
              @click="goCrossTopic(topic)"
            >
              <div class="cross-preview-card__head">
                <h3>{{ cleanTitle(topic.mainTitle) }}</h3>
                <el-tag type="primary" size="small" effect="plain">跨平台主题</el-tag>
              </div>

              <div class="cross-preview-card__platforms">
                <PlatformPill
                  v-for="platform in getTopicPlatforms(topic)"
                  :key="platform"
                  :platform="platform"
                />
              </div>

              <p class="cross-preview-card__summary">
                {{ buildSummaryText(topic.summary, '该主题已被系统识别为多平台共同关注的话题，可继续查看详情。', 124) }}
              </p>

              <div class="cross-preview-card__meta">
                <span>关联平台：{{ topic.platformCount || getTopicPlatforms(topic).length }}</span>
                <span>关联热点：{{ topic.hotspotCount || topic.hotspots?.length || 0 }}</span>
                <span>综合指标：{{ formatHotValue(getTopicTotalHotValue(topic)) }}</span>
              </div>
            </article>
          </div>

          <el-button
            v-if="crossPageCount > 1"
            class="cross-preview-nav cross-preview-nav--next"
            circle
            :disabled="crossSlideIndex >= crossPageCount - 1"
            @click.stop="scrollCrossPreview(1)"
          >
            ›
          </el-button>
        </div>
      </section>
    </RequestState>

    <section class="table-card home-board-panel">
      <div class="section-head">
        <div>
          <h2 class="section-title">平台 Top 榜</h2>
          <p class="section-subtitle">按平台分别展示热点排行，突出前列热点与最新变化。</p>
        </div>
      </div>

      <div class="home-platform-grid">
        <section
          v-for="platform in platforms"
          :key="platform.key"
          class="home-platform-board"
          :class="`home-platform-board--${platform.key}`"
        >
          <div class="home-platform-board__head">
            <div>
              <PlatformPill :platform="platform.key" />
              <h3>{{ platform.label }} Top 10</h3>
              <p>{{ platform.description }}</p>
            </div>
            <el-button type="primary" link @click="goPlatform(platform.key)">查看榜单</el-button>
          </div>

          <div v-if="platform.loading" class="home-rank-loading">
            <div class="home-rank-loading__text">加载中...</div>
          </div>

          <div v-else-if="platform.error" class="home-rank-error">
            <div class="home-rank-error__text">{{ platform.error }}</div>
            <el-button size="small" @click="loadPlatformData(platform)">重试</el-button>
          </div>

          <div v-else-if="platform.dailyTop.length" class="home-rank-list">
            <article
              v-for="(item, index) in platform.dailyTop"
              :key="getHotspotId(item, `${platform.key}-${index}`)"
              class="home-rank-row"
              @click="goDetail(getHotspotId(item))"
            >
              <div class="home-rank-row__rank" :class="{ top: index < 3 }">
                {{ index + 1 }}
              </div>

              <div class="home-rank-row__main">
                <div class="home-rank-row__title">
                  <strong>{{ cleanTitle(item.title) }}</strong>
                </div>
                <div class="home-rank-row__meta">
                  <span>{{ getPlatformHeatLabel(platform.key) }}：{{ formatHotValue(getHotValue(item), platform.key) }}</span>
                  <span>最新抓取：{{ platform.latestTime ? formatDateTime(platform.latestTime) : '暂无' }}</span>
                </div>
              </div>
            </article>
          </div>

          <el-empty v-else description="暂无数据" />

        </section>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import RequestState from '../components/RequestState.vue'
import PlatformPill from '../components/PlatformPill.vue'
import {
  getCrossPlatformTopics,
  getHotspotsByPlatform,
  getPlatformStats
} from '../api/hotspot'
import {
  PLATFORM_ORDER,
  buildSummaryText,
  cleanTitle,
  formatDateTime,
  formatHotValue,
  getHotValue,
  getHotspotId,
  getHotspotTime,
  getTopicPlatforms,
  getTopicTotalHotValue,
  getPlatformHeatLabel,
  getTopicPrimaryHotspot
} from '../utils/hotspot'

const router = useRouter()

const categories = [
  { name: '社会', keyword: '社会' },
  { name: '娱乐', keyword: '娱乐' },
  { name: '科技', keyword: '科技' },
  { name: '体育', keyword: '体育' },
  { name: '游戏', keyword: '游戏' },
  { name: '财经', keyword: '财经' },
  { name: '影视', keyword: '影视' },
  { name: '汽车', keyword: '汽车' }
]

const keyword = ref('')
const selectedCategory = ref('')
const crossLoading = ref(false)
const crossError = ref('')
const crossTopics = ref([])
const crossTopicTotal = ref(0)
const crossScrollerRef = ref(null)
const crossSlideIndex = ref(0)

const platforms = ref(
  PLATFORM_ORDER.map(platform => ({
    key: platform,
    ...{
      weibo: { label: '微博', description: '微博热搜与实时话题' },
      douyin: { label: '抖音', description: '抖音热视频与讨论热点' },
      bilibili: { label: 'B站', description: 'B站热搜词条与视频讨论' }
    }[platform],
    count: 0,
    dailyTop: [],
    currentList: [],
    pinned: null,
    latestTime: '',
    loading: false,
    error: ''
  }))
)

const totalTodayCount = computed(() =>
  platforms.value.reduce((sum, platform) => sum + Number(platform.count || 0), 0)
)
const platformCount = computed(() => platforms.value.length)
const crossTopicCount = computed(() => crossTopicTotal.value || crossTopics.value.length)
const crossSummaryCount = computed(() =>
  crossTopics.value.filter(topic => String(topic?.summary || '').trim()).length
)
const crossPreviewTopics = computed(() => crossTopics.value.slice(0, 8))
const crossPageCount = computed(() => Math.ceil(crossPreviewTopics.value.length / 2))

function scrollCrossPreview(direction) {
  const container = crossScrollerRef.value
  if (!container) return

  const nextIndex = Math.min(
    Math.max(crossSlideIndex.value + direction, 0),
    Math.max(crossPageCount.value - 1, 0)
  )

  crossSlideIndex.value = nextIndex
  container.scrollTo({
    left: container.clientWidth * nextIndex,
    behavior: 'smooth'
  })
}

function normalizeList(result) {
  if (Array.isArray(result)) return result
  if (Array.isArray(result?.data)) return result.data
  if (Array.isArray(result?.records)) return result.records
  if (Array.isArray(result?.list)) return result.list
  if (Array.isArray(result?.items)) return result.items
  return []
}

function normalizeTopicList(result) {
  if (Array.isArray(result)) return result
  if (Array.isArray(result?.records)) return result.records
  if (Array.isArray(result?.list)) return result.list
  if (Array.isArray(result?.items)) return result.items
  if (Array.isArray(result?.data)) return result.data
  if (Array.isArray(result?.data?.records)) return result.data.records
  if (Array.isArray(result?.data?.list)) return result.data.list
  if (Array.isArray(result?.data?.items)) return result.data.items
  return []
}

function getTopicTotal(result, list) {
  return Number(
    result?.total ?? 
    result?.data?.total ?? 
    result?.count ?? 
    result?.data?.count ?? 
    list.length
  )
}

function isSpecialItem(item) {
  return (
    item?.isSpecial === true ||
    item?.is_special === true ||
    Number(item?.isSpecial ?? item?.is_special ?? 0) === 1
  )
}

function getRankValue(item) {
  return Number(item?.rankNum ?? item?.rank_num ?? 999999)
}

function getHeatValueForSort(item) {
  return Number(item?.hotValue ?? item?.hot_value ?? item?.maxHotValue ?? item?.max_hot_value ?? 0)
}

function buildHomeTopList(list) {
  return normalizeList(list)
    .filter(item => !isSpecialItem(item))
    .slice()
    .sort((a, b) => {
      const rankA = getRankValue(a)
      const rankB = getRankValue(b)

      if (rankA !== rankB) {
        return rankA - rankB
      }

      return getHeatValueForSort(b) - getHeatValueForSort(a)
    })
    .slice(0, 10)
}

async function loadPlatformStats() {
  try {
    const statsList = await getPlatformStats()
    platforms.value = platforms.value.map(platform => {
      const stat = (Array.isArray(statsList) ? statsList : []).find(item => item.platform === platform.key)
      return {
        ...platform,
        count: Number(stat?.count ?? stat?.total ?? stat?.value ?? 0)
      }
    })
  } catch {
    platforms.value = platforms.value.map(platform => ({
      ...platform,
      count: platform.dailyTop.length
    }))
  }
}

async function loadPlatformData(platformState) {
  platformState.loading = true
  platformState.error = ''

  try {
    const currentResult = await getHotspotsByPlatform(platformState.key)
    console.log('[home raw result]', platformState.key, currentResult)

    const currentList = normalizeList(currentResult)
    console.log('[home normalized list]', platformState.key, currentList)

    platformState.currentList = currentList
    platformState.dailyTop = buildHomeTopList(currentList)
    platformState.pinned = currentList.find(item => isSpecialItem(item)) || null

    console.log('[home top list]', platformState.key, platformState.dailyTop)

    const latest = currentList
      .map(getHotspotTime)
      .filter(Boolean)
      .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0]

    platformState.latestTime = latest || ''
  } catch (requestError) {
    console.error('[home top10 error]', platformState.key, requestError)
    platformState.error = requestError?.message || `${platformState.label}榜单加载失败`
    platformState.dailyTop = []
    platformState.currentList = []
    platformState.pinned = null
    platformState.latestTime = ''
  } finally {
    platformState.loading = false
    console.log('[home loading end]', platformState.key, platformState.loading)
  }
}

async function loadCrossTopics() {
  crossLoading.value = true
  crossError.value = ''

  try {
    const result = await getCrossPlatformTopics({ page: 1, pageSize: 8 })
    
    console.log('[home cross raw]', result)

    const list = normalizeTopicList(result)
    console.log('[home cross list]', list)

    crossTopics.value = list
    crossTopicTotal.value = getTopicTotal(result, list)
  } catch (error) {
    console.error('[home cross error]', error)
    crossError.value = error?.message || '跨平台主题加载失败'
    crossTopics.value = []
    crossTopicTotal.value = 0
  } finally {
    crossLoading.value = false
  }
}

function handleSearch() {
  const value = keyword.value.trim()
  if (!value) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  router.push({
    name: 'search',
    query: { keyword: value }
  })
}

function handleCategoryClick(category) {
  selectedCategory.value = category.name
  router.push({
    name: 'search',
    query: { keyword: category.keyword }
  })
}

function goPlatform(platform) {
  router.push({
    name: 'platform',
    params: { platform },
    query: { mode: 'current' }
  })
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

function goCrossPlatform() {
  router.push({ name: 'crossPlatform' })
}

function goHistory() {
  router.push({ name: 'history' })
}

function goCrossTopic(topic) {
  const primary = getTopicPrimaryHotspot(topic)
  if (primary) {
    goDetail(getHotspotId(primary))
    return
  }
  goCrossPlatform()
}

onMounted(async () => {
  await Promise.all([
    Promise.all(platforms.value.map(loadPlatformData)),
    loadCrossTopics()
  ])

  await loadPlatformStats()
})
</script>

<style scoped>
.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.7fr);
  gap: 24px;
}

.home-hero__search {
  max-width: 600px;
  margin-top: 20px;
}

.home-hero__actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.home-hero__chips {
  margin-top: 18px;
}

.home-chip-button {
  padding: 8px 13px;
}

.home-hero__mini-stats {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 180px));
  gap: 14px;
}

.home-hero__mini-stat {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(135, 160, 206, 0.18);
  box-shadow: 0 12px 30px rgba(30, 64, 175, 0.06);
}

.home-hero__mini-label {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}

.home-hero__mini-stat strong {
  display: block;
  font-size: 28px;
  line-height: 1.1;
  color: var(--text-primary);
}

.home-hero__mini-stat small {
  display: block;
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.home-hero__aside {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.home-pipeline {
  position: relative;
  overflow: hidden;
  padding: 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(135, 160, 206, 0.14);
}

.home-pipeline::after {
  content: '';
  position: absolute;
  inset: auto -40px -44px auto;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(47, 107, 255, 0.1), transparent 70%);
}

.home-pipeline__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.home-pipeline__head span {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 800;
}

.home-pipeline__head small {
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.home-pipeline__steps {
  display: grid;
  gap: 8px;
}

.home-pipeline__step {
  position: relative;
  padding: 12px 12px 12px 40px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(244, 248, 255, 0.98), rgba(239, 246, 255, 0.9));
}

.home-pipeline__step::before {
  content: '';
  position: absolute;
  left: 16px;
  top: 16px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2f6bff, #28b8ff);
  box-shadow: 0 0 0 5px rgba(47, 107, 255, 0.08);
}

.home-pipeline__step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 20px;
  top: 26px;
  width: 2px;
  height: calc(100% - 8px);
  background: linear-gradient(180deg, rgba(47, 107, 255, 0.3), rgba(47, 107, 255, 0));
}

.home-pipeline__step strong {
  display: block;
  font-size: 14px;
}

.home-pipeline__step span {
  display: block;
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 12px;
}

.home-pipeline__foot {
  position: relative;
  z-index: 1;
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.home-board-panel,
.home-cross-panel {
  padding: 22px;
}

.home-platform-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.home-platform-board {
  position: relative;
  overflow: hidden;
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(248, 251, 255, 0.96), rgba(242, 247, 255, 0.94));
  box-shadow: inset 0 0 0 1px rgba(135, 160, 206, 0.12);
}

.home-platform-board::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  opacity: 0.92;
}

.home-platform-board--weibo::before {
  background: linear-gradient(90deg, #ef4444, #fb7185);
}

.home-platform-board--douyin::before {
  background: linear-gradient(90deg, #111827, #0f766e);
}

.home-platform-board--bilibili::before {
  background: linear-gradient(90deg, #38bdf8, #6366f1);
}

.home-platform-board__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.home-platform-board__head h3 {
  margin: 12px 0 4px;
  font-size: 20px;
}

.home-platform-board__head p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.home-rank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.home-special-card {
  padding: 12px 14px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 247, 237, 0.96), rgba(255, 241, 242, 0.96));
  border: 1px dashed rgba(255, 134, 76, 0.3);
  cursor: pointer;
}

.home-special-card__label {
  color: #f97316;
  font-size: 12px;
  font-weight: 800;
}

.home-special-card__title {
  margin-top: 8px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.55;
}

.home-special-card__meta {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.home-rank-row {
  display: grid;
  grid-template-columns: 38px 1fr;
  gap: 12px;
  align-items: start;
  padding: 12px 2px;
  border-bottom: 1px solid rgba(135, 160, 206, 0.12);
  cursor: pointer;
  transition: transform 0.2s ease;
}

.home-rank-row:last-child {
  border-bottom: 0;
}

.home-rank-row:hover {
  transform: translateX(3px);
}

.home-rank-row__rank {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 800;
  background: rgba(226, 234, 247, 0.94);
}

.home-rank-row__rank.top {
  color: #fff;
  background: linear-gradient(135deg, #ff6b4a, #ff9f1c);
  box-shadow: 0 10px 22px rgba(255, 122, 69, 0.24);
}

.home-rank-row__main {
  min-width: 0;
}

.home-rank-row__title strong {
  display: block;
  font-size: 15px;
  line-height: 1.55;
}

.home-rank-row__meta {
  margin-top: 6px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 12px;
}

.cross-preview-head {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cross-preview-carousel-wrap {
  position: relative;
}

.cross-preview-nav {
  position: absolute;
  top: 50%;
  z-index: 5;
  transform: translateY(-50%);
  width: 38px;
  height: 38px;
  box-shadow: 0 12px 28px rgba(30, 64, 175, 0.16);
}

.cross-preview-nav--prev {
  left: 8px;
}

.cross-preview-nav--next {
  right: 8px;
}

.cross-preview-nav.is-disabled {
  opacity: 0.35;
}

.cross-preview-carousel {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: calc((100% - 16px) / 2);
  gap: 16px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  padding-bottom: 4px;
}

.cross-preview-carousel::-webkit-scrollbar {
  display: none;
}

.cross-preview-card--slide {
  scroll-snap-align: start;
  min-height: 240px;
}

.cross-preview-card {
  position: relative;
  overflow: hidden;
  padding: 20px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(247, 250, 255, 0.96), rgba(241, 246, 255, 0.92));
  box-shadow: inset 0 0 0 1px rgba(135, 160, 206, 0.12);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.cross-preview-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 18px;
  bottom: 18px;
  width: 4px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2f6bff, #28b8ff);
}

.cross-preview-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}

.cross-preview-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.cross-preview-card__head h3 {
  margin: 0;
  padding-left: 8px;
  font-size: 20px;
  line-height: 1.35;
}

.cross-preview-card__platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
  padding-left: 8px;
}

.cross-preview-card__summary {
  margin: 16px 0 0;
  padding-left: 8px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.cross-preview-card__meta {
  margin-top: 16px;
  padding-left: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1160px) {
  .home-platform-grid {
    grid-template-columns: 1fr;
  }

  .cross-preview-carousel {
    grid-auto-columns: 100%;
  }
}

@media (max-width: 980px) {
  .home-hero {
    grid-template-columns: 1fr;
  }
}
</style>
