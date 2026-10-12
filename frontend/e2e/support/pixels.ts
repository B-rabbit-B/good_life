// 从截图里取像素：Playwright 截图是 PNG，这里用 Node 自带的 zlib 解码（只支持截图用到的 8 位 RGB 与 RGBA、非隔行）。
import type { Page } from '@playwright/test'
import { inflateSync } from 'node:zlib'

export interface Rgb {
  r: number
  g: number
  b: number
}

function decodePng(png: Buffer): { width: number; height: number; channels: number; pixels: Buffer } {
  let offset = 8 // PNG 签名
  let width = 0
  let height = 0
  let channels = 0
  const idat: Buffer[] = []
  while (offset < png.length) {
    const length = png.readUInt32BE(offset)
    const type = png.toString('ascii', offset + 4, offset + 8)
    const data = png.subarray(offset + 8, offset + 8 + length)
    if (type === 'IHDR') {
      width = data.readUInt32BE(0)
      height = data.readUInt32BE(4)
      const bitDepth = data[8]
      const colorType = data[9]
      const interlace = data[12]
      if (bitDepth !== 8 || interlace !== 0 || (colorType !== 2 && colorType !== 6)) {
        throw new Error(`不支持的 PNG：位深 ${bitDepth}，颜色类型 ${colorType}，隔行 ${interlace}`)
      }
      channels = colorType === 6 ? 4 : 3
    } else if (type === 'IDAT') {
      idat.push(data)
    } else if (type === 'IEND') {
      break
    }
    offset += 12 + length
  }
  const raw = inflateSync(Buffer.concat(idat))
  const stride = width * channels
  const pixels = Buffer.alloc(stride * height)
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)]
    for (let x = 0; x < stride; x += 1) {
      const value = raw[y * (stride + 1) + 1 + x] ?? 0
      const left = x >= channels ? (pixels[y * stride + x - channels] ?? 0) : 0
      const up = y > 0 ? (pixels[(y - 1) * stride + x] ?? 0) : 0
      const upLeft = y > 0 && x >= channels ? (pixels[(y - 1) * stride + x - channels] ?? 0) : 0
      let predicted = 0
      if (filter === 1) predicted = left
      else if (filter === 2) predicted = up
      else if (filter === 3) predicted = Math.floor((left + up) / 2)
      else if (filter === 4) {
        const p = left + up - upLeft
        const pa = Math.abs(p - left)
        const pb = Math.abs(p - up)
        const pc = Math.abs(p - upLeft)
        predicted = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft
      }
      pixels[y * stride + x] = (value + predicted) & 0xff
    }
  }
  return { width, height, channels, pixels }
}

/** 截下以 (x, y) 为左上角、size × size 的一块视口（CSS 像素），返回其中每个像素的颜色。 */
export async function samplePixels(page: Page, x: number, y: number, size = 4): Promise<Rgb[]> {
  const png = await page.screenshot({ clip: { x, y, width: size, height: size } })
  const { width, height, channels, pixels } = decodePng(png)
  const out: Rgb[] = []
  for (let i = 0; i < width * height; i += 1) {
    out.push({ r: pixels[i * channels] ?? 0, g: pixels[i * channels + 1] ?? 0, b: pixels[i * channels + 2] ?? 0 })
  }
  return out
}

export const hex = ({ r, g, b }: Rgb) => `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('').toUpperCase()}`
