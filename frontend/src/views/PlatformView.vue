<template>
  <div class="platform-page">
    <div class="top-actions">
      <el-button @click="goHome">返回首页</el-button>
    </div>

    <div class="page-header">
      <h1>{{ platformLabel }}热点</h1>
      <p>{{ pageDesc }}</p>
    </div>

    <div class="toolbar">
      <el-radio-group v-model="mode" @change="handleModeChange">
        <el-radio-button label="current">当前榜单</el-radio-button>
        <el-radio-button label="daily">今日榜单</el-radio-button>
      </el-radio-group>

      <div v-if="mode === 'daily'" class="daily-tools">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          :clearable="false"
        />
        <el-button type="primary" @click="loadDaily">查询</el-button>
      </div>
    </div>

    <div v-loading="loading">
      <!-- 当前榜单 -->
      <template v-if="mode === 'current'">
        <div v-if="specialHotspots.length" class="section-block">
          <div class="section-title">置顶热点</div>

          <div
            v-for="item in specialHotspots"
            :key="'special-' + item.id"
            class="hot-card special-card"
            @click="goDetail(item.id)"
          >
            <div class="hot-main">
              <div class="hot-title">
                {{ cleanTitle(item.title) }}
              </div>

              <div class="hot-meta">
                <span v-if="normalizeTag(item.tags, item.title) !== '无'">
                  标签：{{ normalizeTag(item.tags, item.title) }}
                </span>
                <span>热度：{{ formatHotValue(item.hotValue) }}</span>
                <span v-if="item.crawlTime">抓取时间：{{ item.crawlTime }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="section-block">
          <div class="section-title">当前榜单</div>

          <div
            v-for="item in normalHotspots"
            :key="item.id"
            class="hot-card"
            @click="goDetail(item.id)"
          >
            <div class="rank-badge">
              {{ item.rankNum ?? '-' }}
            </div>

            <div class="hot-main">
              <div class="hot-title">{{ cleanTitle(item.title) }}</div>

              <div class="hot-meta">
                <span>热度：{{ formatHotValue(item.hotValue) }}</span>
                <span v-if="normalizeTag(item.tags, item.title) !== '无'">
                  标签：{{ normalizeTag(item.tags, item.title) }}
                </span>
                <span v-if="item.crawlTime">抓取时间：{{ item.crawlTime }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 今日/指定日期榜单 -->
      <template v-else>
        <div class="section-block">
          <div class="section-title">{{ dailyTitle }}</div>

          <div
            v-if="!isSelectedToday && dailySpecial.length"
            class="sub-section-title"
          >
            置顶热点
          </div>

          <div
            v-for="item in dailySpecial"
            :key="'daily-special-' + getItemId(item)"
            class="hot-card special-card"
            @click="goDetail(getItemId(item))"
          >
            <div class="hot-main">
              <div class="hot-title">{{ cleanTitle(item.title) }}</div>

              <div class="hot-meta">
                <span>当日最高热度：{{ formatHotValue(item.maxHotValue) }}</span>
                <span>当日最佳排名：{{ item.bestRankNum ?? '暂无' }}</span>
                <span>持续时长：{{ item.durationMinutes ?? 0 }} 分钟</span>
              </div>
            </div>
          </div>

          <div
            v-if="!isSelectedToday && dailyNormal.length"
            class="sub-section-title"
          >
            正常热点
          </div>

          <div
            v-for="(item, index) in dailyNormal"
            :key="'daily-' + getItemId(item)"
            class="hot-card"
            @click="goDetail(getItemId(item))"
          >
            <div class="rank-badge">
              {{ index + 1 }}
            </div>

            <div class="hot-main">
              <div class="hot-title">{{ cleanTitle(item.title) }}</div>

              <div class="hot-meta">
                <span>
                  {{ isSelectedToday ? '今日最高热度' : '当日最高热度' }}：
                  {{ formatHotValue(item.maxHotValue) }}
                </span>
                <span v-if="!isSelectedToday">
                  当日最佳排名：{{ item.bestRankNum ?? '暂无' }}
                </span>
                <span v-if="!isSelectedToday">
                  持续时长：{{ item.durationMinutes ?? 0 }} 分钟
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <el-empty
        v-if="!loading && mode === 'current' && !specialHotspots.length && !normalHotspots.length"
        description="暂无当前榜单数据"
      />

      <el-empty
        v-if="!loading && mode === 'daily' && !dailyList.length"
        :description="isSelectedToday ? '暂无今日榜单数据' : '该日期暂无历史榜单数据'"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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

const hotspots = ref([])
const dailyHotspots = ref([])
const historyHotspots = ref([])
const selectedDate = ref(route.query.date || getToday())

/**
 * 后续新增平台时，优先在这里补中文名。
 */
const platformNameMap = {
  weibo: '微博',
  douyin: '抖音',
  bilibili: 'B站',
  baidu: '百度'
}

const platformLabel = computed(() => {
  return platformNameMap[platform.value] || platform.value
})

const isSelectedToday = computed(() => selectedDate.value === getToday())

const pageDesc = computed(() => {
  if (mode.value === 'current') {
    return `查看${platformLabel.value}平台当前最新一轮热点榜单`
  }

  if (isSelectedToday.value) {
    return `查看${platformLabel.value}平台今日热点榜单`
  }

  return `查看${platformLabel.value}平台 ${selectedDate.value} 的历史榜单`
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

const dailyList = computed(() =>
  isSelectedToday.value ? dailyHotspots.value : historyHotspots.value
)

const dailySpecial = computed(() =>
  dailyList.value.filter(item => item.isSpecial)
)

const dailyNormal = computed(() =>
  dailyList.value.filter(item => !item.isSpecial)
)

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

  return value || '无'
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

function goHome() {
  router.push('/')
}

function goDetail(id) {
  if (!id) return
  router.push(`/detail/${id}`)
}

async function loadCurrent() {
  loading.value = true

  try {
    const result = await getHotspotsByPlatform(platform.value)
    hotspots.value = Array.isArray(result) ? result : []
  } finally {
    loading.value = false
  }
}

async function loadDaily() {
  loading.value = true

  try {
    router.replace({
      path: `/platform/${platform.value}`,
      query: {
        mode: 'daily',
        date: selectedDate.value
      }
    })

    if (isSelectedToday.value) {
      dailyHotspots.value = await getDailyTop(platform.value, 200)
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

async function handleModeChange() {
  const query = mode.value === 'daily'
    ? {
        mode: mode.value,
        date: selectedDate.value
      }
    : {
        mode: mode.value
      }

  router.replace({
    path: `/platform/${platform.value}`,
    query
  })

  if (mode.value === 'current') {
    await loadCurrent()
  } else {
    await loadDaily()
  }
}

onMounted(async () => {
  if (!['current', 'daily'].includes(mode.value)) {
    mode.value = 'daily'
  }

  if (mode.value === 'current') {
    await loadCurrent()
  } else {
    await loadDaily()
  }
})
</script>

<style scoped>
.platform-page {
  max-width: 1100px;
  margin: 30px auto;
  padding: 20px;
}

.top-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0 0 8px;
  font-size: 30px;
  color: #303133;
}

.page-header p {
  margin: 0;
  color: #606266;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.daily-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-block {
  margin-bottom: 28px;
}

.section-title {
  margin-bottom: 14px;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.sub-section-title {
  margin: 18px 0 12px;
  font-size: 16px;
  font-weight: 600;
  color: #606266;
}

.hot-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  margin-bottom: 14px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.hot-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.08);
}

.special-card {
  border-color: #f56c6c;
  background: #fff7f7;
}

.rank-badge {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.hot-main {
  flex: 1;
}

.hot-title {
  font-size: 18px;
  color: #303133;
  line-height: 1.5;
  margin-bottom: 10px;
}

.hot-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: #606266;
  font-size: 14px;
}
</style>