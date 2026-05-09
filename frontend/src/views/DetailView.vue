<template>
  <div class="detail-page">
    <div class="top-bar">
      <el-button type="primary" plain @click="goBack">返回</el-button>
    </div>

    <div v-if="detail" class="detail-content">
      <div class="title-block">
        <h1>{{ cleanTitle(detail.title) }}</h1>

        <div class="meta">
          <el-tag v-if="detail.isSpecial" type="danger">置顶</el-tag>
          <el-tag>{{ platformName }}</el-tag>
          <span>热度：{{ formatHotValue(detail.hotValue) }}</span>
          <span v-if="detail.rankNum !== null && detail.rankNum !== undefined">
            当前平台内排名：#{{ detail.rankNum }}
          </span>
          <span v-if="detail.tags">标签：{{ detail.tags }}</span>
        </div>
      </div>

      <el-card class="summary-card" shadow="never">
        <template #header>
          <div class="summary-header">
            <span>热点简介</span>

            <div class="summary-tags">
              <el-tag
                v-if="hasAiSummary && isCrossPlatformSummary"
                type="warning"
                size="small"
              >
                跨平台分析
              </el-tag>

              <el-tag
                v-else-if="hasAiSummary"
                type="success"
                size="small"
              >
                AI生成
              </el-tag>

              <el-tag
                v-else
                type="info"
                size="small"
              >
                系统提示
              </el-tag>
            </div>
          </div>
        </template>

        <div
          v-if="isCrossPlatformSummary && relatedPlatformList.length"
          class="cross-platform-info"
        >
          <div class="cross-platform-row">
            <span class="cross-platform-label">关联平台：</span>
            <el-tag
              v-for="platform in relatedPlatformList"
              :key="platform"
              size="small"
              type="info"
              effect="plain"
            >
              {{ getPlatformLabel(platform) }}
            </el-tag>
          </div>

          <div
            v-if="otherRelatedHotspotIdList.length"
            class="cross-platform-row related-hotspot-row"
          >
            <span class="cross-platform-label">关联热点：</span>

            <span v-if="relatedLoading" class="related-loading-text">
              正在加载关联热点...
            </span>

            <div v-else class="related-hotspot-list">
              <button
                v-for="item in relatedHotspots"
                :key="item.id"
                type="button"
                class="related-hotspot-card"
                @click="goRelatedHotspot(item.id)"
              >
                <span class="related-platform">{{ getPlatformLabel(item.platform) }}</span>
                <span class="related-title">{{ cleanTitle(item.title) }}</span>
                <span class="related-meta">
                  <template v-if="item.rankNum !== null && item.rankNum !== undefined">
                    #{{ item.rankNum }}
                  </template>
                  <template v-if="item.hotValue !== null && item.hotValue !== undefined">
                    · {{ formatHotValue(item.hotValue) }}
                  </template>
                </span>
              </button>

              <button
                v-for="id in otherRelatedHotspotFallbackIds"
                :key="id"
                type="button"
                class="related-hotspot-card fallback"
                @click="goRelatedHotspot(id)"
              >
                <span class="related-platform">热点ID</span>
                <span class="related-title">{{ id }}</span>
                <span class="related-meta">点击查看详情</span>
              </button>
            </div>
          </div>
        </div>

        <div class="summary-content">
          <p
            v-for="(paragraph, index) in summaryParagraphs"
            :key="index"
            class="summary-paragraph"
          >
            {{ paragraph }}
          </p>
        </div>
      </el-card>

      <el-card class="chart-card" shadow="hover">
        <template #header>
          <span>趋势分析</span>
        </template>

        <div v-if="hasTrendData" ref="chartRef" class="chart"></div>
        <el-empty v-else description="暂无趋势数据" />
      </el-card>

      <el-card class="source-card" shadow="never">
        <template #header>
          <span>原始来源</span>
        </template>

        <el-button type="primary" :disabled="!detail.sourceUrl" @click="openSource">
          查看原始内容
        </el-button>
      </el-card>
    </div>

    <el-empty v-else description="未找到热点详情" />
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getHotspotDetail, getTrend } from '../api/hotspot'

const route = useRoute()
const router = useRouter()

const detail = ref(null)
const trend = ref({
  times: [],
  hotValues: [],
  rankValues: []
})
const chartRef = ref(null)
const relatedHotspots = ref([])
const relatedLoading = ref(false)
let chartInstance = null

const platformName = computed(() => {
  if (!detail.value || !detail.value.platform) return ''
  return getPlatformLabel(detail.value.platform)
})

const analysisType = computed(() => {
  if (!detail.value) return ''
  const value =
    detail.value.analysisType ||
    detail.value.analysis_type ||
    ''

  return String(value).trim()
})

const isCrossPlatformSummary = computed(() => {
  return analysisType.value === 'cross_platform'
})

