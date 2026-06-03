import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'agent', name: 'Agent', component: () => import('../views/AgentChat.vue') },
      { path: 'mcp', name: 'MCP', component: () => import('../views/MCPManage.vue') },
      { path: 'safety', name: 'Safety', component: () => import('../views/SafetyGate.vue') },
      { path: 'flows', name: 'SkillFlows', component: () => import('../views/SkillFlows.vue') },
      { path: 'workflow', name: 'Workflow', component: () => import('../views/WorkflowView.vue') },
      { path: 'executor', name: 'Executor', component: () => import('../views/Executor.vue') },
      { path: 'trace', name: 'Trace', component: () => import('../views/TraceView.vue') },
      { path: 'alerts', name: 'Alerts', component: () => import('../views/Alerts.vue') },
      { path: 'knowledge', name: 'Knowledge', component: () => import('../views/Knowledge.vue') },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { admin: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) return next('/login')
  if (token && !to.meta.public) {
    const store = useUserStore()
    store.hydrateFromStorage()
    if (!store.username) {
      try { await store.fetchMe() } catch { store.logout(); return next('/login') }
    }
  }
  next()
})

export default router