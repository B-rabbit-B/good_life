import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * 外壳（导航、对话底座、操作坞、面板、轻提示）渲染进 #shell-root：它与 #root 同级，不在任何 overflow:hidden 的容器里，
 * WebKit 的 backdrop-filter 才取得到背后的内容。没有 #shell-root（例如单元测试）时放进 body。
 */
export function ShellPortal({ children }: { children: ReactNode }) {
  return createPortal(children, document.getElementById('shell-root') ?? document.body)
}

export function shellRoot(): HTMLElement {
  return document.getElementById('shell-root') ?? document.body
}
