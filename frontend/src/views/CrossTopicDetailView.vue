<template>
  <div class="app-container page-stack">
    <RequestState
      :loading="loading"
      :error="error"
      :empty="!loading && !error && !topic"
      empty-description="未找到该跨平台主题"
      @retry="loadTopic"
    >
      <template v-if="topic">
        <section class="page-hero cross-topic-hero">
          <div class="cross-topic-hero__main">
            <div class="cross-topic-hero__badges">
              <el-tag type="warning" effect="plain">跨平台主题分析</el-tag>
              <el-tag effect="plain">{{ formatDate(topic.topicDate) }}</el-tag>
            </div>

            <h1 class="page-hero__title">{{ cleanTitle(topic.mainTitle) || '未命名主题' }}</h1>
            <p class="page-hero__subtitle">{{ topicSummary }}</p>

            <div class="cross-topic-hero__platforms">
              <PlatformPill v-for="platform in topicPlatforms" :key="platform" :platform="platform" />
            </div>
          </div>

          <div class="cross-topic-hero__side">
            <div class="cross-topic-stat">
              <span>关联平台数</span>
              <strong>{{ topic.platformCount || topicPlatforms.length }}</strong>
            </div>
            <div class="cross-topic-stat">
              <span>关联热点数</span>
              <strong>{{ topic.hotspotCount || topic.hotspots?.length || 0 }}</strong>
            </div>
            <div class="cross-topic-stat">
              <span>综合指标</span>
              <strong>{{ formatHotValue(getTopicTotalHotValue(topic)) }}</strong>
            </div>
          </div>
        </section>

        <section class="table-card cross-topic-panel">
          <div class="section-head cross-topic-section">
            <div>
              <h2 class="section-title">关联平台与热点</h2>
              <p class="section-subtitle">展示该主题下已经聚合的热点来源，便于演示“多平台共同关注”的识别结果。</p>
            </div>
          </div>

          <div class="cross-topic-list">
            <article
              v-for="item in topic.hotspots || []"
              :key="`${item.platform}-${item.hotspotId}`"
              class="cross-topic-item"
            >
              <div class="cross-topic-item__main">
                <div class="cross-topic-item__title-row">
                  <PlatformPill :platform="item.platform" />
                  <h3>{{ cleanTitle(item.title) || `热点 ${item.hotspotId}` }}</h3>
                  <el-tag v-if="item.primary || item.isPrimary" type="warning" size="small">主热点</el-tag>
                </div>
                <div class="cross-topic-item__meta">
                  <span>平台内排名：{{ item.rankNum ?? '暂无' }}</span>
                  <span>{{ getPlatformHeatLabel(item.platform) }}：{{ formatHotValue(item.hotValue, item.platform) }}</span>
                  <span>采集时间：{{ formatDateTime(item.crawlTime) }}</span>
                </div>
              </div>

              <div class="cross-topic-item__actions">
                <el-button type="primary" plain @click="goHotspotDetail(item.hotspotId)">查看热点详情</el-button>
                <el-button :disabled="!item.sourceUrl" @click="openSource(item.sourceUrl)">来源链接</el-button>
              </div>
            </article>

            <el-empty
              v-if="!(topic.hotspots || []).length"
              description="当前主题暂无关联热点明细"
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
import PlatformPill from '../components/PlatformPill.vue'
import RequestState from '../components/RequestState.vue'
import { getCrossPlatformTopicDetail } from '../api/hotspot'
import {
  buildSummaryText,
  cleanTitle,
  formatDate,
  formatDateTime,
  formatHotValue,
  getPlatformHeatLabel,
  getTopicPlatforms,
  getTopicTotalHotValue
} from '../utils/hotspot'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const error = ref('')
const topic = ref(null)

const topicPlatforms = computed(() => getTopicPlatforms(topic.value))
const topicSummary = computed(() =>
  buildSummaryText(
    topic.value?.summary,
    '当前主题已经被系统识别为多平台共同关注的话题，可继续查看下方关联热点来源。',
    180
  )
)

async function loadTopic() {
  const topicId = route.params.id
  if (!topicId) return

  loading.value = true
  error.value = ''

  try {
    topic.value = await getCrossPlatformTopicDetail(topicId)
  } catch (requestError) {
    error.value = requestError?.message || '跨平台主题详情加载失败'
    topic.value = null
  } finally {
    loading.value = false
  }
}

function goHotspotDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

function openSource(url) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

watch(
  () => route.params.id,
  () => {
    loadTopic()
  },
  { immediate: true }
)
</script>

<style scoped>
.cross-topic-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
  gap: 22px;
}

.cross-topic-hero__badges,
.cross-topic-hero__platforms {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cross-topic-hero__platforms {
  margin-top: 22px;
}

.cross-topic-hero__side {
  display: grid;
  gap: 12px;
}

.cross-topic-stat {
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(135, 160, 206, 0.12);
}

.cross-topic-stat span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.cross-topic-stat strong {
  display: block;
  margin-top: 10px;
  font-size: 26px;
  line-height: 1.2;
}

.cross-topic-panel {
  padding: 22px;
}

.cross-topic-section {
  margin-bottom: 18px;
}

.cross-topic-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cross-topic-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  padding: 16px 4px;
  border-bottom: 1px solid rgba(135, 160, 206, 0.12);
}

.cross-topic-item:last-child {
  border-bottom: 0;
}

.cross-topic-item__main {
  min-width: 0;
}

.cross-topic-item__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cross-topic-item__title-row h3 {
  margin: 0;
  font-size: 18px;
}

.cross-topic-item__meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.cross-topic-item__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 980px) {
  .cross-topic-hero {
    grid-template-columns: 1fr;
  }

  .cross-topic-item {
    grid-template-columns: 1fr;
  }
}
</style>
