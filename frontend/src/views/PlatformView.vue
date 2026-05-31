<template>
  <div class="app-container page-stack platform-page" :class="`platform-page--${platform}`">
    <section class="page-hero platform-hero">
      <div class="platform-hero__header">
        <div>
          <span class="page-hero__eyebrow">{{ platformMeta.label }} Hotspot Board</span>
          <h1 class="page-hero__title">{{ platformMeta.label }}热点榜单</h1>
          <p class="page-hero__subtitle">
            支持查看当前榜单与今日榜单；当切换到指定日期时，页面会继续通过现有历史榜单接口进行兼容展示，但仍保持
            `daily` 模式，不再使用 `history` 作为平台页模式参数。
          </p>
        </div>

        <div class="platform-hero__highlight">
          <PlatformPill :platform="platform" />
          <strong>{{ mode === 'current' ? '当前榜单' : '今日 / 历史日榜' }}</strong>
          <span>{{ platformMeta.heatLabel }}口径保持与平台返回字段一致</span>
        </div>
      </div>

      <div class="platform-hero-metrics">
        <div class="platform-hero-metric">
          <span>当前模式</span>
          <strong>{{ mode === 'current' ? '当前榜单' : '今日榜单' }}</strong>
        </div>
        <div class="platform-hero-metric">
          <span>{{ mode === 'current' ? '普通热点数' : '榜单结果数' }}</span>
          <strong>{{ mode === 'current' ? rankedCurrentHotspots.length : activeDailyList.length }}</strong>
        </div>
        <div class="platform-hero-metric">
          <span>{{ mode === 'current' ? '特殊项数量' : '统计日期' }}</span>
          <strong>{{ mode === 'current' ? currentSpecialHotspots.length : selectedDate }}</strong>
        </div>
        <div class="platform-hero-metric">
          <span>{{ mode === 'current' ? '最新抓取时间' : '指标口径' }}</span>
          <strong>{{ mode === 'current' ? latestTimeText : platformMeta.heatLabel }}</strong>
        </div>
      </div>
    </section>

    <section class="page-card page-card--strong platform-toolbar">
      <div class="control-bar">
        <div class="chip-group">
          <button
            v-for="meta in platformSwitches"
            :key="meta.key"
            type="button"
            class="chip-button"
            :class="{ active: platform === meta.key }"
            @click="switchPlatform(meta.key)"
          >
            {{ meta.label }}
          </button>
        </div>

        <div class="chip-group platform-toolbar__switch">
          <button
            type="button"
            class="chip-button"
            :class="{ active: mode === 'current' }"
            @click="switchMode('current')"
          >
            当前榜单
          </button>
          <button
            type="button"
            class="chip-button"
            :class="{ active: mode === 'daily' }"
            @click="switchMode('daily')"
          >
            今日榜单
          </button>
        </div>

        <div v-if="mode === 'daily'" class="platform-toolbar__date">
          <el-date-picker
            v-model="selectedDate"
            type="date"
            value-format="YYYY-MM-DD"
            :clearable="false"
            placeholder="选择日期"
          />
          <el-button type="primary" @click="applyDate">查询日期</el-button>
        </div>
      </div>
    </section>

    <RequestState
      compact
      :loading="loading"
      :error="error"
      :empty="emptyState"
      :empty-description="emptyDescription"
      @retry="refreshByMode"
    >
      <template v-if="mode === 'current'">
        <section v-if="currentSpecialHotspots.length" class="table-card platform-special-panel">
          <div class="section-head platform-section-head">
            <div>
              <h2 class="section-title">置顶 / 特殊展示项</h2>
              <p class="section-subtitle">单独展示平台特殊项，避免与普通排名混在一起。</p>
            </div>
          </div>

          <div class="platform-special-list">
            <article
              v-for="item in currentSpecialHotspots"
              :key="getHotspotId(item)"
              class="platform-special-item"
              @click="goDetail(getHotspotId(item))"
            >
              <div class="platform-special-item__main">
                <PlatformPill :platform="platform" />
                <strong>{{ cleanTitle(item.title) }}</strong>
                <div class="platform-special-item__meta">
                  <span>更新时间：{{ formatDateTime(getHotspotTime(item)) }}</span>
                  <span v-if="normalizeTag(item.tags, item.title)">标签：{{ normalizeTag(item.tags, item.title) }}</span>
                </div>
              </div>
              <el-button type="warning" plain @click.stop="goDetail(getHotspotId(item))">查看详情</el-button>
            </article>
          </div>
        </section>

        <section class="table-card platform-list-panel">
          <div class="section-head platform-section-head">
            <div>
              <h2 class="section-title">当前热点列表</h2>
              <p class="section-subtitle">按榜单行方式展示平台最新快照中的热点结果，默认每页 25 条。</p>
            </div>
          </div>

          <div class="platform-list">
            <article
              v-for="item in pagedCurrentHotspots"
              :key="getHotspotId(item)"
              class="platform-item"
              @click="goDetail(getHotspotId(item))"
            >
              <div class="platform-item__rank" :class="{ top: Number(item.rankNum) <= 3 }">
                {{ item.rankNum ?? '-' }}
              </div>

              <div class="platform-item__main">
                <div class="platform-item__title-row">
                  <h3>{{ cleanTitle(item.title) }}</h3>
                  <el-tag v-if="normalizeTag(item.tags, item.title)" size="small" effect="plain">
                    {{ normalizeTag(item.tags, item.title) }}
                  </el-tag>
                </div>

                <div class="platform-item__meta">
                  <PlatformPill :platform="platform" />
                  <span>{{ platformMeta.heatLabel }}：{{ formatHotValue(item.hotValue, platform) }}</span>
                  <span>抓取时间：{{ formatDateTime(getHotspotTime(item)) }}</span>
                </div>
              </div>

              <el-button type="primary" plain @click.stop="goDetail(getHotspotId(item))">详情</el-button>
            </article>
          </div>

          <div v-if="rankedCurrentHotspots.length > pageSize" class="platform-pagination">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              layout="total, prev, pager, next"
              :total="rankedCurrentHotspots.length"
              background
            />
          </div>
        </section>
      </template>

      <template v-else>
        <section class="table-card platform-list-panel">
          <div class="section-head platform-section-head">
            <div>
              <h2 class="section-title">{{ isTodaySelected ? `${platformMeta.label}今日榜单` : `${selectedDate} 历史榜单` }}</h2>
              <p class="section-subtitle">
                {{
                  isTodaySelected
                    ? '今日榜单按热度峰值展示；若选择历史日期，则兼容读取归档榜单数据。'
                    : '当前列表来自后端历史榜单接口，继续保留原有业务能力。'
                }}
              </p>
            </div>
          </div>

          <div class="platform-list">
            <article
              v-for="(item, index) in pagedDailyList"
              :key="getHotspotId(item, `${platform}-${index}`)"
              class="platform-item"
              @click="goDetail(getHotspotId(item))"
            >
              <div class="platform-item__rank" :class="{ top: getDisplayRank(index) <= 3 }">
                {{ getDisplayRank(index) }}
              </div>

              <div class="platform-item__main">
                <div class="platform-item__title-row">
                  <h3>{{ cleanTitle(item.title) }}</h3>
                  <el-tag v-if="item.isSpecial" type="warning" size="small">特殊项</el-tag>
                </div>

                <div class="platform-item__meta">
                  <PlatformPill :platform="platform" />
                  <span>{{ isTodaySelected ? `今日${platformMeta.heatLabel}` : `最高${platformMeta.heatLabel}` }}：{{ formatHotValue(getHotValue(item), platform) }}</span>
                  <span>最佳排名：{{ item.bestRankNum ?? '暂无' }}</span>
                  <span v-if="item.appearCount !== undefined">出现次数：{{ item.appearCount }}</span>
                  <span v-if="item.durationMinutes !== undefined">持续时长：{{ formatDurationMinutes(item.durationMinutes) }}</span>
                </div>
              </div>

              <el-button type="primary" plain @click.stop="goDetail(getHotspotId(item))">详情</el-button>
            </article>
          </div>

          <div v-if="activeDailyList.length > pageSize" class="platform-pagination">
            <el-pagination
              v-model:current-page="dailyPage"
              :page-size="pageSize"
              layout="total, prev, pager, next"
              :total="activeDailyList.length"
              background
            />
          </div>
        </section>
      </template>
    </RequestState>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RequestState from '../components/RequestState.vue'
