import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'
// 页面名称/主题见 constants/navigation.js — meta.theme 与 Topbar 主题 pill 对齐

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      { path: 'agent', name: 'Agent', component: () => import('../views/AgentChat.vue'), meta: { theme: 'intel', title: '智能体对话' } },
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { theme: 'ops', title: '运维概览' } },
      { path: 'l5', name: 'L5Analytics', component: () => import('../views/L5Analytics.vue'), meta: { theme: 'ops', title: 'L5 链路分析' } },
      { path: 'safety', name: 'Safety', component: () => import('../views/SafetyGate.vue'), meta: { theme: 'guard' } },
      { path: 'alerts', name: 'Alerts', component: () => import('../views/Alerts.vue'), meta: { theme: 'alert' } },
      { path: 'repair', name: 'Repair', component: () => import('../views/RepairPanel.vue'), meta: { theme: 'guard', title: '环境修复' } },
      { path: 'mcp', name: 'MCP', component: () => import('../views/MCPManage.vue'), meta: { theme: 'mesh' } },
      { path: 'trace', name: 'Trace', component: () => import('../views/TraceView.vue'), meta: { theme: 'audit' } },
      { path: 'knowledge', name: 'Knowledge', component: () => import('../views/Knowledge.vue'), meta: { theme: 'archive' } },
      { path: 'perception', name: 'Perception', component: () => import('../views/SituationalOverview.vue'), meta: { theme: 'intel', title: 'L1 态势总览' } },
      { path: 'l1/boundary', name: 'L1Boundary', component: () => import('../views/BoundaryTraining.vue'), meta: { theme: 'intel', title: 'L1 边界对抗' } },
      { path: 'guide', name: 'Guide', component: () => import('../views/GuidePage.vue'), meta: { theme: 'learn' } },
      { path: 'canvas', name: 'Canvas', component: () => import('../views/InfiniteCanvas.vue'), meta: { theme: 'canvas', title: '五层架构画布' } },
      { path: 'workflow', name: 'Workflow', component: () => import('../views/WorkflowView.vue'), meta: { theme: 'audit', title: '流水线观测' } },
      { path: 'reports', name: 'Reports', component: () => import('../views/Reports.vue'), meta: { theme: 'intel', title: '任务分析报表' } },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { admin: true, theme: 'admin' } },
    ],
  },
  // 隐藏路由
  { path: '/executor', name: 'Executor', component: () => import('../views/Executor.vue'), meta: { hidden: true, theme: 'guard' } },
  { path: '/flows', name: 'SkillFlows', component: () => import('../views/SkillFlows.vue'), meta: { hidden: true, theme: 'mesh' } },
  { path: '/blue-team', name: 'BlueTeam', component: () => import('../views/BlueTeam.vue'), meta: { hidden: true, theme: 'guard' } },
  // 404 兜底 — 所有未匹配路由重定向到首页
  { path: '/:pathMatch(.*)*', name: 'NotFound', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

function authInitialized() {
  return sessionStorage.getItem('security-agent-auth-init') === '1'
}

function setAuthInitialized(v) {
  if (v) sessionStorage.setItem('security-agent-auth-init', '1')
  else sessionStorage.removeItem('security-agent-auth-init')
}

router.beforeEach(async (to, from, next) => {
  const store = useUserStore()
  const token = store.token

  if (!token) setAuthInitialized(false)

  // 无 token 且非公开页面 → 登录
  if (!to.meta.public && !token) return next('/login')

  // 已登录用户访问登录页 → 进入对话页
  if (to.meta.public && token) return next('/agent')

  if (!authInitialized() && token && !to.meta.public) {
    try {
      await store.fetchMe()
      setAuthInitialized(true)
    } catch (e) {
      const status = e.response?.status
      if (status === 401 || status === 403) {
        store.logout()
        setAuthInitialized(false)
        return next('/login')
      }
      console.warn('Auth fetch failed, will retry on next navigation')
    }
  }

  // 管理员路由守卫
  if (to.meta.admin) {
    if (store.role !== 'admin') return next('/')
  }

  next()
})

export default router
