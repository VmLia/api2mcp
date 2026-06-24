import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    redirect: '/frontrouter'
  },
  {
    path: '/frontrouter',
    name: 'Api2mcpList',
    component: () => import('@/views/Api2mcpList.vue')
  },
  {
    path: '/frontrouter/status',
    name: 'ServerStatus',
    component: () => import('@/views/ServerStatus.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
