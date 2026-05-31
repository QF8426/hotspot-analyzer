<template>
  <div class="app-container page-stack">
    <section class="page-card page-card--strong detail-toolbar">
      <div class="detail-toolbar__inner">
        <el-button type="primary" plain @click="goBack">返回上一页</el-button>
        <span class="detail-toolbar__tip">热点详情页聚焦标题、AI 简介、趋势变化与跨平台关联</span>
      </div>
    </section>

    <RequestState
      :loading="loading"
      :error="error"
      :empty="!loading && !error && !detail"
      empty-description="未找到对应的热点详情"
      @retry="loadPage"
    >
      <section v-if="detail" class="page-hero detail-hero">
        <div class="detail-hero__main">
          <div class="detail-hero__badges">
            <PlatformPill :platform="detail.platform" />
            <div v-if="isCrossPlatform" class="detail-analysis-flag">
              <strong>跨平台分析</strong>
              <span>已纳入共同话题识别</span>
            </div>
            <el-tag v-if="detail.isSpecial" type="warning" effect="plain">平台特殊项</el-tag>
          </div>

          <h1 class="page-hero__title detail-hero__title">{{ cleanTitle(detail.title) || '未命名热点' }}</h1>
          <p class="page-hero__subtitle detail-hero__subtitle">{{ heroDescription }}</p>

          <div class="detail-hero__facts">
            <div class="detail-fact">
              <span>平台排名</span>
              <strong>{{ detail.rankNum ?? '暂无' }}</strong>
            </div>
            <div class="detail-fact">
              <span>{{ getPlatformHeatLabel(detail.platform) }}</span>
              <strong>{{ formatHotValue(getHotValue(detail), detail.platform) }}</strong>
            </div>
            <div class="detail-fact">
              <span>更新时间</span>
              <strong>{{ formatDateTime(getHotspotTime(detail)) }}</strong>
            </div>
            <div class="detail-fact">
              <span>关联热点</span>
              <strong>{{ relatedHotspotIds.length }}</strong>
            </div>
          </div>
        </div>

        <div class="detail-hero__side">
          <div class="detail-side-card">
            <span>来源链接</span>
            <el-button type="primary" :disabled="!detail.sourceUrl" @click="openSource">
              查看原始内容
            </el-button>
          </div>

          <div v-if="relatedPlatforms.length" class="detail-side-card">
            <span>关联平台</span>
            <div class="detail-side-card__platforms">
              <PlatformPill v-for="platform in relatedPlatforms" :key="platform" :platform="platform" />
            </div>
          </div>

          <div class="detail-side-card detail-side-card--note">
            <span>分析说明</span>
            <strong>{{ isCrossPlatform ? '跨平台传播观察' : '单平台热点详情' }}</strong>
            <p>
              {{ isCrossPlatform ? '当前热点已经进入跨平台主题分析链路，可结合下方趋势和关联热点一起展示。' : '当前页面聚焦所属平台内的热点表现与时间序列变化。' }}
            </p>
          </div>
        </div>
      </section>

      <section v-if="detail" class="table-card detail-summary-card">
        <div class="section-head detail-section-head">
          <div>
            <h2 class="section-title">AI 简介</h2>
            <p class="section-subtitle">
              {{ hasAiSummary ? '当前内容来自现有详情接口中的 AI / 摘要字段。' : '接口暂未提供 AI 简介，页面已自动生成自然的兜底说明。' }}
            </p>
          </div>
          <el-tag v-if="isCrossPlatform" type="warning" effect="plain">跨平台分析</el-tag>
        </div>

        <div class="detail-summary-card__body">
          <p
            v-for="(paragraph, index) in summaryParagraphs"
            :key="`${index}-${paragraph.slice(0, 12)}`"
            class="detail-summary-card__paragraph"
          >
            {{ paragraph }}
          </p>
        </div>
      </section>

      <section v-if="detail" class="detail-analysis-grid">
        <article class="table-card detail-trend-card">
          <div class="section-head detail-section-head">
            <div>
              <h2 class="section-title">趋势分析</h2>
              <p class="section-subtitle">优先展示现有趋势接口返回的排名 / 热度时间序列。</p>
            </div>
          </div>

          <div v-if="hasTrendData" ref="chartRef" class="detail-chart"></div>
          <div v-else class="detail-trend-empty">
            <el-empty description="暂无趋势数据，等待后续采集形成时间序列" />
            <p>当后续调度持续抓取同一热点时，这里会自动展示排名或热度折线图。</p>
          </div>
        </article>

        <article class="table-card detail-info-card">
          <div class="section-head detail-section-head">
            <div>
              <h2 class="section-title">基础信息</h2>
              <p class="section-subtitle">保留用户真正关心的字段，不直接暴露数据库味很重的内部信息。</p>
            </div>
          </div>

          <dl class="detail-info-list">
            <div class="detail-info-item">
              <dt>所属平台</dt>
              <dd>{{ getPlatformLabel(detail.platform) }}</dd>
            </div>
            <div class="detail-info-item">
              <dt>平台排名</dt>
              <dd>{{ detail.rankNum ?? '暂无' }}</dd>
            </div>
            <div class="detail-info-item">
              <dt>{{ getPlatformHeatLabel(detail.platform) }}</dt>
              <dd>{{ formatHotValue(getHotValue(detail), detail.platform) }}</dd>
            </div>
            <div class="detail-info-item">
              <dt>更新时间</dt>
              <dd>{{ formatDateTime(getHotspotTime(detail)) }}</dd>
            </div>
            <div class="detail-info-item">
              <dt>来源状态</dt>
              <dd>{{ detail.sourceUrl ? '已提供来源链接' : '暂无来源链接' }}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section v-if="detail && (relatedHotspots.length || relatedHotspotIds.length)" class="table-card detail-related-panel">
        <div class="section-head detail-section-head">
          <div>
            <h2 class="section-title">关联热点</h2>
            <p class="section-subtitle">
              {{ isCrossPlatform ? '该区域用于展示跨平台主题下的相关热点。' : '若接口返回了关联热点 ID，这里会兼容展示可跳转入口。' }}
            </p>
          </div>
          <el-tag v-if="relatedLoading" type="info" effect="plain">加载中</el-tag>
        </div>

        <div class="detail-related-list">
          <article
            v-for="item in relatedHotspots"
            :key="getHotspotId(item)"
            class="detail-related-item"
            @click="goDetail(getHotspotId(item))"
          >
            <div class="detail-related-item__main">
              <div class="detail-related-item__title-row">
                <PlatformPill :platform="item.platform" />
                <h3>{{ cleanTitle(item.title) || `关联热点 ${getHotspotId(item)}` }}</h3>
              </div>
              <div class="detail-related-item__meta">
                <span>排名：{{ item.rankNum ?? '暂无' }}</span>
                <span>{{ getPlatformHeatLabel(item.platform) }}：{{ formatHotValue(getHotValue(item), item.platform) }}</span>
                <span>更新时间：{{ formatDateTime(getHotspotTime(item)) }}</span>
              </div>
            </div>
            <el-button type="primary" plain @click.stop="goDetail(getHotspotId(item))">查看详情</el-button>
          </article>

          <article
            v-for="id in missingRelatedIds"
            :key="`fallback-${id}`"
            class="detail-related-item detail-related-item--fallback"
            @click="goDetail(id)"
          >
            <div class="detail-related-item__main">
              <div class="detail-related-item__title-row">
                <el-tag effect="plain">关联热点</el-tag>
                <h3>热点 ID：{{ id }}</h3>
              </div>
              <div class="detail-related-item__meta">
                <span>接口未返回完整标题，已保留可跳转入口</span>
              </div>
            </div>
            <el-button type="primary" plain @click.stop="goDetail(id)">查看详情</el-button>
          </article>
        </div>
      </section>
    </RequestState>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import PlatformPill from '../components/PlatformPill.vue'
