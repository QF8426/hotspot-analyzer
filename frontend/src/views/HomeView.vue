<template>
  <div class="app-container page-stack">
    <section class="page-hero home-hero">
      <div class="home-hero__content">
        <span class="page-hero__eyebrow">Hotspot Intelligence Hub</span>
        <h1 class="page-hero__title">跨平台热点聚合分析器</h1>
        <p class="page-hero__subtitle">
          面向微博、抖音、B站热点榜单的统一展示入口，提供趋势可视化、AI 简介、跨平台主题聚合和历史回看能力，适合毕业设计答辩中的系统总览展示。
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
      </div>

      <div class="home-hero__aside">
        <div class="home-pipeline">
          <div class="home-pipeline__head">
            <span>系统链路</span>
            <small>Data Flow</small>
          </div>

          <div class="home-pipeline__steps">
            <div class="home-pipeline__step">
              <strong>热榜采集</strong>
              <span>微博 / 抖音 / B站</span>
            </div>
            <div class="home-pipeline__step">
              <strong>AI 简介</strong>
              <span>摘要与热点说明</span>
            </div>
            <div class="home-pipeline__step">
              <strong>跨平台分析</strong>
              <span>识别共同事件主题</span>
            </div>
            <div class="home-pipeline__step">
              <strong>前端展示</strong>
              <span>榜单、详情与趋势</span>
            </div>
          </div>

          <p class="home-pipeline__foot">沿用现有 API，不写死假数据，保持与后端链路一致。</p>
        </div>

        <div class="home-hero__legend">
          <div class="legend-item">
            <span class="legend-item__dot legend-item__dot--weibo"></span>
            <span>微博热搜</span>
          </div>
          <div class="legend-item">
            <span class="legend-item__dot legend-item__dot--douyin"></span>
            <span>抖音热榜</span>
          </div>
          <div class="legend-item">
            <span class="legend-item__dot legend-item__dot--bilibili"></span>
            <span>B站热搜</span>
          </div>
        </div>
      </div>
    </section>

    <section class="metric-grid home-metric-grid">
      <article class="metric-card home-metric-card home-metric-card--total">
        <div class="metric-card__kicker">
          <span class="metric-card__icon">Σ</span>
          今日概览
        </div>
        <div class="metric-card__label">今日热点总数</div>
        <div class="metric-card__value mono-text">{{ totalTodayCount }}</div>
        <div class="metric-card__hint">来自三平台今日趋势数据的汇总统计。</div>
      </article>

      <article class="metric-card home-metric-card home-metric-card--platforms">
        <div class="metric-card__kicker">
          <span class="metric-card__icon">3</span>
          Platform
        </div>
        <div class="metric-card__label">覆盖平台数</div>
        <div class="metric-card__value mono-text">{{ platformCount }}</div>
        <div class="metric-card__hint">当前统一覆盖微博、抖音、B站三端热点。</div>
      </article>

      <article class="metric-card home-metric-card home-metric-card--summary">
        <div class="metric-card__kicker">
          <span class="metric-card__icon">AI</span>
          Summary
        </div>
        <div class="metric-card__label">跨平台 AI 简介数</div>
        <div class="metric-card__value mono-text">{{ crossSummaryCount }}</div>
        <div class="metric-card__hint">按跨平台主题接口中返回 summary 的主题数兼容统计。</div>
      </article>

      <article class="metric-card home-metric-card home-metric-card--topics">
        <div class="metric-card__kicker">
          <span class="metric-card__icon">CP</span>
          Topic
        </div>
        <div class="metric-card__label">今日跨平台主题数</div>
        <div class="metric-card__value mono-text">{{ crossTopicCount }}</div>
        <div class="metric-card__hint">展示系统识别出的多平台共同热点主题规模。</div>
      </article>
    </section>

    <section class="table-card home-board-panel">
      <div class="section-head">
        <div>
          <h2 class="section-title">平台今日 Top 榜</h2>
          <p class="section-subtitle">榜单保留平台语境，突出前 3 名与热点排序变化。</p>
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
              <h3>{{ platform.label }}今日 Top 榜</h3>
              <p>{{ platform.description }}</p>
            </div>
            <el-button type="primary" link @click="goPlatform(platform.key)">进入平台页</el-button>
          </div>

          <RequestState
            compact
            :loading="platform.loading"
            :error="platform.error"
            :empty="!platform.loading && !platform.error && platform.dailyTop.length === 0"
            empty-description="暂无今日榜单数据"
            @retry="loadPlatformData(platform)"
          >
            <div class="home-rank-list">
              <article
                v-if="platform.pinned"
                class="home-special-card"
                @click="goDetail(getHotspotId(platform.pinned))"
              >
                <div class="home-special-card__label">特殊展示项</div>
                <div class="home-special-card__title">{{ cleanTitle(platform.pinned.title) }}</div>
                <div class="home-special-card__meta">
                  <span>更新时间：{{ formatDateTime(getHotspotTime(platform.pinned)) }}</span>
                </div>
              </article>

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
          </RequestState>
        </section>
      </div>
    </section>

    <RequestState
      :loading="crossLoading"
      :error="crossError"
      :empty="!crossLoading && !crossError && crossPreviewTopics.length === 0"
      empty-description="暂无跨平台主题预览"
      @retry="loadCrossTopics"
    >
      <section class="table-card home-cross-panel">
        <div class="section-head cross-preview-head">
          <div>
            <h2 class="section-title">跨平台热点预览</h2>
            <p class="section-subtitle">突出系统亮点：同一事件在多个平台同步升温时的聚合视角。</p>
          </div>
          <el-button type="primary" @click="goCrossPlatform">进入跨平台热点合集</el-button>
        </div>

        <div class="cross-preview-grid">
          <article
            v-for="topic in crossPreviewTopics"
            :key="topic.id"
            class="cross-preview-card"
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
              {{ buildSummaryText(topic.summary, '该主题已被系统识别为多平台共同关注的话题，可继续进入详情查看关联热点。', 124) }}
            </p>

            <div class="cross-preview-card__meta">
              <span>关联平台：{{ topic.platformCount || getTopicPlatforms(topic).length }}</span>
              <span>关联热点：{{ topic.hotspotCount || topic.hotspots?.length || 0 }}</span>
              <span>综合指标：{{ formatHotValue(getTopicTotalHotValue(topic)) }}</span>
            </div>
          </article>
        </div>
      </section>
    </RequestState>
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
  getDailyTop,
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
  getPlatformHeatLabel,
  getPlatformMeta,
  getTopicPlatforms,
  getTopicTotalHotValue
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

