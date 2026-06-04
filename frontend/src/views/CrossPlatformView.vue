<template>
  <div class="app-container page-stack">
    <section class="page-hero">
      <span class="page-hero__eyebrow">跨平台分析</span>
      <h1 class="page-hero__title">跨平台热点合集</h1>
      <p class="page-hero__subtitle">
        展示系统识别出的多平台共同热点主题，重点体现微博、抖音、B站之间的话题联动与共同传播情况。
      </p>

      <div class="cross-hero__metrics">
        <div class="cross-hero__metric">
          <span>当前筛选主题数</span>
          <strong>{{ topicTotal }}</strong>
        </div>
        <div class="cross-hero__metric">
          <span>当前页主题数</span>
          <strong>{{ currentTopics.length }}</strong>
        </div>
        <div class="cross-hero__metric">
          <span>三平台共同主题</span>
          <strong>{{ threePlatformCount }}</strong>
        </div>
        <div class="cross-hero__metric">
          <span>含 AI 简介主题</span>
          <strong>{{ summaryCount }}</strong>
        </div>
      </div>
    </section>

    <section class="page-card page-card--strong cross-toolbar">
      <div class="control-bar">
        <div class="chip-group">
          <button
            v-for="option in filterOptions"
            :key="option.key"
            type="button"
            class="chip-button"
            :class="{ active: activeFilter === option.key }"
            @click="activeFilter = option.key"
          >
            {{ option.label }}
          </button>
        </div>

        <div class="cross-toolbar__actions">
          <el-button type="primary" @click="loadTopics">刷新主题</el-button>
        </div>
      </div>
    </section>

    <RequestState
      :loading="loading"
      :error="error"
      :empty="!loading && !error && currentTopics.length === 0 && topicTotal === 0"
      empty-description="当前条件下暂无可展示的跨平台热点主题"
      @retry="loadTopics"
    >
      <section class="cross-topic-grid">
        <article
          v-for="topic in currentTopics"
          :key="topic.id || topic.mainTitle"
          class="table-card cross-topic-card"
        >
          <div class="cross-topic-card__head">
            <div class="cross-topic-card__badges">
              <el-tag type="primary" effect="plain">跨平台主题</el-tag>
              <el-tag effect="plain">{{ formatTopicDate(topic.topicDate) }}</el-tag>
            </div>
          </div>

          <h2 class="cross-topic-card__title">{{ cleanTitle(topic.mainTitle) || '未命名主题' }}</h2>

          <div class="cross-topic-card__platforms">
            <PlatformPill
              v-for="platform in getTopicPlatforms(topic)"
              :key="`${topic.id || topic.mainTitle}-${platform}`"
              :platform="platform"
            />
          </div>

          <div class="cross-topic-card__meta-inline">
            <span>关联平台：{{ getTopicPlatforms(topic).length }}</span>
            <span>关联热点：{{ topic.hotspotCount || topic.hotspots?.length || 0 }}</span>
            <span>综合指标：{{ formatHotValue(getTopicTotalHotValue(topic)) }}</span>
          </div>

          <p class="cross-topic-card__summary">
            {{ buildSummaryText(topic.summary, fallbackSummary(topic), 168) }}
          </p>

          <div class="soft-divider"></div>

          <div class="cross-topic-card__related">
            <div class="section-head cross-topic-card__related-head">
              <div>
                <h3>主要关联热点</h3>
                <p>展示该主题下最主要的关联热点，方便继续查看单个热点详情。</p>
              </div>
            </div>

            <div class="cross-topic-card__related-list">
              <article
                v-for="item in (topic.hotspots || []).slice(0, 4)"
                :key="`${topic.id || topic.mainTitle}-${getHotspotId(item)}`"
                class="cross-related-item"
                @click="goDetail(getHotspotId(item))"
              >
                <div class="cross-related-item__main">
                  <div class="cross-related-item__title-row">
                    <PlatformPill :platform="item.platform" />
                    <h4>{{ cleanTitle(item.title) || `热点 ${getHotspotId(item)}` }}</h4>
                    <el-tag v-if="item.primary || item.isPrimary" type="warning" size="small">主热点</el-tag>
                  </div>
                  <div class="cross-related-item__meta">
                    <span>排名：{{ item.rankNum ?? '暂无' }}</span>
                    <span>{{ getPlatformHeatLabel(item.platform) }}：{{ formatHotValue(getHotValue(item), item.platform) }}</span>
                  </div>
                </div>
                <el-button type="primary" plain @click.stop="goDetail(getHotspotId(item))">查看详情</el-button>
              </article>

              <el-empty
                v-if="!(topic.hotspots || []).length"
                description="当前主题暂未同步关联热点明细，仍可通过主题入口查看聚合信息"
              />
            </div>
          </div>
        </article>

        <div class="cross-pagination" v-if="topicTotal > topicPageSize">
          <span class="cross-pagination__total">共 {{ topicTotal }} 条</span>
          <el-pagination
            v-model:current-page="topicPage"
            :page-size="topicPageSize"
            :total="topicTotal"
            layout="prev, pager, next"
            background
            @current-change="loadTopics"
          />
        </div>
      </section>
    </RequestState>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PlatformPill from '../components/PlatformPill.vue'
