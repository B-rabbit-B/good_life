// 对话底座选的照片交给拍照识别页（/photos/new）：只放在模块内存里，取走即清空；不写任何存储，刷新页面就没有了。
let pending: File | null = null

export function setPendingPhoto(file: File): void {
  pending = file
}

/** 退出登录或登录失效时丢掉还没交出去的照片（不留给下一个登录的人） */
export function clearPendingPhoto(): void {
  pending = null
}

/** 看一眼有没有交来的照片，不取走（渲染时用；真正取走在副作用里，渲染被丢弃时照片不会丢） */
export function peekPendingPhoto(): File | null {
  return pending
}

/** 拍照识别页打开时取走对话页交来的照片；没有时为 null */
export function takePendingPhoto(): File | null {
  const file = pending
  pending = null
  return file
}