import PlatformPill from '../components/PlatformPill.vue'
import { getDailyTop, getHistoryHotspots, getHotspotsByPlatform } from '../api/hotspot'
import {
  PLATFORM_ORDER,
  cleanTitle,
  formatDateTime,
  formatDurationMinutes,
  formatHotValue,
  getHotValue,
  getHotspotId,
  getHotspotTime,
  getPlatformMeta,
  getToday,
  normalizeTag
} from '../utils/hotspot'

const route = useRoute()
const router = useRouter()

const platform = ref('weibo')
const mode = ref('current')
const selectedDate = ref(getToday())
const loading = ref(false)
const error = ref('')

const currentHotspots = ref([])
const dailyHotspots = ref([])
const historyHotspots = ref([])

const currentPage = ref(1)
const dailyPage = ref(1)
const pageSize = 25

const platformSwitches = PLATFORM_ORDER.map(getPlatformMeta)

const platformMeta = computed(() => getPlatformMeta(platform.value))
const currentSpecialHotspots = computed(() => currentHotspots.value.filter(item => item.isSpecial))
const rankedCurrentHotspots = computed(() => currentHotspots.value.filter(item => !item.isSpecial))
const isTodaySelected = computed(() => selectedDate.value === getToday())
const activeDailyList = computed(() => (isTodaySelected.value ? dailyHotspots.value : historyHotspots.value))
const latestTimeText = computed(() => {
  const latest = [...currentHotspots.value]
    .map(getHotspotTime)
    .filter(Boolean)
    .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0]
  return latest ? formatDateTime(latest) : '暂无'
})

