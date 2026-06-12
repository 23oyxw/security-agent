import { onMounted, onUnmounted, nextTick } from 'vue'

/**
 * 滚动入场揭示 — Intersection Observer
 * 给容器内 .reveal-item 元素加 .is-visible
 */
export function useStaggerReveal(rootRef, options = {}) {
  const { threshold = 0.12, rootMargin = '0px 0px -40px 0px' } = options
  let observer = null

  function observeAll() {
    const root = rootRef?.value
    if (!root) return

    if (typeof IntersectionObserver === 'undefined') {
      root.querySelectorAll('.reveal-item').forEach(el => el.classList.add('is-visible'))
      return
    }

    if (!observer) {
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-visible')
              observer.unobserve(entry.target)
            }
          })
        },
        { threshold, rootMargin }
      )
    }

    root.querySelectorAll('.reveal-item:not(.is-visible)').forEach(el => observer.observe(el))
  }

  onMounted(() => nextTick(observeAll))
  onUnmounted(() => observer?.disconnect())

  return { refresh: () => nextTick(observeAll) }
}
