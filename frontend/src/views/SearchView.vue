<template>
  <div class="app-container page-stack">
    <section class="page-hero search-hero">
      <span class="page-hero__eyebrow">跨平台检索</span>
      <h1 class="page-hero__title">热点搜索</h1>
      <p class="page-hero__subtitle">
        支持跨平台关键词检索，统一展示微博、抖音、B站中已入库的热点结果，便于快速定位正在传播的话题内容。
      </p>

      <div class="search-hero__toolbar">
        <el-input
          v-model="inputKeyword"
          clearable
          size="large"
          placeholder="输入关键词重新搜索"
          @keyup.enter="applySearch"
          @clear="applySearch"
        >
          <template #append>
            <el-button type="primary" @click="applySearch">搜索</el-button>
          </template>
        </el-input>

        <div class="search-hero__meta">
          <span class="search-hero__meta-item">当前关键词：{{ keyword || '未输入' }}</span>
          <span class="search-hero__meta-item">结果数量：{{ results.length }}</span>
        </div>
      </div>
    </section>

    <RequestState
      compact
      :loading="loading"
      :error="error"
      :empty="!loading && !error && !keyword"
      empty-description="请输入关键词开始搜索"
      @retry="loadSearchResult"
    >
      <template v-if="keyword">
        <RequestState
          compact
          :loading="false"
          :error="''"
          :empty="!loading && !error && results.length === 0"
          empty-description="没有搜索到相关热点，请尝试更换关键词"
        >
          <section class="table-card search-panel">
            <div class="section-head search-section-head">
              <div>
                <h2 class="section-title">搜索结果列表</h2>
                <p class="section-subtitle">点击任意结果可进入热点详情页，继续查看热点解读、趋势变化和来源信息。</p>
              </div>
              <el-tag type="primary" effect="plain">关键词：{{ keyword }}</el-tag>
            </div>

            <div class="search-list">
              <article
                v-for="item in results"
                :key="getHotspotId(item, `${item.platform}-${item.title}`)"
                class="search-item"
                @click="goDetail(getHotspotId(item))"
              >
                <div class="search-item__main">
                  <div class="search-item__title-row">
                    <PlatformPill :platform="item.platform" />
                    <h3>{{ cleanTitle(item.title) }}</h3>
                    <el-tag v-if="normalizeTag(item.tags, item.title)" size="small" effect="plain">
                      {{ normalizeTag(item.tags, item.title) }}
                    </el-tag>
                  </div>

                  <div class="search-item__meta">
                    <span>平台内排名：{{ item.rankNum ?? '暂无' }}</span>
                    <span>{{ getPlatformHeatLabel(item.platform) }}：{{ formatHotValue(item.hotValue, item.platform) }}</span>
                    <span>更新时间：{{ formatDateTime(getHotspotTime(item)) }}</span>
                  </div>
                </div>

                <el-button type="primary" plain @click.stop="goDetail(getHotspotId(item))">查看详情</el-button>
              </article>
            </div>
          </section>
        </RequestState>
      </template>
    </RequestState>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PlatformPill from '../components/PlatformPill.vue'
import RequestState from '../components/RequestState.vue'
import { searchHotspots } from '../api/hotspot'
import {
  cleanTitle,
  formatDateTime,
  formatHotValue,
  getHotspotId,
  getHotspotTime,
  getPlatformHeatLabel,
  normalizeTag
} from '../utils/hotspot'

const route = useRoute()
const router = useRouter()

const keyword = ref('')
const inputKeyword = ref('')
const loading = ref(false)
const error = ref('')
const results = ref([])

async function loadSearchResult() {
  const currentKeyword = String(route.query.keyword || '').trim()
  keyword.value = currentKeyword
  inputKeyword.value = currentKeyword

  if (!currentKeyword) {
    results.value = []
    error.value = ''
    return
  }

  loading.value = true
  error.value = ''

  try {
    const result = await searchHotspots(currentKeyword)
    results.value = Array.isArray(result) ? result : []
  } catch (requestError) {
    error.value = requestError?.message || '搜索失败，请稍后重试'
    results.value = []
  } finally {
    loading.value = false
  }
}

function applySearch() {
  const value = inputKeyword.value.trim()
  router.push({
    name: 'search',
    query: { keyword: value || undefined }
  })
}

function goDetail(id) {
  if (!id) return
  router.push({ name: 'detail', params: { id } })
}

watch(
  () => route.fullPath,
  () => {
    loadSearchResult()
  },
  { immediate: true }
)
</script>

<style scoped>
.search-hero__toolbar {
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 780px;
}

.search-hero__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.search-hero__meta-item {
  padding: 10px 12px;
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(135, 160, 206, 0.12);
}

.search-panel {
  padding: 22px;
}

.search-section-head {
  margin-bottom: 14px;
}

.search-list {
  display: flex;
  flex-direction: column;
}

.search-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 15px 4px;
  border-bottom: 1px solid rgba(135, 160, 206, 0.12);
  cursor: pointer;
  transition: transform 0.2s ease;
}

.search-item:last-child {
  border-bottom: 0;
}

.search-item:hover {
  transform: translateX(4px);
}

.search-item__main {
  min-width: 0;
}

.search-item__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-item__title-row h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.5;
}

.search-item__meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .search-item {
    grid-template-columns: 1fr;
  }
}
</style>
