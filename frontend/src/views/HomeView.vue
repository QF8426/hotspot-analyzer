<template>
  <div class="home-shell">
    <!-- 顶部导航：简化为首页 / 跨平台热点 / 历史榜单，避免与平台入口、详情页重复 -->
    <header class="top-bar">
      <div class="brand" @click="goHome">
        <div class="brand-logo">
          <span>↗</span>
        </div>
        <div>
          <div class="brand-title">跨平台热点聚合分析器</div>
          <div class="brand-subtitle">Weibo · Douyin · Bilibili Intelligence</div>
        </div>
      </div>

      <nav class="nav-tabs">
        <button class="nav-tab active" @click="goHome">
          <span class="nav-icon">⌂</span>
          首页
        </button>
        <button class="nav-tab" @click="goCrossPlatform">
          <span class="nav-icon">▥</span>
          跨平台热点
        </button>
        <button class="nav-tab" @click="goHistory">
          <span class="nav-icon">◷</span>
          历史榜单
        </button>
      </nav>

      <div class="sync-status">
        <span class="status-dot"></span>
        <span>{{ lastSyncText }} · 三平台运行中</span>
        <span class="status-bars">▮▮▮</span>
      </div>
    </header>

    <main class="home-page">
      <!-- Hero 区 -->
      <section class="hero-section">
        <div class="hero-bg hero-bg-left"></div>
        <div class="hero-bg hero-bg-right"></div>

        <div class="hero-content">
          <h1>跨平台热点<span>观察台</span></h1>
          <p>
            聚合微博、抖音、B站热点数据，智能生成 AI 简介与跨平台分析，洞察全网热点趋势
          </p>

          <div class="hero-search">
            <el-input
              v-model="keyword"
              placeholder="搜索热点关键词、事件或话题..."
              size="large"
              clearable
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <span class="search-prefix">⌕</span>
              </template>
              <template #append>
                <el-button type="primary" @click="handleSearch">搜索</el-button>
              </template>
            </el-input>
          </div>
        </div>

        <div class="hero-visual" aria-hidden="true">
          <div class="visual-card">
            <div class="bubble">···</div>
            <div class="lens"></div>
            <div class="bar bar-1"></div>
            <div class="bar bar-2"></div>
            <div class="bar bar-3"></div>
            <div class="platform-layer layer-top"></div>
            <div class="platform-layer layer-bottom"></div>
          </div>
        </div>
      </section>

      <!-- 热门分类：轻量筛选带 -->
      <section class="category-strip">
        <div class="category-title">
          <span class="flame">◆</span>
          热门分类
        </div>
        <div class="category-list">
          <button
            v-for="category in categories"
            :key="category.name"
            class="category-chip"
            :class="{ active: selectedCategory === category.name }"
            @click="handleCategoryClick(category)"
          >
            <span class="category-icon">{{ category.icon }}</span>
            <span>{{ category.name }}</span>
            <small v-if="getCategoryCount(category) > 0">{{ getCategoryCount(category) }}</small>
          </button>
        </div>
      </section>

      <!-- 概览卡片 -->
      <section class="overview-grid">
        <article class="overview-card blue">
          <div class="metric-icon">🔥</div>
          <div class="metric-main">
            <div class="metric-title">今日热点总数</div>
            <div class="metric-value">{{ totalTodayCount }}</div>
            <div class="metric-tip">统计今日进入榜单的不同热点</div>
          </div>
          <svg class="mini-chart" viewBox="0 0 120 46" preserveAspectRatio="none">
            <polyline points="0,36 20,28 40,31 60,18 80,24 100,10 120,18" />
          </svg>
        </article>

        <article class="overview-card purple">
          <div class="metric-icon">✣</div>
          <div class="metric-main">
            <div class="metric-title">跨平台热点组</div>
            <div class="metric-value">{{ crossGroupCount }}</div>
            <div class="metric-tip">来自跨平台主题表</div>
          </div>
          <svg class="mini-chart purple-line" viewBox="0 0 120 46" preserveAspectRatio="none">
            <polyline points="0,34 20,30 40,20 60,24 80,13 100,8 120,16" />
          </svg>
        </article>

        <article class="overview-card indigo">
          <div class="metric-icon">AI</div>
          <div class="metric-main">
            <div class="metric-title">AI 简介能力</div>
            <div class="metric-value small-value">运行中</div>
            <div class="metric-tip">支持单平台与跨平台简介</div>
          </div>
          <svg class="mini-chart" viewBox="0 0 120 46" preserveAspectRatio="none">
            <polyline points="0,30 20,26 40,28 60,17 80,22 100,12 120,18" />
          </svg>
        </article>

        <article class="overview-card green">
          <div class="metric-icon">◎</div>
          <div class="metric-main">
            <div class="metric-title">覆盖平台数</div>
            <div class="metric-value">{{ platformCount }}</div>
            <div class="metric-tip">微博 / 抖音 / B站</div>
          </div>
        </article>
      </section>

      <!-- 跨平台热点观察 -->
      <section id="cross-hotspots" class="section-card cross-section">
        <div class="section-header">
          <div>
            <h2><span>◆</span> 跨平台热点观察</h2>
            <p>展示系统已识别并入库的跨平台联合热点主题，数据来源于 cross_platform_topic。</p>
          </div>
          <el-button type="primary" link @click="goCrossPlatform">查看更多</el-button>
        </div>

        <div v-if="crossHotspots.length > 0" v-loading="crossLoading" class="cross-grid">
          <article
            v-for="(item, index) in crossHotspots"
            :key="item.topicId || item.id || index"
            class="cross-card"
            @click="goCrossTopicDetail(item)"
          >
            <div class="cross-top">
              <span class="cross-rank">{{ index + 1 }}</span>
              <h3>{{ cleanTitle(item.title) }}</h3>
              <el-tag size="small" type="primary">跨平台分析</el-tag>
            </div>
            <div class="platform-badges">
              <span
                v-for="platform in item.platforms"
                :key="platform"
                class="platform-badge"
                :class="platform"
              >
                {{ getPlatformName(platform) }}
              </span>
            </div>
            <div class="cross-meta-line">
              <span>日期：{{ formatTopicDate(item.topicDate) }}</span>
              <span>综合热度：{{ item.hotText }}</span>
            </div>
            <p class="cross-summary">{{ item.summary }}</p>
            <div class="cross-footer">
              <span>按关联平台热度求和排序</span>
              <span>关联平台 {{ item.platforms.length }} 个</span>
            </div>
          </article>
        </div>

        <el-empty v-else description="暂无跨平台联合热点，请先运行跨平台扫描或查看合集页" />
      </section>

      <!-- 三平台 Top10 -->
      <section id="platform-ranks" class="rank-section">
        <div class="rank-section-header">
          <div>
            <h2>三平台今日榜单</h2>
            <p>每个平台单独按今日最高热度展示，避免不同平台热度口径直接混排。</p>
          </div>
        </div>

        <div class="rank-grid">
          <article
            v-for="platform in platforms"
            :key="platform.key"
            class="rank-card"
            :class="platform.key"
          >
            <div class="rank-card-header">
              <div class="rank-title-wrap">
                <span class="platform-logo">{{ platform.icon }}</span>
                <div>
                  <h3>{{ platform.name }}今日 Top10</h3>
                  <p>{{ platform.desc }}</p>
                </div>
              </div>
              <button class="text-link" @click="goPlatform(platform.key, 'daily')">
                查看完整榜单 →
              </button>
            </div>

            <div v-loading="platform.loading" class="rank-list-wrap">
              <div
                v-if="platform.showPinned && platform.pinned"
                class="pinned-block"
                @click="goDetail(platform.pinned.id)"
              >
                <span class="pinned-tag">置顶</span>
                <div class="pinned-content">
                  <div class="pinned-title">{{ cleanTitle(platform.pinned.title) }}</div>
                  <div class="pinned-meta">
                    标签：{{ normalizeTag(platform.pinned.tags, platform.pinned.title) }}
                  </div>
                </div>
              </div>

              <template v-if="platform.dailyTop.length > 0">
                <div
                  v-for="(item, index) in platform.dailyTop.slice(0, 10)"
                  :key="getItemId(item, platform.key, index)"
                  class="rank-row"
                  @click="goDetail(getItemId(item, platform.key, index))"
                >
                  <span class="rank-number" :class="{ top: index < 3 }">{{ index + 1 }}</span>
                  <span class="rank-name">{{ cleanTitle(item.title) }}</span>
                  <span class="rank-heat">🔥 {{ formatHotValue(getHotValue(item)) }}</span>
                </div>
              </template>

              <el-empty v-else description="暂无数据" />
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getPlatformStats,
  getDailyTop,
  getHotspotsByPlatform,
  getCrossPlatformTopics
} from '../api/hotspot'