const pagedCurrentHotspots = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return rankedCurrentHotspots.value.slice(start, start + pageSize)
})

const pagedDailyList = computed(() => {
  const start = (dailyPage.value - 1) * pageSize
  return activeDailyList.value.slice(start, start + pageSize)
})

const emptyState = computed(() => !error.value && !loading.value && (mode.value === 'current' ? currentHotspots.value.length === 0 : activeDailyList.value.length === 0))
const emptyDescription = computed(() =>
  mode.value === 'current' ? '当前榜单暂无数据' : isTodaySelected.value ? '今日榜单暂无数据' : '该日期暂无历史榜单数据'
)

function syncRouteState() {
  const nextPlatform = String(route.params.platform || 'weibo')
  platform.value = PLATFORM_ORDER.includes(nextPlatform) ? nextPlatform : 'weibo'

  const nextMode = String(route.query.mode || 'current')
  mode.value = ['current', 'daily'].includes(nextMode) ? nextMode : 'current'

  selectedDate.value = String(route.query.date || getToday())
}

async function loadCurrent() {
  loading.value = true
  error.value = ''

  try {
    const result = await getHotspotsByPlatform(platform.value)
    currentHotspots.value = Array.isArray(result) ? result : []
    currentPage.value = 1
  } catch (requestError) {
    error.value = requestError?.message || `${platformMeta.value.label}当前榜单加载失败`
    currentHotspots.value = []
  } finally {
    loading.value = false
  }
}

async function loadDaily() {
  loading.value = true
  error.value = ''

  try {
    if (isTodaySelected.value) {
      const result = await getDailyTop(platform.value, 500)
      dailyHotspots.value = Array.isArray(result) ? result : []
      historyHotspots.value = []
    } else {
      const result = await getHistoryHotspots(platform.value, selectedDate.value)
      historyHotspots.value = Array.isArray(result) ? result : []
      dailyHotspots.value = []
    }

    dailyPage.value = 1
  } catch (requestError) {
    error.value = requestError?.message || `${platformMeta.value.label}日榜加载失败`
    dailyHotspots.value = []
    historyHotspots.value = []
  } finally {
    loading.value = false
  }
}

