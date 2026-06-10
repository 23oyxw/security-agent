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
      { path: 'safety', name: 'Safety', component: () => import('../views/SafetyGate.vue') },
      { path: 'alerts', name: 'Alerts', component: () => import('../views/Alerts.vue') },
      { path: 'mcp', name: 'MCP', component: () => import('../views/MCPManage.vue') },
      { path: 'trace', name: 'Trace', component: () => import('../views/TraceView.vue') },
      { path: 'knowledge', name: 'Knowledge', component: () => import('../views/Knowledge.vue') },
      { path: 'guide', name: 'Guide', component: () => import('../views/GuidePage.vue') },
      { path: 'canvas', name: 'Canvas', component: () => import('../views/InfiniteCanvas.vue') },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { admin: true } },
    ],
  },
  // 隐藏路由
  { path: '/executor', name: 'Executor', component: () => import('../views/Executor.vue'), meta: { hidden: true } },
  { path: '/flows', name: 'SkillFlows', component: () => import('../views/SkillFlows.vue'), meta: { hidden: true } },
  { path: '/workflow', name: 'Workflow', component: () => import('../views/WorkflowView.vue'), meta: { hidden: true } },
  { path: '/blue-team', name: 'BlueTeam', component: () => import('../views/BlueTeam.vue'), meta: { hidden: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

// P0 修复：仅在首次导航时初始化认证，避免每次路由切换冗余请求
let isAuthInitialized = false

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')

  // 无 token 且非公开页面 → 登录
  if (!to.meta.public && !token) return next('/login')

  // 有 token + 非公开页面 + 首次初始化
  if (!isAuthInitialized && token && !to.meta.public) {
    const store = useUserStore()
    store.hydrateFromStorage()
    if (!store.username) {
      try {
        await store.fetchMe()
        isAuthInitialized = true
      } catch (e) {
        // 区分 401 认证失败 vs 网络抖动
        if (e.response?.status === 401) {
          store.logout()
          return next('/login')
        }
        // 网络错误不登出，允许离线使用缓存状态
        console.warn('Auth fetch failed, will retry on next navigation')
      }
    } else {
      isAuthInitialized = true
    }
  }

  // 管理员路由守卫
  if (to.meta.admin) {
    const store = useUserStore()
    if (store.role !== 'admin') return next('/')
  }

  next()
})

export { router, isAuthInitialized }
export default router