import RequestState from '../components/RequestState.vue'
import { getHotspotDetail, getTrend } from '../api/hotspot'
import {
  cleanTitle,
  formatDateTime,
  formatHotValue,
  getHotValue,
  getHotspotId,
  getHotspotTime,
  getPlatformHeatLabel,
  getPlatformLabel,
  parsePlatformList
} from '../utils/hotspot'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const error = ref('')
const detail = ref(null)
const trend = ref({
  times: [],
  hotValues: [],
  rankValues: []
})
const relatedHotspots = ref([])
const relatedLoading = ref(false)
const chartRef = ref(null)

let chartInstance = null

const hotspotId = computed(() => String(route.params.id || ''))
const analysisType = computed(() =>
  String(detail.value?.analysisType || detail.value?.analysis_type || '').trim()
)
const isCrossPlatform = computed(() => analysisType.value === 'cross_platform')
const relatedPlatforms = computed(() =>
  parsePlatformList(detail.value?.relatedPlatforms || detail.value?.related_platforms)
)
const relatedHotspotIds = computed(() => {
  const ids = parsePlatformList(detail.value?.relatedHotspotIds || detail.value?.related_hotspot_ids)
  const seen = new Set()

  return ids.filter(id => {
    const value = String(id || '')
    if (!value || value === hotspotId.value || seen.has(value)) {
      return false
    }
    seen.add(value)
    return true
  })
})

