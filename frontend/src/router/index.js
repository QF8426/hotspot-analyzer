import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SearchView from '../views/SearchView.vue'
import DetailView from '../views/DetailView.vue'
import PlatformView from '../views/PlatformView.vue'
import CrossPlatformView from '../views/CrossPlatformView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/search',
    name: 'search',
    component: SearchView
  },
  {
    path: '/detail/:id',
    name: 'detail',
    component: DetailView
  },
  {
    path: '/platform/:platform',
    name: 'platform',
    component: PlatformView
  },
  {
    path: '/cross-platform',
    name: 'crossPlatform',
    component: CrossPlatformView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
