/** 主布局内容区滚动复位（滚动容器为 MainLayout `.content`） */
export function scrollMainContentToTop(behavior = 'instant') {
  const el = document.querySelector('main.content')
  if (!el) return
  try {
    el.scrollTo({ top: 0, left: 0, behavior })
  } catch {
    el.scrollTop = 0
  }
}

/** 将 Element Plus Dialog 正文滚回顶部 */
export function scrollDialogBodyToTop(dialogClass = '') {
  const sel = dialogClass
    ? `.${dialogClass} .el-dialog__body`
    : '.el-dialog__body'
  const body = document.querySelector(sel)
  if (body) body.scrollTop = 0
}