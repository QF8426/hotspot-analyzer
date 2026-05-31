<template>
  <div class="app-container page-stack">
    <section class="page-hero">
      <span class="page-hero__eyebrow">Cross-Platform Intelligence</span>
      <h1 class="page-hero__title">跨平台热点合集</h1>
      <p class="page-hero__subtitle">
        展示系统识别出的多平台共同热点主题，重点体现微博、抖音、B站之间的话题联动情况，并为毕业设计答辩提供可直接演示的主题汇总视图。
      </p>

      <div class="cross-hero__metrics">
        <div class="cross-hero__metric">
          <span>全部主题数</span>
          <strong>{{ topics.length }}</strong>
        </div>
        <div class="cross-hero__metric">
          <span>筛选后主题数</span>
          <strong>{{ filteredTopics.length }}</strong>
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
          <el-select v-model="limit" placeholder="主题数量" @change="loadTopics">
            <el-option :value="30" label="最近 30 条" />
            <el-option :value="60" label="最近 60 条" />
            <el-option :value="100" label="最近 100 条" />
          </el-select>
          <el-button type="primary" @click="loadTopics">刷新主题</el-button>
        </div>
      </div>
    </section>

    <RequestState
      :loading="loading"
      :error="error"
      :empty="!loading && !error && filteredTopics.length === 0"
      empty-description="当前条件下暂无可展示的跨平台热点主题"
      @retry="loadTopics"
    >
      <section class="cross-topic-grid">
        <article
          v-for="topic in filteredTopics"
          :key="topic.id || topic.mainTitle"
          class="table-card cross-topic-card"
        >
          <div class="cross-topic-card__head">
            <div>
              <div class="cross-topic-card__badges">
                <el-tag type="primary" effect="plain">跨平台主题</el-tag>
                <el-tag effect="plain">{{ formatTopicDate(topic.topicDate) }}</el-tag>
              </div>
              <h2 class="cross-topic-card__title">{{ cleanTitle(topic.mainTitle) || '未命名主题' }}</h2>
            </div>

            <div class="cross-topic-card__cta">
              <el-button
                v-if="topic.id"
                type="primary"
                @click="goTopicDetail(topic)"
              >
                查看主题分析
              </el-button>
              <el-button
                v-else-if="getTopicPrimaryHotspot(topic)"
                type="primary"
                @click="goPrimaryHotspot(topic)"
              >
                查看相关热点详情
              </el-button>
            </div>
          </div>

          <div class="cross-topic-card__platforms">
            <PlatformPill
              v-for="platform in getTopicPlatforms(topic)"
              :key="`${topic.id || topic.mainTitle}-${platform}`"
              :platform="platform"
            />
          </div>

          <p class="cross-topic-card__summary">
            {{ buildSummaryText(topic.summary, fallbackSummary(topic), 168) }}
          </p>

          <div class="cross-topic-card__metrics">
            <div class="cross-topic-card__metric">
              <span>关联平台数</span>
              <strong>{{ getTopicPlatforms(topic).length }}</strong>
            </div>
            <div class="cross-topic-card__metric">
              <span>关联热点数</span>
              <strong>{{ topic.hotspotCount || topic.hotspots?.length || 0 }}</strong>
            </div>
            <div class="cross-topic-card__metric">
              <span>综合指标</span>
              <strong>{{ formatHotValue(getTopicTotalHotValue(topic)) }}</strong>
            </div>
          </div>

          <div class="soft-divider"></div>

          <div class="cross-topic-card__related">
            <div class="section-head cross-topic-card__related-head">
              <div>
                <h3>主要关联热点</h3>
                <p>展示该主题下最主要的关联热点，支持继续进入单热点详情页。</p>
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
                description="接口暂未返回关联热点明细，仍可通过主题入口查看聚合信息"
              />
            </div>
          </div>
        </article>
      </section>
    </RequestState>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
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
const limit = ref(60)
const activeFilter = ref('all')
const topics = ref([])

const filteredTopics = computed(() => {
  if (activeFilter.value === 'all') return topics.value

  return topics.value.filter(topic => {
    const platforms = getTopicPlatforms(topic)

    if (activeFilter.value === 'three') {
      return platforms.length >= 3
    }

    const expected = activeFilter.value.split(',')
    return expected.every(platform => platforms.includes(platform)) && platforms.length === expected.length
  })
})

const threePlatformCount = computed(
  () => topics.value.filter(topic => getTopicPlatforms(topic).length >= 3).length
)

const summaryCount = computed(
  () => topics.value.filter(topic => String(topic?.summary || '').trim()).length
)

async function loadTopics() {
  loading.value = true
  error.value = ''

  try {
    const result = await getCrossPlatformTopics({ limit: limit.value })
    topics.value = Array.isArray(result) ? result : []
  } catch (requestError) {
    error.value = requestError?.message || '跨平台主题加载失败，请稍后重试'
    topics.value = []
  } finally {
    loading.value = false
  }
}

function fallbackSummary(topic) {
  const platforms = getTopicPlatforms(topic).map(getPlatformLabel).join('、') || '多个平台'
  return `该主题由系统自动聚合而成，当前已覆盖${platforms}的共同热点，适合作为跨平台传播对比和答辩展示时的主题入口。`
}

function formatTopicDate(value) {
  return value ? formatDate(value) : '日期未标注'
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

function goTopicDetail(topic) {
  if (topic?.id) {
    router.push({ name: 'crossPlatformTopic', params: { id: topic.id } })
    return
  }
  goPrimaryHotspot(topic)
}

function goPrimaryHotspot(topic) {
  const primary = getTopicPrimaryHotspot(topic)
  if (primary) {
    goDetail(getHotspotId(primary))
  }
}

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

.cross-topic-card {
  display: grid;
  gap: 18px;
}

.cross-topic-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.cross-topic-card__badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cross-topic-card__title {
  margin: 14px 0 0;
  font-size: 26px;
  line-height: 1.3;
}

.cross-topic-card__cta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cross-topic-card__platforms {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cross-topic-card__summary {
  margin: 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.85;
}

.cross-topic-card__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.cross-topic-card__metric {
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(245, 249, 255, 0.82);
  border: 1px solid rgba(135, 160, 206, 0.16);
}

.cross-topic-card__metric span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.cross-topic-card__metric strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
  line-height: 1.2;
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
  .cross-hero__metrics,
  .cross-topic-card__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cross-topic-card__head {
    flex-direction: column;
  }
}

@media (max-width: 860px) {
  .cross-related-item {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .cross-hero__metrics,
  .cross-topic-card__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