const router = useRouter()

const platformConfigs = [
  {
    key: 'weibo',
    name: '微博',
    desc: '微博热搜榜',
    icon: '🔴',
    showPinned: true
  },
  {
    key: 'douyin',
    name: '抖音',
    desc: '抖音热榜',
    icon: '♪',
    showPinned: false
  },
  {
    key: 'bilibili',
    name: 'B站',
    desc: 'B站热搜词条',
    icon: '▣',
    showPinned: false
  }
]

const categories = [
  { name: '全部', icon: '✨', keywords: [] },
  { name: '社会民生', icon: '👥', keywords: ['社会', '民生', '通报', '回应', '警方', '官方', '网友', '辟谣'] },
  { name: '娱乐', icon: '☆', keywords: ['明星', '演员', '综艺', '娱乐', '恋情', '新剧'] },
  { name: '科技数码', icon: '▣', keywords: ['科技', '数码', '手机', 'AI', '华为', '苹果', '芯片', '机器人'] },
  { name: '体育运动', icon: '🏃', keywords: ['体育', '世界杯', '足球', '篮球', '比赛', '运动'] },
  { name: '游戏', icon: '🎮', keywords: ['游戏', '原神', '王者', '英雄联盟', 'LPL', 'Steam'] },
  { name: '影视', icon: '🎬', keywords: ['电影', '电视剧', '影视', '票房', '导演'] },
  { name: '财经', icon: '📈', keywords: ['财经', '股票', 'A股', '房价', '油价', '人民币'] },
  { name: '汽车', icon: '🚘', keywords: ['汽车', '新能源', '车', '智驾', '特斯拉'] },
  { name: '美食', icon: '🍜', keywords: ['美食', '餐饮', '饭店', '外卖', '菜'] },
  { name: '更多', icon: '⌄', keywords: [] }
]

