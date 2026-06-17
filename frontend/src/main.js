import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/global-overrides.css'
import './styles/cinematic.css'
import './styles/page-themes.css'
import './styles/component-surfaces.css'
import './styles/chart-surfaces.css'
import './styles/motion-system.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
// 同步加载 mock 模块（内部按 VITE_MOCK 决定是否拦截）
import './api/mock'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: { el: { pagination: { total: '共 {total} 条' } } } })

// P1 优化：仅注册实际使用的图标组件，避免 200+ 全量注册
const usedIcons = [
  'ArrowLeft', 'ArrowRight', 'Bell', 'CaretRight', 'ChatDotRound',
  'CircleCheck', 'CircleCheckFilled', 'CircleCloseFilled', 'Clock',
  'Coin', 'Connection', 'CopyDocument', 'Cpu', 'DataAnalysis',
  'DataLine', 'Delete', 'Document', 'EditPen', 'Expand', 'Fold', 'FullScreen',
  'Grid', 'InfoFilled', 'List', 'Loading', 'Lock', 'MagicStick', 'Monitor',
  'Odometer', 'Promotion', 'Reading', 'Refresh', 'Search', 'SetUp', 'Share',
  'SwitchButton', 'Terminal', 'TrendCharts', 'User', 'UserFilled', 'View', 'WarningFilled',
  'Finished',
]
usedIcons.forEach(name => {
  if (ElementPlusIconsVue[name]) {
    app.component(name, ElementPlusIconsVue[name])
  }
})

app.mount('#app')
