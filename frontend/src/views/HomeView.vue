<template>
  <div class="home-page">
    <div class="header">
      <h1>热点聚合分析器</h1>
      <p>跨平台热点数据展示与分析</p>

      <div class="search-box">
        <el-input
          v-model="keyword"
          placeholder="请输入热点关键词，例如：广州"
          size="large"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 平台统计卡片：以后新增平台，只改 platformConfigs -->
    <el-row :gutter="20" class="stat-row">
      <el-col
        v-for="platform in platforms"
        :key="platform.key"
        :xs="24"
        :sm="12"
        :md="8"
      >
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-title">{{ platform.name }}今日热点总数</div>
            <div class="stat-value">{{ platform.count }}</div>
            <div class="stat-tip">统计今天进入榜单的不同热点数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 平台 Top 榜：微博 / 抖音 / B站 自动循环展示 -->
    <el-row :gutter="20" class="platform-row">
      <el-col
        v-for="platform in platforms"
        :key="platform.key"
        :xs="24"
        :md="12"
        :lg="8"
      >
        <el-card shadow="hover" class="platform-card">
          <template #header>
            <div class="card-header">
              <div>
                <span>{{ platform.name }}今日 Top10</span>
                <div class="platform-desc">{{ platform.desc }}</div>
              </div>

              <el-button
                type="primary"
                link
                @click="goPlatform(platform.key, 'daily')"
              >
                查看今日全部热点
              </el-button>
            </div>
          </template>

          <div v-loading="platform.loading">
            <!-- 目前只有微博需要展示置顶热点，后续平台有置顶也可以打开 showPinned -->
            <div
              v-if="platform.showPinned && platform.pinned"
              class="pinned-block"
              @click="goDetail(platform.pinned.id)"
            >
              <div class="pinned-left">
                <el-tag type="danger" effect="dark" round>置顶</el-tag>
              </div>

              <div class="pinned-content">
                <div class="pinned-title">
                  {{ cleanTitle(platform.pinned.title) }}
                </div>
                <div class="pinned-meta">
                  <span>
                    标签：{{ normalizeTag(platform.pinned.tags, platform.pinned.title) }}
                  </span>
                </div>
              </div>
            </div>

            <div v-if="platform.dailyTop.length > 0">
              <div
                v-for="(item, index) in platform.dailyTop"
                :key="getItemId(item, platform.key, index)"
                class="hot-item"
                @click="goDetail(getItemId(item, platform.key, index))"
              >
                <span class="rank">{{ index + 1 }}</span>
                <span class="title">{{ cleanTitle(item.title) }}</span>
                <span class="hot">{{ formatHotValue(getHotValue(item)) }}</span>
              </div>
            </div>

            <el-empty v-else description="暂无数据" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getPlatformStats,
  getDailyTop,
  getHotspotsByPlatform
} from '../api/hotspot'

const router = useRouter()

/**
 * 后续如果要新增平台，优先改这里。
 * 例如接入百度热搜，就加：
 * { key: 'baidu', name: '百度', desc: '百度热搜榜', showPinned: false }
 */
const platformConfigs = [
  {
    key: 'weibo',
    name: '微博',
    desc: '微博热搜榜',
    showPinned: true
  },
  {
    key: 'douyin',
    name: '抖音',
    desc: '抖音热榜',
    showPinned: false
  },
  {
    key: 'bilibili',
    name: 'B站',
    desc: 'B站热门榜',
    showPinned: false
  }
]

const platforms = ref(
  platformConfigs.map(item => ({
    ...item,
    count: 0,
    dailyTop: [],
    pinned: null,
    loading: false
  }))
)

const keyword = ref('')

const handleSearch = () => {
  const value = keyword.value.trim()
  if (!value) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  router.push({
    path: '/search',
    query: {
      keyword: value
    }
  })
}

const goPlatform = (platform, mode = 'current') => {
  router.push({
    path: `/platform/${platform}`,
    query: {
      mode
    }
  })
}

const goDetail = (id) => {
  if (!id) return
  router.push(`/detail/${id}`)
}

const cleanTitle = (title) => {
  if (!title) return ''
  return String(title).replace(/^#|#$/g, '')
}

const normalizeTag = (tag, title = '') => {
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

const getHotValue = (item) => {
  return item.maxHotValue ?? item.hotValue ?? item.hot_value
}

const getItemId = (item, platformKey = '', index = 0) => {
  return item.id ?? item.hotspotId ?? item.hotspot_id ?? `${platformKey}-${index}`
}

const formatHotValue = (value) => {
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

const getStatCount = (statsList, platformKey) => {
  const item = statsList.find(i => i.platform === platformKey)
  return item ? (item.count ?? item.total ?? item.value ?? 0) : 0
}

const loadPlatformData = async (platform) => {
  platform.loading = true

  try {
    const dailyTop = await getDailyTop(platform.key, 10).catch(() => [])
    platform.dailyTop = Array.isArray(dailyTop) ? dailyTop : []

    if (platform.showPinned) {
      const currentList = await getHotspotsByPlatform(platform.key).catch(() => [])
      const list = Array.isArray(currentList) ? currentList : []
      platform.pinned = list.find(item => item.isSpecial) || null
    }
  } finally {
    platform.loading = false
  }
}

onMounted(async () => {
  const statsList = await getPlatformStats().catch(() => [])

  platforms.value.forEach(platform => {
    platform.count = getStatCount(statsList, platform.key)
  })

  await Promise.all(
    platforms.value.map(platform => loadPlatformData(platform))
  )
})
</script>

<style scoped>
.home-page {
  max-width: 1280px;
  margin: 30px auto;
  padding: 20px;
}

.header {
  margin-bottom: 30px;
}

.header h1 {
  font-size: 36px;
  margin-bottom: 10px;
}

.header p {
  color: #666;
  margin-bottom: 20px;
}

.search-box {
  max-width: 600px;
}

.stat-row {
  margin-bottom: 20px;
}

.stat-row .el-col {
  margin-bottom: 20px;
}

.platform-row .el-col {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-title {
  font-size: 16px;
  color: #666;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
  margin-top: 8px;
}

.stat-tip {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

.platform-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: bold;
}

.platform-desc {
  margin-top: 4px;
  font-size: 12px;
  font-weight: normal;
  color: #909399;
}

.pinned-block {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 14px 0 16px;
  margin-bottom: 8px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}

.pinned-block:hover {
  background: #f8f9fb;
}

.pinned-content {
  flex: 1;
}

.pinned-title {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 6px;
}

.pinned-meta {
  color: #909399;
  font-size: 13px;
}

.hot-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: all 0.2s;
}

.hot-item:hover {
  background: #f8f9fb;
}

.rank {
  width: 36px;
  font-weight: bold;
  color: #f56c6c;
  font-size: 20px;
}

.title {
  flex: 1;
  margin: 0 10px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hot {
  color: #999;
  min-width: 72px;
  text-align: right;
}
</style>