const missingRelatedIds = computed(() => {
  const loadedIds = new Set(relatedHotspots.value.map(item => String(getHotspotId(item))))
  return relatedHotspotIds.value.filter(id => !loadedIds.has(String(id)))
})

const hasAiSummary = computed(() => {
  const text = detail.value?.aiSummary || detail.value?.summary || detail.value?.ai_summary || ''
  return String(text).trim().length > 0
})

const fallbackSummary = computed(() => {
  if (!detail.value) return '正在加载热点详情。'

  if (isCrossPlatform.value) {
    const platformText = relatedPlatforms.value.map(getPlatformLabel).join('、') || '多个平台'
    return `该热点已被系统识别为跨平台关联话题，目前涉及${platformText}的共同讨论。当前接口尚未返回完整 AI 简介，因此页面先展示基础信息、趋势变化和关联热点入口，便于继续追踪传播路径。`
  }

  const rankText =
    detail.value.rankNum === null || detail.value.rankNum === undefined
      ? '当前已进入平台热点列表'
      : `当前位于平台榜单第 ${detail.value.rankNum} 位`
  const heatText =
    getHotValue(detail.value) === null || getHotValue(detail.value) === undefined
      ? '暂未返回明确的热度指标'
      : `${getPlatformHeatLabel(detail.value.platform)}约为 ${formatHotValue(
          getHotValue(detail.value),
          detail.value.platform
        )}`

  return `该热点正在${getPlatformLabel(detail.value.platform)}中受到关注，${rankText}，${heatText}。当前接口暂无 AI 简介时，页面会自动提供这段自然说明，避免详情页出现空白内容。`
})

const displaySummary = computed(() => {
  const text = detail.value?.aiSummary || detail.value?.summary || detail.value?.ai_summary || ''
  return String(text).trim() || fallbackSummary.value
})

const summaryParagraphs = computed(() =>
  String(displaySummary.value)
    .split(/\n+/)
    .map(item => item.trim())
    .filter(Boolean)
)

const heroDescription = computed(() => {
  if (!detail.value) return ''

  const pieces = [
    `${getPlatformLabel(detail.value.platform)}热点分析页`,
    detail.value.rankNum !== null && detail.value.rankNum !== undefined
      ? `当前排名第 ${detail.value.rankNum} 位`
      : '当前排名暂无',
    `${getPlatformHeatLabel(detail.value.platform)}为 ${formatHotValue(
      getHotValue(detail.value),
      detail.value.platform
    )}`
  ]

  if (isCrossPlatform.value && relatedPlatforms.value.length) {
    pieces.push(`已关联 ${relatedPlatforms.value.map(getPlatformLabel).join('、')}`)
  }

  return pieces.join('，') + '。'
})