const platforms = ref(
  platformConfigs.map(item => ({
    ...item,
    count: 0,
    dailyTop: [],
    currentList: [],
    pinned: null,
    latestTime: null,
    loading: false
  }))
)

const keyword = ref('')
const selectedCategory = ref('全部')

const totalTodayCount = computed(() => {
  return platforms.value.reduce((sum, platform) => sum + Number(platform.count || 0), 0)
})

const platformCount = computed(() => platforms.value.length)

const allLoadedItems = computed(() => {
  const list = []
  const seen = new Set()

  platforms.value.forEach(platform => {
    const pushUnique = (item) => {
      const id = getItemId(item, platform.key)
      const title = cleanTitle(item?.title)
      const key = id && !String(id).includes('-') ? `${platform.key}:${id}` : `${platform.key}:${title}`
      if (!title || seen.has(key)) return
      seen.add(key)
      list.push({ ...item, _platform: platform.key })
    }

    ;(platform.dailyTop || []).forEach(pushUnique)
    ;(platform.currentList || []).forEach(pushUnique)
  })

  return list
})

const crossTopics = ref([])
const crossLoading = ref(false)

const crossGroupCount = computed(() => crossTopics.value.length)

const crossHotspots = computed(() => {
  return crossTopics.value
    .filter(topic => (topic.platformCount || getTopicPlatforms(topic).length || 0) >= 2)
    .slice(0, 3)
    .map(topic => buildCrossTopicCard(topic))
})

const lastSyncText = computed(() => {
  const times = platforms.value
    .map(platform => platform.latestTime)
    .filter(Boolean)
    .map(value => new Date(value).getTime())
    .filter(value => !Number.isNaN(value))

  if (!times.length) return '最近同步：刚刚刷新'

  const latest = Math.max(...times)
  const diffMinutes = Math.max(0, Math.round((Date.now() - latest) / 60000))

  if (diffMinutes <= 1) return '最近同步：1分钟内'
  if (diffMinutes < 60) return `最近同步：${diffMinutes}分钟前`

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `最近同步：${diffHours}小时前`

  return '最近同步：今日数据'
})

