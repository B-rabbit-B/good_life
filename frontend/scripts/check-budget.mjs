// 首屏预算（对话路由，gzip 后）：脚本 150 KB、样式 22 KB；预加载字体合计 45 KB。pnpm build:check 在构建后运行。
// 计入的块：index.html 入口与对话页（src/features/chat/ChatPage.tsx），以及它们静态导入的全部块；
// 对话页还不存在时（任务 6 之前）只检查入口。
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const root = fileURLToPath(new URL('..', import.meta.url))
const dist = join(root, 'dist')
const KB = 1024
const LIMITS = { script: 150 * KB, style: 22 * KB, font: 45 * KB }
const ENTRY = 'index.html'
const CHAT_ROUTE = 'src/features/chat/ChatPage.tsx'
const FONTS = join(root, 'public', 'fonts')

const manifest = JSON.parse(readFileSync(join(dist, '.vite', 'manifest.json'), 'utf8'))
const starts = [ENTRY, CHAT_ROUTE].filter((key) => key in manifest)
if (!starts.includes(ENTRY)) {
  console.error(`构建清单里没有 ${ENTRY} 入口`)
  process.exit(1)
}

// 从入口与对话页出发，沿静态导入收集全部块
const seen = new Set()
const pending = [...starts]
while (pending.length > 0) {
  const key = pending.pop()
  if (seen.has(key)) continue
  seen.add(key)
  pending.push(...(manifest[key].imports ?? []))
}
const scripts = [...new Set([...seen].map((key) => manifest[key].file).filter((file) => file.endsWith('.js')))]
const styles = [...new Set([...seen].flatMap((key) => manifest[key].css ?? []))]

const gzipSize = (file) => gzipSync(readFileSync(join(dist, file)), { level: 9 }).length
const rows = (files, size) => files.map((file) => ({ file, bytes: size(file) }))
const groups = [
  { name: '脚本（gzip）', limit: LIMITS.script, rows: rows(scripts, gzipSize) },
  { name: '样式（gzip）', limit: LIMITS.style, rows: rows(styles, gzipSize) },
  { name: '预加载字体', limit: LIMITS.font,
    rows: readdirSync(FONTS).filter((f) => f.endsWith('.woff2'))
      .map((file) => ({ file: `fonts/${file}`, bytes: statSync(join(FONTS, file)).size })) },
]

const kb = (bytes) => `${(bytes / KB).toFixed(1)} KB`
console.log(`首屏预算：计入 ${starts.join(' 与 ')}${starts.includes(CHAT_ROUTE) ? '' : '（对话页还不存在，只检查入口）'}`)
let failed = false
for (const group of groups) {
  const total = group.rows.reduce((sum, row) => sum + row.bytes, 0)
  const over = total > group.limit
  failed ||= over
  console.log(`${over ? '超出' : '通过'}  ${group.name} ${kb(total)} / 上限 ${kb(group.limit)}`)
  if (over) {
    for (const row of [...group.rows].sort((a, b) => b.bytes - a.bytes)) console.log(`        ${kb(row.bytes)}  ${row.file}`)
  }
}
process.exit(failed ? 1 : 0)
