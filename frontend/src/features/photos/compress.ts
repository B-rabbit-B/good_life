// 上传前在本机压缩照片：长边超过 2048 时等比缩小，画到画布上转成质量 0.85 的 JPEG（透明处垫白）。
// 解码失败（例如 HEIC、文件损坏）时原样返回文件，交给后端判断格式并给出说明。
const JPEG_QUALITY = 0.85

/** 长边超过 maxEdge 时等比缩小到 maxEdge；否则原样 */
export function targetSize(width: number, height: number, maxEdge = 2048): { width: number; height: number } {
  const longEdge = Math.max(width, height)
  if (longEdge <= maxEdge) return { width, height }
  const scale = maxEdge / longEdge
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}

export async function compressImage(file: File): Promise<Blob> {
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    return file
  }
  try {
    const { width, height } = targetSize(bitmap.width, bitmap.height)
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) return file
    context.fillStyle = '#fff'
    context.fillRect(0, 0, width, height)
    context.drawImage(bitmap, 0, 0, width, height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY))
    return blob ?? file
  } catch {
    return file
  } finally {
    bitmap.close()
  }
}