const platforms = ref(
  PLATFORM_ORDER.map(platform => ({
    ...getPlatformMeta(platform),
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
const crossTopicCount = computed(() => crossTopics.value.length)
const crossSummaryCount = computed(() =>
  crossTopics.value.filter(topic => String(topic?.summary || '').trim()).length
)
const crossPreviewTopics = computed(() => crossTopics.value.slice(0, 4))

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
    const [dailyTop, currentList] = await Promise.all([
      getDailyTop(platformState.key, 10),
      getHotspotsByPlatform(platformState.key)
    ])

    platformState.dailyTop = Array.isArray(dailyTop) ? dailyTop : []
    platformState.currentList = Array.isArray(currentList) ? currentList : []
    platformState.pinned = platformState.currentList.find(item => item.isSpecial) || null

    const latest = [...platformState.currentList]
      .map(getHotspotTime)
      .filter(Boolean)
      .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0]

    platformState.latestTime = latest || ''
  } catch (requestError) {
    platformState.error = requestError?.message || `${platformState.label}榜单加载失败`
    platformState.dailyTop = []
    platformState.currentList = []
    platformState.pinned = null
    platformState.latestTime = ''
  } finally {
    platformState.loading = false
  }
}

async function loadCrossTopics() {
  crossLoading.value = true
  crossError.value = ''

  try {
    const result = await getCrossPlatformTopics({ limit: 50, todayOnly: true })
    crossTopics.value = Array.isArray(result) ? result : []
  } catch (requestError) {
    crossError.value = requestError?.message || '跨平台主题加载失败'
    crossTopics.value = []
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
  if (topic?.id) {
    router.push({ name: 'crossPlatformTopic', params: { id: topic.id } })
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
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
  gap: 28px;
}

.home-hero__search {
  max-width: 640px;
  margin-top: 24px;
}

.home-hero__actions {
  margin-top: 18px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.home-hero__chips {
  margin-top: 20px;
}

.home-chip-button {
  padding: 8px 13px;
}

.home-hero__aside {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.home-pipeline,
.home-hero__legend {
  position: relative;
  overflow: hidden;
  padding: 20px;
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
  margin-bottom: 16px;
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
  gap: 10px;
}

.home-pipeline__step {
  position: relative;
  padding: 14px 14px 14px 44px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(244, 248, 255, 0.98), rgba(239, 246, 255, 0.9));
}

.home-pipeline__step::before {
  content: '';
  position: absolute;
  left: 18px;
  top: 18px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2f6bff, #28b8ff);
  box-shadow: 0 0 0 6px rgba(47, 107, 255, 0.08);
}

.home-pipeline__step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 23px;
  top: 30px;
  width: 2px;
  height: calc(100% - 8px);
  background: linear-gradient(180deg, rgba(47, 107, 255, 0.3), rgba(47, 107, 255, 0));
}

.home-pipeline__step strong {
  display: block;
  font-size: 15px;
}

.home-pipeline__step span {
  display: block;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 13px;
}

.home-pipeline__foot {
  position: relative;
  z-index: 1;
  margin: 16px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.home-hero__legend {
  display: grid;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-weight: 700;
}

.legend-item__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-item__dot--weibo {
  background: #ef4444;
}

.legend-item__dot--douyin {
  background: #0f172a;
}

.legend-item__dot--bilibili {
  background: #38bdf8;
}

.home-metric-card--total {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(236, 244, 255, 0.96));
}

.home-metric-card--platforms {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(237, 249, 247, 0.94));
}

.home-metric-card--summary {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 241, 255, 0.94));
}

.home-metric-card--topics {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 244, 236, 0.94));
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
  margin-bottom: 18px;
}

.cross-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
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
  .home-platform-grid,
  .cross-preview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .home-hero {
    grid-template-columns: 1fr;
  }
}
</style>