async function refreshByMode() {
  if (mode.value === 'current') {
    await loadCurrent()
    return
  }
  await loadDaily()
}

function pushRoute(queryOverrides = {}) {
  router.replace({
    name: 'platform',
    params: { platform: platform.value },
    query: {
      mode: mode.value,
      ...(mode.value === 'daily' ? { date: selectedDate.value } : {}),
      ...queryOverrides
    }
  })
}

function switchPlatform(nextPlatform) {
  if (platform.value === nextPlatform) return
  platform.value = nextPlatform
  pushRoute()
}

function switchMode(nextMode) {
  if (mode.value === nextMode) return
  mode.value = nextMode
  pushRoute()
}

function applyDate() {
  mode.value = 'daily'
  pushRoute()
}

function getDisplayRank(index) {
  return (dailyPage.value - 1) * pageSize + index + 1
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

watch(
  () => route.fullPath,
  async () => {
    syncRouteState()
    await refreshByMode()
  },
  { immediate: true }
)
</script>

<style scoped>
.platform-hero__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.platform-hero__highlight {
  min-width: 240px;
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(135, 160, 206, 0.12);
  display: grid;
  gap: 10px;
}

.platform-hero__highlight strong {
  font-size: 18px;
  line-height: 1.35;
}

.platform-hero__highlight span {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.platform-hero-metrics {
  margin-top: 24px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.platform-hero-metric {
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(135, 160, 206, 0.16);
}

.platform-hero-metric span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.platform-hero-metric strong {
  display: block;
  margin-top: 10px;
  font-size: 22px;
  line-height: 1.2;
}

.platform-toolbar {
  padding: 18px 22px;
}

.platform-toolbar__switch {
  margin-left: auto;
}

.platform-toolbar__date {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.platform-section-head {
  margin-bottom: 18px;
}

.platform-special-panel,
.platform-list-panel {
  padding: 22px;
}

.platform-special-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.platform-special-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 247, 237, 0.96), rgba(255, 241, 242, 0.94));
  border: 1px dashed rgba(255, 134, 76, 0.28);
  cursor: pointer;
}

.platform-special-item__main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.platform-special-item__main strong {
  font-size: 18px;
  line-height: 1.5;
}

.platform-special-item__meta,
.platform-item__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.platform-list {
  display: flex;
  flex-direction: column;
}

.platform-item {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 14px 4px;
  border-bottom: 1px solid rgba(135, 160, 206, 0.12);
  cursor: pointer;
  transition: transform 0.2s ease;
}

.platform-item:last-child {
  border-bottom: 0;
}

.platform-item:hover {
  transform: translateX(4px);
}

.platform-item__rank {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(226, 234, 247, 0.94);
  color: var(--text-secondary);
  font-weight: 800;
}

.platform-item__rank.top {
  color: #fff;
  box-shadow: 0 10px 22px rgba(255, 122, 69, 0.24);
}

.platform-page--weibo .platform-item__rank.top {
  background: linear-gradient(135deg, #ef4444, #fb7185);
}

.platform-page--douyin .platform-item__rank.top {
  background: linear-gradient(135deg, #111827, #0f766e);
}

.platform-page--bilibili .platform-item__rank.top {
  background: linear-gradient(135deg, #38bdf8, #6366f1);
}

.platform-item__main {
  min-width: 0;
}

.platform-item__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.platform-item__title-row h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.5;
}

.platform-item__meta {
  margin-top: 8px;
}

.platform-pagination {
  margin-top: 22px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1080px) {
  .platform-hero__header {
    flex-direction: column;
  }

  .platform-hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .platform-item,
  .platform-special-item {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .platform-hero-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