const relatedPlatformList = computed(() => {
  if (!detail.value) return []

  const value =
    detail.value.relatedPlatforms ||
    detail.value.related_platforms ||
    ''

  return String(value)
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
})

const relatedHotspotIdList = computed(() => {
  if (!detail.value) return []

  const value =
    detail.value.relatedHotspotIds ||
    detail.value.related_hotspot_ids ||
    ''

  return String(value)
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
})

const currentHotspotId = computed(() => String(route.params.id || ''))

const otherRelatedHotspotIdList = computed(() => {
  const seen = new Set()

  return relatedHotspotIdList.value.filter(id => {
    const normalizedId = String(id)
    if (!normalizedId || normalizedId === currentHotspotId.value || seen.has(normalizedId)) {
      return false
    }

    seen.add(normalizedId)
    return true
  })
})

const otherRelatedHotspotFallbackIds = computed(() => {
  const loadedIds = new Set(relatedHotspots.value.map(item => String(item.id)))
  return otherRelatedHotspotIdList.value.filter(id => !loadedIds.has(String(id)))
})

const hasAiSummary = computed(() => {
  if (!detail.value) return false

  const text =
    detail.value.aiSummary ||
    detail.value.summary ||
    detail.value.ai_summary ||
    ''

  return String(text).trim().length > 0
})

const displaySummary = computed(() => {
  if (!detail.value) return '该热点信息正在加载中。'

  const aiText =
    detail.value.aiSummary ||
    detail.value.summary ||
    detail.value.ai_summary ||
    ''

  if (String(aiText).trim()) {
    return String(aiText).trim()
  }

  return genericSummary.value
})

const summaryParagraphs = computed(() => {
  return String(displaySummary.value || '')
    .split(/\n+/)
    .map(item => item.replace(/^[\s　]+/, '').trim())
    .filter(Boolean)
})

const hasTrendData = computed(() => {
  return (
    trend.value.times.length > 0 &&
    (trend.value.hotValues.length > 0 || trend.value.rankValues.length > 0)
  )
})

const genericSummary = computed(() => {
  if (!detail.value) {
    return '该热点信息正在加载中。'
  }

  const platform = platformName.value || '相关平台'

  const hasRank =
    detail.value.rankNum !== null &&
    detail.value.rankNum !== undefined &&
    detail.value.rankNum !== ''

  const hasHotValue =
    detail.value.hotValue !== null &&
    detail.value.hotValue !== undefined &&
    detail.value.hotValue !== ''

  const rankText = hasRank
    ? `当前位于第 ${detail.value.rankNum} 位`
    : '当前已进入热点列表'

  const hotText = hasHotValue
    ? `热度约为 ${formatHotValue(detail.value.hotValue)}`
    : '暂无明确热度数据'

  if (detail.value.isSpecial) {
    return `这个话题目前被${platform}放在较醒目的位置展示，通常代表平台认为它具有较高关注价值。由于这类内容不一定参与普通热榜排名，系统会单独记录它的出现情况，你可以通过下方趋势图或来源链接进一步了解。`
  }

  return `这个话题正在${platform}热榜中受到关注，${rankText}，${hotText}。系统暂时还没有生成详细解读，你可以先通过下方趋势图观察它的变化，或点击来源链接查看平台原始内容。`
})

async function loadRelatedHotspots() {
  relatedHotspots.value = []

  if (!isCrossPlatformSummary.value || otherRelatedHotspotIdList.value.length === 0) {
    return
  }

  relatedLoading.value = true

  try {
    const results = await Promise.all(
      otherRelatedHotspotIdList.value.map(async id => {
        try {
          const data = await getHotspotDetail(id)
          return data || { id }
        } catch (error) {
          console.warn(`关联热点 ${id} 加载失败：`, error)
          return null
        }
      })
    )

    relatedHotspots.value = results
      .filter(Boolean)
      .map((item, index) => ({
        ...item,
        id: item.id || otherRelatedHotspotIdList.value[index]
      }))
  } finally {
    relatedLoading.value = false
  }
}

async function loadDetail(id) {
  if (!id) return

  detail.value = null
  relatedHotspots.value = []
  trend.value = {
    times: [],
    hotValues: [],
    rankValues: []
  }

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  try {
    const detailRes = await getHotspotDetail(id)
    const trendRes = await getTrend(id)

    detail.value = detailRes

    if (
      trendRes &&
      Array.isArray(trendRes.times) &&
      Array.isArray(trendRes.hotValues) &&
      Array.isArray(trendRes.rankValues)
    ) {
      trend.value = {
        times: trendRes.times,
        hotValues: trendRes.hotValues,
        rankValues: trendRes.rankValues
      }
    } else {
      trend.value = {
        times: [],
        hotValues: [],
        rankValues: []
      }
    }

    await loadRelatedHotspots()
    await nextTick()
    initChart()
  } catch (error) {
    console.error('详情页加载失败：', error)
    detail.value = null
    relatedHotspots.value = []
    trend.value = {
      times: [],
      hotValues: [],
      rankValues: []
    }
  }
}

