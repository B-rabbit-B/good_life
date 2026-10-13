import { useEffect } from 'react'

// 键盘与地址栏伸缩的区别：小于这个高度的差值当作浏览器自己的工具栏，不算键盘
const MIN_KEYBOARD = 80
// 页面被放大（双指缩放）时不按键盘处理
const MAX_SCALE = 1.01

/**
 * iOS 软键盘弹起时布局视口不变、可见视口变小：在根节点设 --kb（键盘高度）与 data-kb，对话底座贴在键盘上沿、导航那一行隐藏。
 * 安卓靠 viewport 的 interactive-widget=resizes-content，两个视口一起变小，这里量出来是 0。
 */
export function useVisualViewportInset(): void {
  useEffect(() => {
    const viewport = window.visualViewport
    if (!viewport) return undefined
    const root = document.documentElement
    const clear = () => {
      root.style.removeProperty('--kb')
      delete root.dataset.kb
    }
    const update = () => {
      // 双指放大也会让可见视口变小，那不是键盘
      if (viewport.scale > MAX_SCALE) {
        clear()
        return
      }
      const keyboard = Math.round(window.innerHeight - viewport.height - viewport.offsetTop)
      if (keyboard < MIN_KEYBOARD) {
        clear()
        return
      }
      root.style.setProperty('--kb', `${keyboard}px`)
      root.dataset.kb = ''
    }
    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)
    update()
    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
      clear()
    }
  }, [])
}
