import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { theme: 'ops' } },
      { path: 'agent', name: 'Agent', component: () => import('../views/AgentChat.vue'), meta: { theme: 'intel' } },
      { path: 'safety', name: 'Safety', component: () => import('../views/SafetyGate.vue'), meta: { theme: 'guard' } },
      { path: 'alerts', name: 'Alerts', component: () => import('../views/Alerts.vue'), meta: { theme: 'alert' } },
      { path: 'mcp', name: 'MCP', component: () => import('../views/MCPManage.vue'), meta: { theme: 'mesh' } },
      { path: 'trace', name: 'Trace', component: () => import('../views/TraceView.vue'), meta: { theme: 'audit' } },
      { path: 'knowledge', name: 'Knowledge', component: () => import('../views/Knowledge.vue'), meta: { theme: 'archive' } },
      { path: 'guide', name: 'Guide', component: () => import('../views/GuidePage.vue'), meta: { theme: 'learn' } },
      { path: 'canvas', name: 'Canvas', component: () => import('../views/InfiniteCanvas.vue'), meta: { theme: 'canvas' } },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { admin: true, theme: 'admin' } },
    ],
  },
  // 隐藏路由
  { path: '/executor', name: 'Executor', component: () => import('../views/Executor.vue'), meta: { hidden: true, theme: 'guard' } },
  { path: '/flows', name: 'SkillFlows', component: () => import('../views/SkillFlows.vue'), meta: { hidden: true, theme: 'mesh' } },
  { path: '/workflow', name: 'Workflow', component: () => import('../views/WorkflowView.vue'), meta: { hidden: true, theme: 'audit' } },
  { path: '/blue-team', name: 'BlueTeam', component: () => import('../views/BlueTeam.vue'), meta: { hidden: true, theme: 'guard' } },
  // 404 兜底 — 所有未匹配路由重定向到首页
  { path: '/:pathMatch(.*)*', name: 'NotFound', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

let isAuthInitialized = false

router.beforeEach(async (to, from, next) => {
  // 从 Pinia store 读取 token（而非直接读 localStorage）
  // Pinia 持久化插件存储在 security-agent-user key 中
  const store = useUserStore()
  const token = store.token

  // 无 token 且非公开页面 → 登录
  if (!to.meta.public && !token) return next('/login')

  // 已登录用户访问登录页 → 跳转首页
  if (to.meta.public && token) return next('/')

  // 有 token + 非公开页面 + 首次初始化
  if (!isAuthInitialized && token && !to.meta.public) {
    if (!store.username) {
      try {
        await store.fetchMe()
        isAuthInitialized = true
      } catch (e) {
        if (e.response?.status === 401) {
          store.logout()
          return next('/login')
        }
        console.warn('Auth fetch failed, will retry on next navigation')
      }
    } else {
      isAuthInitialized = true
    }
  }

  // 管理员路由守卫
  if (to.meta.admin) {
    if (store.role !== 'admin') return next('/')
  }

  next()
})

export default router
