<template>
  <div class="app-container page-stack">
    <section class="page-hero history-hero">
      <span class="page-hero__eyebrow">历史观察</span>
      <h1 class="page-hero__title">历史榜单查询</h1>
      <p class="page-hero__subtitle">
        基于已归档的日榜摘要数据，支持按平台、日期和关键词回看历史热点表现，帮助从时间维度观察话题变化。
      </p>
    </section>

    <section class="page-card page-card--strong history-toolbar">
      <div class="control-bar">
        <div class="history-toolbar__filters">
          <el-select v-model="filters.platform" placeholder="选择平台" @change="applyFilters">
            <el-option
              v-for="option in platformOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>

          <el-date-picker
            v-model="filters.date"
            type="date"
            value-format="YYYY-MM-DD"
            :clearable="false"
            placeholder="选择日期"
            @change="applyFilters"
          />

          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="按关键词过滤历史热点"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
        </div>

        <div class="history-toolbar__meta">
          <span class="history-toolbar__meta-item">统计日期：{{ filters.date }}</span>
          <span class="history-toolbar__meta-item">结果数：{{ filteredList.length }}</span>
        </div>
      </div>
    </section>

    <RequestState
      compact
      :loading="loading"
      :error="error"
      :empty="!loading && !error && filteredList.length === 0"
      empty-description="该日期下暂无可展示的历史热点数据"
      @retry="loadHistory"
    >
      <section class="table-card history-panel">
        <div class="section-head history-section-head">
          <div>
            <h2 class="section-title">历史热点列表</h2>
            <p class="section-subtitle">当平台选择“全部”时，页面会统一汇总微博、抖音、B站的归档结果。</p>
          </div>
        </div>

        <div class="history-list">
          <article
            v-for="item in pagedList"
            :key="getHotspotId(item, `${item.platform}-${item.title}`)"
            class="history-item"
            @click="goDetail(getHotspotId(item))"
          >
            <div class="history-item__main">
              <div class="history-item__title-row">
                <PlatformPill :platform="item.platform" />
                <h3>{{ cleanTitle(item.title) }}</h3>
                <el-tag v-if="item.isSpecial" type="warning" size="small">特殊项</el-tag>
              </div>

              <div class="history-item__meta">
                <span>{{ filters.date }}</span>
                <span>最佳排名：{{ item.bestRankNum ?? '暂无' }}</span>
                <span>{{ getPlatformHeatLabel(item.platform) === '排序值' ? '最高排序值' : '最高热度' }}：{{ formatHotValue(item.maxHotValue, item.platform) }}</span>
                <span>出现次数：{{ item.appearCount ?? '暂无' }}</span>
                <span>持续时长：{{ formatDurationMinutes(item.durationMinutes) }}</span>
              </div>
            </div>

            <el-button type="primary" plain @click.stop="goDetail(getHotspotId(item))">查看详情</el-button>
          </article>
        </div>

        <div v-if="filteredList.length > pageSize" class="history-pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            layout="total, prev, pager, next"
            :total="filteredList.length"
            background
          />
        </div>
      </section>
    </RequestState>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PlatformPill from '../components/PlatformPill.vue'
import RequestState from '../components/RequestState.vue'
import { getHistoryHotspots } from '../api/hotspot'
import {
  PLATFORM_ORDER,
  cleanTitle,
  formatDurationMinutes,
  formatHotValue,
  getHotspotId,
  getPlatformHeatLabel,
  getPlatformLabel,
  getYesterday,
  sortHistoryList
} from '../utils/hotspot'

const route = useRoute()
const router = useRouter()

const platformOptions = [
  { value: 'all', label: '全部平台' },
  ...PLATFORM_ORDER.map(platform => ({
    value: platform,
    label: getPlatformLabel(platform)
  }))
]

const filters = reactive({
  platform: 'all',
  date: getYesterday(),
  keyword: ''
})

const loading = ref(false)
const error = ref('')
const historyList = ref([])
const page = ref(1)
const pageSize = 25

const filteredList = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  if (!keyword) return historyList.value

  return historyList.value.filter(item => String(item?.title || '').toLowerCase().includes(keyword))
})

const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredList.value.slice(start, start + pageSize)
})

function syncFiltersFromRoute() {
  filters.platform = String(route.query.platform || 'all')
  filters.date = String(route.query.date || getYesterday())
  filters.keyword = String(route.query.keyword || '')
}

async function loadHistory() {
  loading.value = true
  error.value = ''

  try {
    const platforms = filters.platform === 'all' ? PLATFORM_ORDER : [filters.platform]
    const results = await Promise.all(platforms.map(platform => getHistoryHotspots(platform, filters.date)))

    const merged = results.flatMap((list, index) => {
      const platform = platforms[index]
      return (Array.isArray(list) ? list : []).map(item => ({
        ...item,
        platform: item.platform || platform
      }))
    })

    historyList.value = sortHistoryList(merged)
    page.value = 1
  } catch (requestError) {
    error.value = requestError?.message || '历史榜单加载失败，请稍后重试'
    historyList.value = []
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  router.replace({
    name: 'history',
    query: {
      platform: filters.platform,
      date: filters.date,
      keyword: filters.keyword || undefined
    }
  })
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

watch(
  () => route.fullPath,
  async () => {
    syncFiltersFromRoute()
    await loadHistory()
  },
  { immediate: true }
)
</script>

<style scoped>
.history-toolbar {
  padding: 20px 22px;
}

.history-toolbar__filters {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex: 1;
}

.history-toolbar__filters > * {
  min-width: 180px;
}

.history-toolbar__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.history-toolbar__meta-item {
  padding: 10px 12px;
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(135, 160, 206, 0.12);
}

.history-panel {
  padding: 22px;
}

.history-section-head {
  margin-bottom: 14px;
}

.history-list {
  display: flex;
  flex-direction: column;
}

.history-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 15px 4px;
  border-bottom: 1px solid rgba(135, 160, 206, 0.12);
  cursor: pointer;
  transition: transform 0.2s ease;
}

.history-item:last-child {
  border-bottom: 0;
}

.history-item:hover {
  transform: translateX(4px);
}

.history-item__main {
  min-width: 0;
}

.history-item__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.history-item__title-row h3 {
  margin: 0;
  font-size: 18px;
}

.history-item__meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.history-pagination {
  margin-top: 22px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .history-item {
    grid-template-columns: 1fr;
  }
}
</style>