function goRelatedHotspot(id) {
  if (!id || String(id) === currentHotspotId.value) return
  router.push({ name: 'detail', params: { id } })
}

function goBack() {
  router.back()
}

function openSource() {
  if (detail.value && detail.value.sourceUrl) {
    window.open(detail.value.sourceUrl, '_blank')
  }
}

function cleanTitle(title) {
  if (!title) return ''
  return String(title).replace(/^#|#$/g, '')
}

function getPlatformLabel(platform) {
  if (platform === 'weibo') return '微博'
  if (platform === 'douyin') return '抖音'
  if (platform === 'bilibili') return 'B站'
  return platform || '未知平台'
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

function formatTooltipHotValue(value) {
  if (value === null || value === undefined || value === '') return '暂无'
  return formatHotValue(value)
}

function resizeChart() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

function initChart() {
  if (!chartRef.value || !hasTrendData.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      formatter(params) {
        if (!params || !params.length) return ''

        const time = params[0].axisValue || ''
        let rankText = '暂无'
        let hotText = '暂无'

        params.forEach(item => {
          if (item.seriesName === '排名') {
            rankText =
              item.data === null || item.data === undefined ? '暂无' : `#${item.data}`
          }
          if (item.seriesName === '热度') {
            hotText = formatTooltipHotValue(item.data)
          }
        })

        return `
          <div style="line-height: 1.8;">
            <div style="margin-bottom: 6px; font-weight: 600;">${time}</div>
            <div>排名：${rankText}</div>
            <div>热度：${hotText}</div>
          </div>
        `
      }
    },
    legend: {
      top: 0,
      data: ['排名', '热度']
    },
    grid: {
      left: 70,
      right: 80,
      top: 50,
      bottom: 70
    },
    xAxis: {
      type: 'category',
      data: trend.value.times,
      boundaryGap: false,
      axisLabel: {
        rotate: 30
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '排名',
        inverse: true,
        min: 1,
        max: 50,
        interval: 5,
        axisLine: {
          show: true
        },
        splitLine: {
          show: true
        }
      },
      {
        type: 'value',
        name: '热度',
        position: 'right',
        axisLine: {
          show: true
        },
        splitLine: {
          show: false
        },
        axisLabel: {
          formatter(value) {
            if (value >= 100000000) return (value / 100000000).toFixed(1) + '亿'
            if (value >= 10000) return (value / 10000).toFixed(0) + '万'
            return value
          }
        }
      }
    ],
    series: [
      {
        name: '排名',
        type: 'line',
        yAxisIndex: 0,
        data: trend.value.rankValues,
        smooth: true,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 6
      },
      {
        name: '热度',
        type: 'line',
        yAxisIndex: 1,
        data: trend.value.hotValues,
        smooth: true,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 6
      }
    ]
  })

  window.removeEventListener('resize', resizeChart)
  window.addEventListener('resize', resizeChart)
}

watch(
  () => route.params.id,
  id => {
    loadDetail(id)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.detail-page {
  max-width: 960px;
  margin: 30px auto;
  padding: 20px;
}

.top-bar {
  margin-bottom: 20px;
}

.title-block {
  margin-bottom: 20px;
}

.title-block h1 {
  margin: 0 0 12px;
  font-size: 30px;
  color: #303133;
  line-height: 1.4;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  color: #606266;
}

.summary-card,
.chart-card,
.source-card {
  margin-top: 20px;
}

.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.summary-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cross-platform-info {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  color: #606266;
  font-size: 14px;
}

.cross-platform-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  line-height: 1.7;
}

.cross-platform-row + .cross-platform-row {
  margin-top: 6px;
}

.cross-platform-label {
  color: #303133;
  font-weight: 600;
}

.related-hotspot-row {
  align-items: flex-start;
}

.related-loading-text {
  color: #909399;
}

.related-hotspot-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.related-hotspot-card {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #ffffff;
  cursor: pointer;
  text-align: left;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.related-hotspot-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.12);
  transform: translateY(-1px);
}

.related-hotspot-card.fallback {
  border-style: dashed;
}

.related-platform {
  color: #409eff;
  font-weight: 600;
  white-space: nowrap;
}

.related-title {
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.related-meta {
  color: #909399;
  font-size: 13px;
  white-space: nowrap;
}

.summary-content {
  color: #303133;
  font-size: 15px;
}

.summary-paragraph {
  margin: 0;
  line-height: 1.9;
  text-indent: 2em;
}

.summary-paragraph + .summary-paragraph {
  margin-top: 4px;
}

.chart {
  height: 420px;
}
</style>