const handleSearch = () => {
  const value = keyword.value.trim()
  if (!value) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  router.push({
    path: '/search',
    query: { keyword: value }
  })
}

const handleCategoryClick = (category) => {
  selectedCategory.value = category.name

  if (category.name === '全部') {
    ElMessage.info('已显示首页全部热点概览')
    return
  }

  if (category.name === '更多') {
    ElMessage.info('更多分类可以后续扩展为分类热点页')
    return
  }

  router.push({
    path: '/search',
    query: { keyword: category.name }
  })
}

const goHome = () => {
  router.push('/')
}

const goHistory = () => {
  router.push({
    path: '/platform/weibo',
    query: { mode: 'history' }
  })
}

const goCrossPlatform = () => {
  router.push('/cross-platform')
}

const goPlatform = (platform, mode = 'current') => {
  router.push({
    path: `/platform/${platform}`,
    query: { mode }
  })
}

const goDetail = (id) => {
  if (!id || String(id).includes('-')) return
  router.push(`/detail/${id}`)
}

const goCrossTopicDetail = (item) => {
  if (item?.id) {
    goDetail(item.id)
    return
  }
  goCrossPlatform()
}

const scrollToCrossHotspots = () => {
  document.querySelector('#cross-hotspots')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const scrollToPlatformRanks = () => {
  document.querySelector('#platform-ranks')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const cleanTitle = (title) => {
  if (!title) return ''
  return String(title).replace(/^#|#$/g, '').trim()
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
  return item?.maxHotValue ?? item?.hotValue ?? item?.hot_value ?? item?.max_hot_value
}

const getItemId = (item, platformKey = '', index = 0) => {
  return item?.id ?? item?.hotspotId ?? item?.hotspot_id ?? `${platformKey}-${index}`
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

const formatTopicDate = (value) => {
  if (!value) return '未知日期'

  const text = String(value).slice(0, 10)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  const toDateText = (date) => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }

  // 不再显示“今天/昨天”，统一显示具体日期，避免用户无法判断是哪一天的热点
  return text
}

const getPlatformName = (platformKey) => {
  const item = platformConfigs.find(platform => platform.key === platformKey)
  return item ? item.name : platformKey
}

const getStatCount = (statsList, platformKey) => {
  const item = statsList.find(i => i.platform === platformKey)
  return item ? (item.count ?? item.total ?? item.value ?? 0) : 0
}

const getCategoryCount = (category) => {
  if (category.name === '全部') return allLoadedItems.value.length
  if (category.name === '更多') return 0
  if (!category.keywords?.length) return 0

  return allLoadedItems.value.filter(item => {
    const text = `${item.title || ''} ${item.tags || ''}`
    return category.keywords.some(word => text.includes(word))
  }).length
}

const getTopicPlatforms = (topic) => {
  if (topic?.relatedPlatforms) {
    return String(topic.relatedPlatforms)
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)
  }

  const set = new Set()
  ;(topic?.hotspots || []).forEach(item => {
    if (item.platform) set.add(item.platform)
  })
  return Array.from(set)
}

const getTopicPrimaryHotspot = (topic) => {
  return (topic?.hotspots || []).find(item => item.primary || item.isPrimary) || (topic?.hotspots || [])[0] || null
}

const getTopicTotalHotValue = (topic) => {
  const apiValue = Number(topic?.totalHotValue ?? topic?.total_hot_value ?? 0)
  if (apiValue > 0) return apiValue

  return (topic?.hotspots || []).reduce((sum, item) => {
    return sum + (Number(item.hotValue ?? item.hot_value ?? 0) || 0)
  }, 0)
}

const buildTopicSummary = (topic) => {
  const text = String(topic?.summary || '').replace(/\s+/g, ' ').trim()
  if (text) return text.length > 92 ? `${text.slice(0, 92)}...` : text

  const platformsText = getTopicPlatforms(topic).map(getPlatformName).join('、')
  return `该话题已被系统识别为${platformsText || '多个平台'}共同关注的联合热点，可进入详情页查看 AI 简介、趋势和来源材料。`
}

const buildCrossTopicCard = (topic) => {
  const primary = getTopicPrimaryHotspot(topic)
  const platforms = getTopicPlatforms(topic)

  return {
    topicId: topic.id,
    id: primary?.hotspotId,
    title: topic.mainTitle || primary?.title || '跨平台热点',
    platforms,
    topicDate: topic.topicDate,
    hotText: formatHotValue(getTopicTotalHotValue(topic)),
    summary: buildTopicSummary(topic)
  }
}

const loadCrossTopics = async () => {
  crossLoading.value = true
  try {
    const result = await getCrossPlatformTopics({ limit: 3, todayOnly: true }).catch(() => [])
    crossTopics.value = Array.isArray(result) ? result : []
  } finally {
    crossLoading.value = false
  }
}

const loadPlatformData = async (platform) => {
  platform.loading = true

  try {
    const [dailyTopResult, currentListResult] = await Promise.all([
      getDailyTop(platform.key, 10).catch(() => []),
      getHotspotsByPlatform(platform.key).catch(() => [])
    ])

    platform.dailyTop = Array.isArray(dailyTopResult) ? dailyTopResult : []
    platform.currentList = Array.isArray(currentListResult) ? currentListResult : []

    if (platform.showPinned) {
      platform.pinned = platform.currentList.find(item => item.isSpecial) || null
    }

    const latestItem = platform.currentList
      .filter(item => item.crawlTime || item.crawl_time)
      .sort((a, b) => new Date(b.crawlTime || b.crawl_time) - new Date(a.crawlTime || a.crawl_time))[0]

    platform.latestTime = latestItem?.crawlTime || latestItem?.crawl_time || null
  } finally {
    platform.loading = false
  }
}

onMounted(async () => {
  const statsList = await getPlatformStats().catch(() => [])

  platforms.value.forEach(platform => {
    platform.count = getStatCount(Array.isArray(statsList) ? statsList : [], platform.key)
  })

  await Promise.all([
    Promise.all(platforms.value.map(platform => loadPlatformData(platform))),
    loadCrossTopics()
  ])
})
</script>

<style scoped>
:global(html) {
  background: #f5f8ff;
}

:global(body) {
  margin: 0;
  background: #f5f8ff;
  color: #172033;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

:global(*) {
  box-sizing: border-box;
}

.home-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 8%, rgba(75, 133, 255, 0.14), transparent 26%),
    radial-gradient(circle at 88% 14%, rgba(128, 84, 255, 0.14), transparent 28%),
    linear-gradient(180deg, #f8fbff 0%, #f4f7fc 48%, #f7f9ff 100%);
}

.top-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 34px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(80, 116, 180, 0.12);
  box-shadow: 0 10px 30px rgba(64, 102, 180, 0.08);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 310px;
  cursor: pointer;
}

.brand-logo {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 15px;
  color: #fff;
  font-size: 21px;
  font-weight: 900;
  background: linear-gradient(135deg, #2275ff, #7d5cff);
  box-shadow: 0 12px 26px rgba(48, 101, 255, 0.28);
}

.brand-title {
  font-size: 17px;
  font-weight: 800;
  color: #13213d;
  line-height: 1.2;
}

.brand-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: #667085;
  letter-spacing: 0.02em;
}

.nav-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 18px;
  background: rgba(245, 248, 255, 0.8);
}

