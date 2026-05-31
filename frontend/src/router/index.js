import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SearchView from '../views/SearchView.vue'
import DetailView from '../views/DetailView.vue'
import PlatformView from '../views/PlatformView.vue'
import CrossPlatformView from '../views/CrossPlatformView.vue'
import HistoryView from '../views/HistoryView.vue'
import CrossTopicDetailView from '../views/CrossTopicDetailView.vue'

const APP_TITLE = '跨平台热点聚合分析器'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { title: '首页' }
  },
  {
    path: '/search',
    name: 'search',
    component: SearchView,
    meta: { title: '搜索结果' }
  },
  {
    path: '/detail/:id',
    name: 'detail',
    component: DetailView,
    meta: { title: '热点详情' }
  },
  {
    path: '/platform/:platform',
    name: 'platform',
    component: PlatformView,
    meta: { title: '平台榜单' }
  },
  {
    path: '/cross-platform',
    name: 'crossPlatform',
    component: CrossPlatformView,
    meta: { title: '跨平台热点' }
  },
  {
    path: '/cross-platform/topic/:id',
    name: 'crossPlatformTopic',
    component: CrossTopicDetailView,
    meta: { title: '跨平台主题详情' }
  },
  {
    path: '/history',
    name: 'history',
    component: HistoryView,
    meta: { title: '历史榜单' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.afterEach(to => {
  document.title = `${to.meta?.title || '页面'} - ${APP_TITLE}`
})

export default router