import RequestState from '../components/RequestState.vue'
import { getCrossPlatformTopics } from '../api/hotspot'
import {
  buildSummaryText,
  cleanTitle,
  formatDate,
  formatHotValue,
  getHotValue,
  getHotspotId,
  getPlatformHeatLabel,
  getPlatformLabel,
  getTopicPlatforms,
  getTopicPrimaryHotspot,
  getTopicTotalHotValue
} from '../utils/hotspot'

const router = useRouter()

const filterOptions = [
  { key: 'all', label: '全部' },
  { key: 'weibo,douyin', label: '微博 + 抖音' },
  { key: 'weibo,bilibili', label: '微博 + B站' },
  { key: 'douyin,bilibili', label: '抖音 + B站' },
  { key: 'three', label: '三平台共同' }
]

const loading = ref(false)
const error = ref('')
const activeFilter = ref('all')
const currentTopics = ref([])
const topicPage = ref(1)
const topicPageSize = 10
const topicTotal = ref(0)

const threePlatformCount = computed(
  () => currentTopics.value.filter(topic => getTopicPlatforms(topic).length >= 3).length
)

const summaryCount = computed(
  () => currentTopics.value.filter(topic => String(topic?.summary || '').trim()).length
)

async function loadTopics() {
  loading.value = true
  error.value = ''

  try {
    const result = await getCrossPlatformTopics({
      platformCombo: activeFilter.value,
      page: topicPage.value,
      pageSize: topicPageSize
    })
    
    if (result && result.records) {
      currentTopics.value = result.records
      topicTotal.value = result.total || 0
    } else {
      currentTopics.value = []
      topicTotal.value = 0
    }
  } catch (requestError) {
    error.value = requestError?.message || '跨平台主题加载失败，请稍后重试'
    currentTopics.value = []
    topicTotal.value = 0
  } finally {
    loading.value = false
  }
}

function fallbackSummary(topic) {
  const platforms = getTopicPlatforms(topic).map(getPlatformLabel).join('、') || '多个平台'
  return `该主题由系统自动聚合而成，当前已覆盖${platforms}的共同热点，可用于观察不同平台之间的话题联动。`
}

function formatTopicDate(value) {
  return value ? formatDate(value) : '日期未标注'
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

function goTopicDetail(topic) {
  goPrimaryHotspot(topic)
}

function goPrimaryHotspot(topic) {
  const primary = getTopicPrimaryHotspot(topic)
  if (primary) {
    goDetail(getHotspotId(primary))
  }
}

watch(activeFilter, () => {
  topicPage.value = 1
})

onMounted(loadTopics)
</script>

<style scoped>
.cross-hero__metrics {
  margin-top: 24px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.cross-hero__metric {
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(135, 160, 206, 0.18);
}

.cross-hero__metric span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.cross-hero__metric strong {
  display: block;
  margin-top: 10px;
  font-size: 24px;
  line-height: 1.2;
}

.cross-toolbar {
  padding: 20px 24px;
}

.cross-toolbar__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.cross-topic-grid {
  display: grid;
  gap: 16px;
}

.cross-pagination {
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid rgba(135, 160, 206, 0.16);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 14px;
}

.cross-pagination__total {
  color: var(--text-secondary);
  font-size: 13px;
}

.cross-topic-card {
  display: grid;
  gap: 12px;
}

.cross-topic-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cross-topic-card__badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cross-topic-card__title {
  margin: 0;
  font-size: 22px;
  line-height: 1.4;
}

.cross-topic-card__platforms {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cross-topic-card__meta-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.cross-topic-card__meta-inline span {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.06);
  border: 1px solid rgba(59, 130, 246, 0.12);
}

.cross-topic-card__summary {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.cross-topic-card__related-head h3 {
  margin: 0;
  font-size: 18px;
}

.cross-topic-card__related-head p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.cross-topic-card__related-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cross-related-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(245, 249, 255, 0.82);
  border: 1px solid rgba(135, 160, 206, 0.16);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.cross-related-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
  border-color: rgba(47, 107, 255, 0.2);
}

.cross-related-item__main {
  min-width: 0;
  flex: 1;
}

.cross-related-item__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cross-related-item__title-row h4 {
  margin: 0;
  font-size: 18px;
  line-height: 1.45;
}

.cross-related-item__meta {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1080px) {
  .cross-hero__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .cross-related-item {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .cross-hero__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