.nav-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 7px;
  border: 0;
  border-radius: 14px;
  padding: 10px 17px;
  color: #344054;
  font-size: 15px;
  font-weight: 700;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-tab:hover,
.nav-tab.active {
  color: #1d5fff;
  background: #fff;
  box-shadow: 0 10px 24px rgba(36, 101, 255, 0.12);
}

.nav-tab.active::after {
  content: '';
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: -7px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1d6bff, #6e5cff);
}

.nav-icon {
  font-size: 17px;
}

.sync-status {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 265px;
  padding: 8px 13px;
  border: 1px solid rgba(82, 126, 200, 0.13);
  border-radius: 14px;
  color: #344054;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.78);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.1);
}

.status-bars {
  color: #246bff;
  letter-spacing: -2px;
}

.home-page {
  width: min(1640px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 12px 0 40px;
}

.hero-section {
  position: relative;
  min-height: 174px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  align-items: center;
  overflow: hidden;
  margin-bottom: 12px;
  border-radius: 0 0 22px 22px;
  background:
    linear-gradient(135deg, rgba(230, 241, 255, 0.92), rgba(246, 248, 255, 0.96)),
    radial-gradient(circle at 90% 20%, rgba(79, 110, 255, 0.18), transparent 28%);
}

.hero-bg {
  position: absolute;
  width: 460px;
  height: 140px;
  border-radius: 999px;
  opacity: 0.55;
  filter: blur(2px);
}

.hero-bg-left {
  left: -120px;
  bottom: 18px;
  background: rgba(74, 133, 255, 0.14);
  transform: rotate(-8deg);
}

.hero-bg-right {
  right: 60px;
  top: 26px;
  background: rgba(127, 91, 255, 0.14);
  transform: rotate(10deg);
}

.hero-content {
  position: relative;
  z-index: 2;
  max-width: 720px;
  justify-self: center;
  text-align: center;
  padding: 22px 20px 24px;
}

.hero-content h1 {
  margin: 0;
  color: #121826;
  font-size: clamp(34px, 3.3vw, 48px);
  line-height: 1.12;
  font-weight: 900;
  letter-spacing: -0.04em;
}

.hero-content h1 span {
  margin-left: 4px;
  color: #2563ff;
}

.hero-content p {
  margin: 10px 0 18px;
  color: #56627a;
  font-size: 14px;
  line-height: 1.55;
}

.hero-search {
  max-width: 560px;
  margin: 0 auto;
  border-radius: 16px;
  box-shadow: 0 16px 45px rgba(68, 103, 180, 0.16);
}

.hero-search :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 16px 0 0 16px;
  box-shadow: 0 0 0 1px rgba(76, 111, 180, 0.12) inset;
}

