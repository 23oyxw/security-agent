import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/global-overrides.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: { el: { pagination: { total: '共 {total} 条' } } } })

// P1 优化：仅注册实际使用的图标组件，避免 200+ 全量注册
const usedIcons = [
  'ArrowLeft', 'ArrowRight', 'Bell', 'CaretRight', 'CircleCheck',
  'CircleCheckFilled', 'CircleCloseFilled', 'Clock', 'Coin', 'Connection',
  'CopyDocument', 'Cpu', 'DataAnalysis', 'DataLine', 'Delete', 'FullScreen',
  'Grid', 'Loading', 'Lock', 'MagicStick', 'Promotion', 'Reading', 'Refresh',
  'Search', 'SetUp', 'SwitchButton', 'Terminal', 'User', 'WarningFilled',
]
usedIcons.forEach(name => {
  if (ElementPlusIconsVue[name]) {
    app.component(name, ElementPlusIconsVue[name])
  }
})

app.mount('#app')