const hasTrendData = computed(() => {
  return (
    Array.isArray(trend.value.times) &&
    trend.value.times.length > 0 &&
    (trend.value.hotValues.some(value => value !== null && value !== undefined) ||
      trend.value.rankValues.some(value => value !== null && value !== undefined))
  )
})

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

function resizeChart() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

function initChart() {
  if (!chartRef.value || !hasTrendData.value || !detail.value) return

  disposeChart()
  chartInstance = echarts.init(chartRef.value)

  chartInstance.setOption({
    color: ['#2f6bff', '#28b8ff'],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      top: 4,
      data: ['平台排名', getPlatformHeatLabel(detail.value.platform)]
    },
    grid: {
      left: 54,
      right: 76,
      top: 56,
      bottom: 48
    },
    xAxis: {
      type: 'category',
      data: trend.value.times,
      boundaryGap: false,
      axisLabel: {
        color: '#5f728f',
        rotate: 24
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(101, 132, 188, 0.3)'
        }
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '排名',
        inverse: true,
        min: value => Math.max(1, Math.floor(value.min || 1) - 1),
        axisLabel: { color: '#5f728f' },
        splitLine: {
          lineStyle: {
            color: 'rgba(135, 160, 206, 0.14)'
          }
        }
      },
      {
        type: 'value',
        name: getPlatformHeatLabel(detail.value.platform),
        position: 'right',
        axisLabel: {
          color: '#5f728f',
          formatter: value => formatHotValue(value, detail.value.platform)
        },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '平台排名',
        type: 'line',
        yAxisIndex: 0,
        data: trend.value.rankValues,
        smooth: true,
        connectNulls: false,
        symbolSize: 7,
        lineStyle: {
          width: 3
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(47, 107, 255, 0.18)' },
            { offset: 1, color: 'rgba(47, 107, 255, 0.02)' }
          ])
        }
      },
      {
        name: getPlatformHeatLabel(detail.value.platform),
        type: 'line',
        yAxisIndex: 1,
        data: trend.value.hotValues,
        smooth: true,
        connectNulls: false,
        symbolSize: 7,
        lineStyle: {
          width: 3
        }
      }
    ]
  })
}

async function loadRelatedHotspots() {
  relatedHotspots.value = []

  if (!relatedHotspotIds.value.length) return

  relatedLoading.value = true

  try {
    const results = await Promise.all(
      relatedHotspotIds.value.slice(0, 12).map(async id => {
        try {
          const result = await getHotspotDetail(id)
          return result ? { ...result, id: getHotspotId(result, id) } : null
        } catch {
          return null
        }
      })
    )

    relatedHotspots.value = results.filter(Boolean)
  } finally {
    relatedLoading.value = false
  }
}

async function loadPage() {
  if (!hotspotId.value) return

  loading.value = true
  error.value = ''
  detail.value = null
  trend.value = {
    times: [],
    hotValues: [],
    rankValues: []
  }
  relatedHotspots.value = []
  disposeChart()

  try {
    const [detailResult, trendResult] = await Promise.allSettled([
      getHotspotDetail(hotspotId.value),
      getTrend(hotspotId.value)
    ])

    if (detailResult.status !== 'fulfilled') {
      throw detailResult.reason
    }

    detail.value = detailResult.value || null

    if (trendResult.status === 'fulfilled') {
      trend.value = {
        times: Array.isArray(trendResult.value?.times) ? trendResult.value.times : [],
        hotValues: Array.isArray(trendResult.value?.hotValues) ? trendResult.value.hotValues : [],
        rankValues: Array.isArray(trendResult.value?.rankValues) ? trendResult.value.rankValues : []
      }
    }

    await loadRelatedHotspots()
    await nextTick()
    initChart()
  } catch (requestError) {
    error.value = requestError?.message || '热点详情加载失败，请稍后重试'
    detail.value = null
    trend.value = {
      times: [],
      hotValues: [],
      rankValues: []
    }
    relatedHotspots.value = []
  } finally {
    loading.value = false
  }
}

