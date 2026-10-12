// 对话底座选的照片交给拍照识别页（/photos/new）：只放在模块内存里，取走即清空；不写任何存储，刷新页面就没有了。
let pending: File | null = null

export function setPendingPhoto(file: File): void {
  pending = file
}

/** 拍照识别页打开时取走对话页交来的照片；没有时为 null */
export function takePendingPhoto(): File | null {
  const file = pending
  pending = null
  return file
}