.hero-search :deep(.el-input-group__append) {
  border-radius: 0 16px 16px 0;
  overflow: hidden;
  background: linear-gradient(135deg, #246bff, #154ee8);
  border-color: transparent;
  box-shadow: none;
}

.hero-search :deep(.el-button) {
  min-width: 84px;
  height: 46px;
  border: 0;
  color: #fff;
  font-weight: 800;
  background: transparent;
}

.search-prefix {
  color: #667085;
  font-size: 20px;
}

.hero-visual {
  position: relative;
  z-index: 2;
  height: 174px;
  display: grid;
  place-items: center;
}

.visual-card {
  position: relative;
  width: 210px;
  height: 146px;
}

.platform-layer {
  position: absolute;
  left: 34px;
  width: 140px;
  height: 50px;
  border-radius: 24px;
  transform: skewX(-14deg) rotate(-3deg);
}

.layer-bottom {
  bottom: 10px;
  background: linear-gradient(135deg, #4278ff, #765eff);
  box-shadow: 0 24px 50px rgba(72, 98, 238, 0.32);
}

.layer-top {
  bottom: 40px;
  background: linear-gradient(135deg, #f9fbff, #dce7ff);
  border: 1px solid rgba(80, 120, 240, 0.14);
  box-shadow: 0 14px 24px rgba(90, 116, 180, 0.15);
}

.bubble {
  position: absolute;
  z-index: 4;
  left: 24px;
  top: 26px;
  width: 50px;
  height: 32px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 21px;
  letter-spacing: 2px;
  background: linear-gradient(135deg, #3785ff, #635bff);
  box-shadow: 0 18px 34px rgba(70, 112, 255, 0.28);
}

.lens {
  position: absolute;
  z-index: 5;
  right: 20px;
  top: 8px;
  width: 62px;
  height: 62px;
  border-radius: 50%;
  border: 8px solid #386cff;
  box-shadow: inset 0 0 0 8px rgba(255, 255, 255, 0.7), 0 18px 36px rgba(56, 108, 255, 0.3);
}

.lens::after {
  content: '';
  position: absolute;
  width: 36px;
  height: 10px;
  right: -28px;
  bottom: -18px;
  border-radius: 999px;
  transform: rotate(44deg);
  background: #386cff;
}

.bar {
  position: absolute;
  z-index: 4;
  bottom: 61px;
  width: 16px;
  border-radius: 999px 999px 4px 4px;
}

.bar-1 {
  left: 106px;
  height: 32px;
  background: #ff78b7;
}

.bar-2 {
  left: 130px;
  height: 46px;
  background: #6e7cff;
}

.bar-3 {
  left: 154px;
  height: 36px;
  background: #37b7ff;
}

.category-strip {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 10px 16px;
  margin-bottom: 12px;
  border: 1px solid rgba(99, 130, 190, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 30px rgba(87, 113, 160, 0.08);
}

.category-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 112px;
  color: #172033;
  font-size: 16px;
  font-weight: 800;
}

.flame {
  color: #246bff;
}

.category-list {
  display: flex;
  flex: 1;
  flex-wrap: nowrap;
  overflow-x: auto;
  padding-bottom: 2px;
  gap: 8px;
}

.category-chip {
  min-height: 30px;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border: 1px solid rgba(88, 117, 172, 0.12);
  border-radius: 12px;
  color: #344054;
  font-weight: 700;
  background: #f8faff;
  cursor: pointer;
  transition: all 0.18s ease;
}

.category-chip small {
  min-width: 24px;
  padding: 2px 7px;
  border-radius: 999px;
  color: #475467;
  font-size: 12px;
  background: #fff;
  box-shadow: inset 0 0 0 1px rgba(88, 117, 172, 0.14);
}

.category-chip:hover,
.category-chip.active {
  color: #fff;
  border-color: transparent;
  background: linear-gradient(135deg, #246bff, #665cff);
  box-shadow: 0 10px 18px rgba(48, 93, 255, 0.18);
}

.category-chip.active small,
.category-chip:hover small {
  color: #1f5fff;
}

.category-icon {
  font-size: 15px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.overview-card {
  position: relative;
  min-height: 86px;
  display: flex;
  align-items: center;
  gap: 16px;
  overflow: hidden;
  padding: 15px 18px;
  border: 1px solid rgba(99, 130, 190, 0.12);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 14px 34px rgba(87, 113, 160, 0.09);
}

.metric-icon {
  flex: 0 0 auto;
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 22px;
  color: #fff;
  font-size: 23px;
  font-weight: 900;
}

.overview-card.blue .metric-icon {
  background: linear-gradient(135deg, #3a85ff, #246bff);
}

.overview-card.purple .metric-icon {
  background: linear-gradient(135deg, #a76bff, #725cff);
}

.overview-card.indigo .metric-icon {
  font-size: 20px;
  background: linear-gradient(135deg, #6b72ff, #364dff);
}

.overview-card.green .metric-icon {
  background: linear-gradient(135deg, #22c55e, #16a34a);
}

.metric-title {
  color: #344054;
  font-size: 14px;
  font-weight: 800;
}

.metric-value {
  margin-top: 4px;
  color: #111827;
  font-size: 27px;
  line-height: 1;
  font-weight: 900;
  letter-spacing: -0.02em;
}

.small-value {
  font-size: 21px;
}

.metric-tip {
  margin-top: 4px;
  color: #667085;
  font-size: 12px;
}

.mini-chart {
  position: absolute;
  right: 16px;
  bottom: 14px;
  width: 78px;
  height: 28px;
  fill: none;
  stroke: #246bff;
  stroke-width: 4;
  stroke-linecap: round;
  stroke-linejoin: round;
  opacity: 0.9;
}

.purple-line {
  stroke: #725cff;
}

.section-card,
.rank-card {
  border: 1px solid rgba(99, 130, 190, 0.12);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.93);
  box-shadow: 0 14px 34px rgba(87, 113, 160, 0.09);
}

.cross-section {
  padding: 16px 18px;
  margin-bottom: 14px;
  scroll-margin-top: 90px;
}

.section-header,
.rank-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.section-header h2,
.rank-section-header h2 {
  margin: 0;
  color: #172033;
  font-size: 20px;
  font-weight: 900;
}

.section-header h2 span {
  color: #246bff;
}

.section-header p,
.rank-section-header p {
  margin: 3px 0 0;
  color: #667085;
  font-size: 13px;
}

.cross-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.cross-card {
  min-height: 126px;
  padding: 14px 16px;
  border: 1px solid rgba(87, 121, 190, 0.13);
  border-radius: 17px;
  background: linear-gradient(180deg, #fff, #fbfdff);
  cursor: pointer;
  transition: all 0.2s ease;
}

.cross-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 16px 36px rgba(76, 106, 168, 0.14);
}

.cross-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cross-rank {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 8px;
  color: #fff;
  font-size: 15px;
  font-weight: 900;
  background: linear-gradient(135deg, #ff4d4f, #ff8a35);
}

.cross-top h3 {
  flex: 1;
  min-width: 0;
  margin: 0;
  color: #182235;
  font-size: 16px;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0;
}

.platform-badge {
  padding: 3px 9px;
  border-radius: 999px;
  color: #475467;
  font-size: 12px;
  font-weight: 800;
  background: #f2f6ff;
}

.platform-badge.weibo {
  color: #e5484d;
  background: #fff1f2;
}

.platform-badge.douyin {
  color: #111827;
  background: #f4f5f7;
}

.platform-badge.bilibili {
  color: #fb5ca8;
  background: #fff0f7;
}

.cross-meta-line {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: 6px 0 8px;
  padding: 7px 9px;
  border-radius: 12px;
  color: #475467;
  font-size: 12px;
  font-weight: 800;
  background: #f7f9ff;
}

.cross-summary {
  min-height: 40px;
  margin: 0 0 8px;
  color: #4a5568;
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.cross-footer {
  display: flex;
  justify-content: space-between;
  color: #667085;
  font-size: 13px;
}

.rank-section {
  scroll-margin-top: 90px;
}

.rank-section-header {
  padding: 0 4px;
}

.rank-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.rank-card {
  min-height: 354px;
  padding: 16px 18px;
}

.rank-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 10px;
  margin-bottom: 6px;
  border-bottom: 1px solid rgba(100, 122, 160, 0.12);
}

.rank-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.platform-logo {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  font-weight: 900;
  background: #f3f6ff;
}

.rank-card.weibo .platform-logo {
  background: #fff0f1;
}

.rank-card.douyin .platform-logo {
  color: #fff;
  background: #111827;
}

.rank-card.bilibili .platform-logo {
  color: #fff;
  background: #fb5ca8;
}

.rank-title-wrap h3 {
  margin: 0;
  color: #172033;
  font-size: 17px;
  font-weight: 900;
}

.rank-title-wrap p {
  margin: 4px 0 0;
  color: #667085;
  font-size: 12px;
}

.text-link {
  border: 0;
  padding: 0;
  color: #246bff;
  font-size: 13px;
  font-weight: 800;
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
}

.rank-list-wrap {
  min-height: 282px;
}

.pinned-block {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 10px;
  margin-bottom: 8px;
  border-radius: 13px;
  background: linear-gradient(135deg, #fff7ed, #fff1f2);
  cursor: pointer;
}

.pinned-tag {
  flex: 0 0 auto;
  padding: 4px 8px;
  border-radius: 999px;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  background: #ef4444;
}

.pinned-content {
  min-width: 0;
}

.pinned-title {
  color: #172033;
  font-size: 14px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pinned-meta {
  margin-top: 4px;
  color: #667085;
  font-size: 12px;
}

.rank-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 82px;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  padding: 5px 2px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.rank-row:hover {
  background: #f5f8ff;
}

.rank-number {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  color: #667085;
  font-size: 12px;
  font-weight: 900;
  background: #eef2f7;
}

.rank-number.top {
  color: #fff;
  background: linear-gradient(135deg, #ff4d4f, #ffb02e);
}

.rank-name {
  min-width: 0;
  color: #29334d;
  font-size: 14px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-heat {
  color: #ff5b73;
  font-size: 13px;
  font-weight: 800;
  text-align: right;
  white-space: nowrap;
}

@media (max-width: 1280px) {
  .top-bar {
    padding: 0 20px;
  }

  .brand {
    min-width: 260px;
  }

  .sync-status {
    min-width: auto;
  }

  .hero-section {
    grid-template-columns: 1fr;
  }

  .hero-visual {
    display: none;
  }

  .overview-grid,
  .rank-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .top-bar {
    position: static;
    height: auto;
    flex-direction: column;
    align-items: stretch;
    padding: 16px;
  }

  .brand,
  .sync-status {
    min-width: 0;
  }

  .nav-tabs {
    overflow-x: auto;
  }

  .home-page {
    width: min(100vw - 24px, 100%);
  }

  .category-strip {
    align-items: flex-start;
    flex-direction: column;
  }

  .overview-grid,
  .cross-grid,
  .rank-grid {
    grid-template-columns: 1fr;
  }
}
</style>