function openSource() {
  if (detail.value?.sourceUrl) {
    window.open(detail.value.sourceUrl, '_blank', 'noopener,noreferrer')
  }
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

function goBack() {
  router.back()
}

watch(
  () => route.params.id,
  async () => {
    await loadPage()
  },
  { immediate: true }
)

watch(
  () => hasTrendData.value,
  async hasData => {
    if (!hasData) {
      disposeChart()
      return
    }

    await nextTick()
    initChart()
  }
)

onMounted(() => {
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  disposeChart()
})
</script>

<style scoped>
.detail-toolbar {
  padding: 16px 22px;
}

.detail-toolbar__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.detail-toolbar__tip {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.detail-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
  gap: 22px;
}

.detail-hero__main {
  min-width: 0;
}

.detail-hero__badges {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-analysis-flag {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 999px;
  color: #8a4b00;
  background: linear-gradient(135deg, rgba(255, 247, 220, 0.96), rgba(255, 238, 190, 0.92));
  box-shadow: inset 0 0 0 1px rgba(250, 204, 21, 0.22);
}

.detail-analysis-flag strong {
  font-size: 13px;
}

.detail-analysis-flag span {
  font-size: 12px;
}

.detail-hero__title {
  margin-bottom: 14px;
  max-width: 980px;
}

.detail-hero__subtitle {
  max-width: 900px;
}

.detail-hero__facts {
  margin-top: 22px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-fact {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(135, 160, 206, 0.12);
}

.detail-fact span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.detail-fact strong {
  display: block;
  margin-top: 8px;
  font-size: 18px;
  line-height: 1.4;
}

.detail-hero__side {
  display: grid;
  gap: 14px;
}

.detail-side-card {
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(135, 160, 206, 0.12);
  display: grid;
  gap: 10px;
}

.detail-side-card span {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.detail-side-card strong {
  font-size: 18px;
}

.detail-side-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.detail-side-card__platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-summary-card {
  padding: 24px;
}

.detail-section-head {
  margin-bottom: 18px;
}

.detail-summary-card__body {
  position: relative;
  display: grid;
  gap: 16px;
  padding-left: 18px;
}

.detail-summary-card__body::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 4px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2f6bff, #28b8ff);
}

.detail-summary-card__paragraph {
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.95;
}

.detail-summary-card__paragraph:first-child {
  font-size: 16px;
}

.detail-analysis-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 16px;
}

.detail-trend-card,
.detail-info-card,
.detail-related-panel {
  padding: 22px;
}

.detail-chart {
  height: 420px;
}

.detail-trend-empty {
  display: grid;
  gap: 10px;
  padding: 8px 0 0;
}

.detail-trend-empty p {
  margin: 0;
  text-align: center;
  color: var(--text-secondary);
  line-height: 1.7;
}

.detail-info-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.detail-info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 14px;
  border-radius: 16px;
  background: rgba(245, 249, 255, 0.8);
  border: 1px solid rgba(135, 160, 206, 0.12);
}

.detail-info-item dt {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.detail-info-item dd {
  margin: 0;
  text-align: right;
  font-size: 14px;
  font-weight: 800;
  color: var(--text-primary);
}

.detail-related-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-related-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  padding: 16px 4px;
  border-bottom: 1px solid rgba(135, 160, 206, 0.12);
  cursor: pointer;
  transition: transform 0.2s ease;
}

.detail-related-item:last-child {
  border-bottom: 0;
}

.detail-related-item:hover {
  transform: translateX(4px);
}

.detail-related-item--fallback {
  border-bottom-style: dashed;
}

.detail-related-item__main {
  min-width: 0;
}

.detail-related-item__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-related-item__title-row h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.45;
}

.detail-related-item__meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1180px) {
  .detail-hero,
  .detail-analysis-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .detail-hero__facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .detail-related-item {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .detail-hero__facts {
    grid-template-columns: 1fr;
  }
}
</style>
