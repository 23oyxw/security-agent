/** 统一严重度映射 — 中文版 + 英文版，消除 6 处重复定义 */

// 中文严重度 → ElementUI type
export const SEV_TO_TYPE = {
  '严重': 'danger',
  '高': 'warning',
  '中': '',
  '低': 'success',
  '信息': 'info',
}
export function sevTypeCN(level) { return SEV_TO_TYPE[level] || 'info' }

// 英文严重度 → ElementUI type (用于部分后端返回)
const SEV_EN_TO_TYPE = {
  critical: 'danger',
  high: 'warning',
  medium: '',
  low: 'info',
}
export function sevType(lvl) {
  return SEV_TO_TYPE[lvl] || SEV_EN_TO_TYPE[lvl] || 'info'
}

// 分类标签 → 中文 + 颜色 (供 Knowledge.vue / KB 搜索组件共用)
export const CATEGORY_META = {
  privilege:          { label: '权限管理', color: 'danger' },
  misdelete:          { label: '误删防护', color: 'danger' },
  exfiltration:       { label: '数据外泄', color: 'danger' },
  port_exposure:      { label: '端口暴露', color: 'warning' },
  impersonation:      { label: '进程伪装', color: 'warning' },
  monitoring_gap:     { label: '监控覆盖', color: '' },
  network:            { label: '网络安全', color: '' },
  daily_dev:          { label: '日常运维', color: 'success' },
  advisor:            { label: '处置建议', color: 'info' },
  blue_team:          { label: '入侵排查', color: '' },
  detection:          { label: '威胁检测', color: 'warning' },
  log_analysis:       { label: '日志分析', color: '' },
  audit:              { label: '审计合规', color: 'success' },
  webshell:           { label: 'WebShell', color: 'danger' },
  waf:                { label: 'WAF 防护', color: 'warning' },
  system:             { label: '系统加固', color: '' },
  ids:                { label: 'IDS 检测', color: 'info' },
  intrusion:          { label: '入侵响应', color: 'danger' },
  asset_scan:         { label: '资产扫描', color: '' },
  api_security:       { label: 'API 安全', color: 'info' },
  incident_response:  { label: '应急响应', color: 'danger' },
  knowledge_base:     { label: '知识沉淀', color: 'success' },
  resilience:         { label: '弹性防御', color: 'warning' },
  data:               { label: '数据安全', color: 'warning' },
  server:             { label: '服务安全', color: '' },
  false_positive:     { label: '误报校准', color: 'info' },
  process:            { label: '进程管理', color: '' },
  root:               { label: 'Root 操作', color: 'danger' },
  kylin:              { label: '麒麟适配', color: 'info' },
  sigma:              { label: 'Sigma规则', color: '' },
  ioc:                { label: 'IOC匹配', color: 'warning' },
  docker:             { label: '容器安全', color: 'warning' },
  backup:             { label: '备份恢复', color: 'success' },
}
export function categoryLabel(cat) { return CATEGORY_META[cat]?.label || cat || '通用' }
export function categoryColor(cat) { return CATEGORY_META[cat]?.color || 'info' }
