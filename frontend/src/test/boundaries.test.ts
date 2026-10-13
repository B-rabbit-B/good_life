// @vitest-environment node
// 分层：扫描 src 下的源码（不含测试）的相对导入，检查依赖方向。
// lib 是最底层的工具与后端副本；api 是接口与缓存；components 是不认业务的界面零件；features 是各页面；app 把它们装起来。
import { readdirSync, readFileSync } from 'node:fs'
import { posix } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// 统一成正斜杠（Windows 上 fileURLToPath 给的是反斜杠），不带末尾斜杠
const ROOT = fileURLToPath(new URL('../', import.meta.url)).replaceAll('\\', '/').replace(/\/$/, '')

/** 显式放行的导入（导入方 -> 被导入模块，都相对 src、不带扩展名）与原因 */
const ALLOWED: Record<string, string> = {
  'lib/labels -> api/schema': '标签映射的枚举类型取自生成的接口类型（只有 import type，不进运行时）',
  'lib/formErrors -> api/errors': '表单错误归位要认 ApiError（errors.ts 只有错误类本身，不依赖任何模块）',
  // 对话页按需加载继续遵守面板（只在 lazy(() => import(...)) 里）：经 features/medical/index 动态引入会把整个医嘱视图
  // （连同标签输入、下拉等，gzip 后约 64 KB）一起下载，直接引入这个模块只下载面板本身
  'features/chat/OpeningCard -> features/medical/ContinueSheet': '按需加载继续遵守面板',
  'features/chat/PendingStrip -> features/medical/ContinueSheet': '按需加载继续遵守面板',
}

/** components 可以引用的 app 模块与原因 */
const COMPONENTS_MAY_USE: Record<string, string> = {
  'app/shellContext': '页头与操作坞要知道外壳的状态（遮盖层、底座高度），外壳上下文只是一个 React context',
  'app/sensitiveAreas': '遮盖组件按敏感区名登记，名字表放在 app 供路由与外壳共用',
}

/** dir 下的源码文件（不含测试文件、src/test 下的测试支撑与类型声明） */
function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = posix.join(dir, entry.name)
    if (entry.isDirectory()) return full === `${ROOT}/test` ? [] : sources(full)
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) && !entry.name.endsWith('.d.ts') ? [full] : []
  })
}

const IMPORT = /(?:from\s+|import\s*\(\s*|import\s+)'(\.{1,2}\/[^']+)'/g

/** 每条相对导入：导入方与被导入模块（相对 src，不带扩展名） */
function edges(): { from: string; to: string }[] {
  return sources(ROOT).flatMap((file) => {
    const from = posix.relative(ROOT, file).replace(/\.tsx?$/, '')
    const text = readFileSync(file, 'utf-8')
    return [...text.matchAll(IMPORT)].map((match) => ({
      from,
      to: posix.normalize(posix.join(posix.dirname(from), match[1] ?? '')).replace(/\.tsx?$/, ''),
    }))
  })
}

const layer = (module: string) => module.split('/')[0] ?? ''

function violations(rule: (from: string, to: string) => boolean): string[] {
  return edges()
    .filter(({ from, to }) => !to.endsWith('.css') && !(`${from} -> ${to}` in ALLOWED) && rule(from, to))
    .map(({ from, to }) => `${from} -> ${to}`)
}

describe('module boundaries', () => {
  it('finds the source files and their imports', () => {
    const all = edges()
    expect(all.length).toBeGreaterThan(500)
    expect(all).toContainEqual({ from: 'app/routes', to: 'app/guards' })
  })

  it('keeps lib free of api', () => {
    expect(violations((from, to) => layer(from) === 'lib' && layer(to) === 'api')).toEqual([])
  })

  it('keeps api free of app, components and features', () => {
    expect(violations((from, to) => layer(from) === 'api' && ['app', 'components', 'features'].includes(layer(to)))).toEqual([])
  })

  it('keeps components free of features and app except the listed ones', () => {
    expect(violations((from, to) =>
      layer(from) === 'components' && ['app', 'features'].includes(layer(to)) && !(to in COMPONENTS_MAY_USE))).toEqual([])
  })

  it('lets one feature use another only through its index', () => {
    const feature = (module: string) => (layer(module) === 'features' ? module.split('/')[1] : undefined)
    expect(violations((from, to) => {
      const target = feature(to)
      const viaIndex = to === `features/${target}` || to === `features/${target}/index`
      return feature(from) !== undefined && target !== undefined && feature(from) !== target && !viaIndex
    })).toEqual([])
  })

  it('loads the continue sheet into chat only lazily', () => {
    for (const file of ['features/chat/OpeningCard.tsx', 'features/chat/PendingStrip.tsx']) {
      const text = readFileSync(`${ROOT}/${file}`, 'utf-8')
      expect(text, file).toContain("lazy(() => import('../medical/ContinueSheet'))")
      expect(text, file).not.toMatch(/from '\.\.\/medical\/ContinueSheet'/)
    }
  })

  it('lists only exceptions that are still used', () => {
    const all = edges()
    const used = new Set(all.map(({ from, to }) => `${from} -> ${to}`))
    expect(Object.keys(ALLOWED).filter((edge) => !used.has(edge))).toEqual([])
    const targets = new Set(all.filter(({ from }) => layer(from) === 'components').map(({ to }) => to))
    expect(Object.keys(COMPONENTS_MAY_USE).filter((to) => !targets.has(to))).toEqual([])
  })
})
