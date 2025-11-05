import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import History from '@/views/History.vue'
import SessionDetail from '@/views/SessionDetail.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/history',
    name: 'History',
    component: History
  },
  {
    path: '/session/:id',
    name: 'SessionDetail',
    component: SessionDetail
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
