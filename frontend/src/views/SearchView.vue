<template>
  <div class="search-page">
    <div class="top-actions">
      <el-button plain @click="goHome">← 返回首页</el-button>
    </div>

    <div class="page-header">
      <h1>搜索结果</h1>
      <p>当前关键词：{{ keyword || '无' }}</p>

      <div class="search-bar">
        <el-input
          v-model="inputKeyword"
          placeholder="请输入关键词重新搜索"
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

    <el-card shadow="hover">
      <template #header>
        <div class="result-header">
          <span>共找到 {{ resultList.length }} 条结果</span>
        </div>
      </template>

      <div v-if="resultList.length > 0">
        <div
          v-for="item in resultList"
          :key="item.id"
          class="result-item"
          @click="goDetail(item.id)"
        >
          <div class="result-title">{{ item.title }}</div>

          <div class="result-meta">
            <span>平台：{{ item.platform }}</span>
            <span>热度：{{ item.hotValue }}</span>
            <span>平台内排名：{{ item.rankNum }}</span>
          </div>
        </div>
      </div>

      <el-empty v-else description="没有搜索到相关热点" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { searchHotspots } from '../api/hotspot'

const route = useRoute()
const router = useRouter()

const keyword = ref('')
const inputKeyword = ref('')
const resultList = ref([])

const loadSearchResult = async () => {
  const currentKeyword = route.query.keyword?.toString().trim() || ''
  keyword.value = currentKeyword
  inputKeyword.value = currentKeyword

  if (!currentKeyword) {
    resultList.value = []
    return
  }

  try {
    resultList.value = await searchHotspots(currentKeyword)
    console.log('搜索结果 = ', resultList.value)
  } catch (error) {
    console.error('搜索失败：', error)
    ElMessage.error('搜索失败，请稍后重试')
  }
}

const handleSearch = () => {
  const value = inputKeyword.value.trim()
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

const goHome = () => {
  router.push('/')
}

const goDetail = (id) => {
  console.log('准备跳转详情页，id = ', id)
  router.push(`/detail/${id}`)
}

watch(
  () => route.query.keyword,
  () => {
    loadSearchResult()
  }
)

onMounted(() => {
  loadSearchResult()
})
</script>

<style scoped>
.search-page {
  max-width: 1000px;
  margin: 30px auto;
  padding: 20px;
}

.top-actions {
  margin-bottom: 18px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 32px;
  margin-bottom: 10px;
}

.page-header p {
  color: #666;
  margin-bottom: 16px;
}

.search-bar {
  max-width: 600px;
}

.result-header {
  font-weight: bold;
}

.result-item {
  padding: 16px 0;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: all 0.2s;
}

.result-item:hover {
  background: #f8f9fb;
}

.result-item:last-child {
  border-bottom: none;
}

.result-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #303133;
}

.result-meta {
  display: flex;
  gap: 20px;
  color: #909399;
  font-size: 14px;
}
</style>