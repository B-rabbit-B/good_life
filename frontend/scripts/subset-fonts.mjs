// 生成两个自托管字体子集与回退字体的度量规则（pnpm fonts）。
// 源文件放在 .font-cache/（不提交）：
//   NotoSerifSC-Bold.otf            github.com/notofonts/noto-cjk 的 Serif/SubsetOTF/SC（OFL-1.1）
//   SourceSerif4Variable-Roman.ttf  github.com/adobe-fonts/source-serif 的发布包 VAR/（OFL-1.1）
// 输出（提交）：public/fonts/gl-serif-700.woff2、public/fonts/gl-num-500.woff2、
//   src/styles/fonts.css、src/styles/fonts-manifest.json
// 两个子集是 OFL 所说的修改版：改名为 GL Serif 与 GL Num（不用保留字体名“Source”），保留版权与许可证名称记录，
// 许可证全文与版权见 public/fonts/OFL.txt。
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const at = (path) => join(root, path)

const SERIF_SOURCE = at('.font-cache/NotoSerifSC-Bold.otf')
const NUM_SOURCE = at('.font-cache/SourceSerif4Variable-Roman.ttf')
const NUM_INSTANCE = at('.font-cache/ss4-500.ttf')
const SERIF_OUT = 'public/fonts/gl-serif-700.woff2'
const NUM_OUT = 'public/fonts/gl-num-500.woff2'
const NUM_CHARS = '0123456789,.:/-×%'
// local() 只认字体的完整名或 PostScript 名，不认字族名，所以每个字重各列一组：苹方、微软雅黑、思源黑体（Noto Sans CJK）
const FALLBACK_SRC = {
  serif: ['PingFangSC-Semibold', 'PingFang SC Semibold', 'Microsoft YaHei Bold', 'MicrosoftYaHei-Bold',
    'NotoSansCJKsc-Bold', 'Noto Sans CJK SC Bold'],
  // 数字是 500：苹方与思源黑体用 Medium；微软雅黑没有 Medium，用常规体
  num: ['PingFangSC-Medium', 'PingFang SC Medium', 'Microsoft YaHei', 'MicrosoftYaHei',
    'NotoSansCJKsc-Medium', 'Noto Sans CJK SC Medium'],
}
const localSrc = (names) => names.map((name) => `local("${name}")`).join(', ')
// 回退黑体的数字平均字宽（em）：微软雅黑常规体（msyh.ttc，Microsoft YaHei / MicrosoftYaHei）实测 1201/2048。
// 苹方 Medium 与思源黑体 Medium 没有在本机实测（Windows 上没有这两个字体）。
const FALLBACK_DIGIT_EM = 1201 / 2048

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
    // 固定时间戳：fontTools 按 SOURCE_DATE_EPOCH 写 head.modified，同样的输入生成逐字节相同的文件
    env: { ...process.env, PYTHONUTF8: '1', SOURCE_DATE_EPOCH: '1760227200' },
  })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`${command} ${args.join(' ')} 失败（退出码 ${result.status}）`)
  return result.stdout
}

// 去掉 CFF 提示、展开子程序：字形不变（手机高分屏不用提示），woff2 压缩后宋体子集小约四分之一
// 名称记录保留 0（版权）、13 与 14（许可证说明与网址），以及 1 到 6（字体名，随后由 font_names.py 改名）
// fonttools 钉确切版本（uvx 当前缓存里用的版本），换版本前先核对子集结果与 docs/01-交付物/依赖许可证.md
const PYFTSUBSET = ['--from', 'fonttools[woff]==4.66.1', 'pyftsubset', '--no-hinting', '--desubroutinize',
  '--name-IDs=0,1,2,3,4,5,6,13,14']

function rename(file, family, style, note) {
  run('uv', ['run', '--no-project', '--with', 'fonttools[woff]==4.66.1', 'python', 'scripts/font_names.py', file, family, style,
    note])
}

function fontMetrics(font, coversFile) {
  const args = ['run', '--no-project', '--with', 'fonttools==4.66.1', 'python', 'scripts/font_metrics.py', font]
  if (coversFile) args.push('--covers', coversFile)
  return JSON.parse(run('uv', args))
}

for (const source of [SERIF_SOURCE, NUM_SOURCE]) {
  try {
    statSync(source)
  } catch {
    console.error(`缺少字体源文件 ${source}，来源见本脚本开头的注释`)
    process.exit(1)
  }
}

// 宋体子集：全部写死的标题加 SERIF_EXTRA。titles.ts 是 TypeScript，这里直接读同一份 titles.json 与常量
const titles = JSON.parse(readFileSync(at('src/lib/titles.json'), 'utf8'))
const titlesSource = readFileSync(at('src/lib/titles.ts'), 'utf8')
const extraMatch = titlesSource.match(/export const SERIF_EXTRA = '([^']*)'/)
if (!extraMatch) throw new Error('src/lib/titles.ts 里找不到 SERIF_EXTRA')
const wanted = [...new Set(Array.from(Object.values(titles).join('') + extraMatch[1]))].sort().join('')

const scratch = mkdtempSync(join(tmpdir(), 'gl-fonts-'))
try {
  const textFile = join(scratch, 'serif.txt')
  writeFileSync(textFile, wanted, 'utf8')
  run('uvx', [...PYFTSUBSET, SERIF_SOURCE, `--text-file=${textFile}`, '--flavor=woff2',
    '--layout-features=palt,kern', `--output-file=${SERIF_OUT}`])
  rename(SERIF_OUT, 'GL Serif', 'Bold',
    'Modified Version (subset, renamed). See OFL.txt.')
  const serif = fontMetrics(SERIF_SOURCE, textFile)
  const missing = Array.from(wanted).filter((char) => !serif.covered.includes(char))
  if (missing.length > 0) throw new Error(`思源宋体缺这些字：${missing.join('')}`)
  delete serif.covered

  // 数字子集：先固定成 500 字重、16 号光学尺寸的静态字体，再取数字与符号
  run('uvx', ['--from', 'fonttools[woff]==4.66.1', 'fonttools', 'varLib.instancer', NUM_SOURCE, 'wght=500', 'opsz=16',
    '-o', NUM_INSTANCE])
  run('uvx', [...PYFTSUBSET, NUM_INSTANCE, `--text=${NUM_CHARS}`, '--flavor=woff2',
    '--layout-features=tnum,lnum', `--output-file=${NUM_OUT}`])
  rename(NUM_OUT, 'GL Num', 'Medium',
    'Modified Version (instanced, subset, renamed; not Source Serif 4). See OFL.txt.')
  const num = fontMetrics(NUM_INSTANCE)

  const percent = (value) => `${(value * 100).toFixed(2)}%`
  // 回退字体的度量按 size-adjust 缩放，所以覆盖值要先除以它
  const overrides = (metrics, sizeAdjust) => [
    `  ascent-override: ${percent(metrics.ascender / metrics.unitsPerEm / sizeAdjust)};`,
    `  descent-override: ${percent(-metrics.descender / metrics.unitsPerEm / sizeAdjust)};`,
    `  size-adjust: ${percent(sizeAdjust)};`,
  ]
  const serifAdjust = 1 // 标题都是全宽汉字，宽度本来就一样
  const numAdjust = num.digitAdvance / num.unitsPerEm / FALLBACK_DIGIT_EM

  const css = [
    '/* 由 pnpm fonts（scripts/subset-fonts.mjs）生成，不要手改 */',
    '@font-face {',
    "  font-family: 'GL Serif';",
    "  src: url('/fonts/gl-serif-700.woff2') format('woff2');",
    '  font-weight: 700;',
    '  font-style: normal;',
    '  font-display: swap;',
    '}',
    '',
    '@font-face {',
    "  font-family: 'GL Num';",
    "  src: url('/fonts/gl-num-500.woff2') format('woff2');",
    '  font-weight: 500;',
    '  font-style: normal;',
    '  font-display: swap;',
    '}',
    '',
    '/* 字体到达前的回退：系统黑体按网页字体的度量对齐，换字体时不跳动 */',
    '@font-face {',
    "  font-family: 'GL Serif Fallback';",
    `  src: ${localSrc(FALLBACK_SRC.serif)};`,
    '  font-weight: 700;',
    ...overrides(serif, serifAdjust),
    '}',
    '',
    '@font-face {',
    "  font-family: 'GL Num Fallback';",
    `  src: ${localSrc(FALLBACK_SRC.num)};`,
    '  font-weight: 500;',
    ...overrides(num, numAdjust),
    '}',
    '',
  ].join('\n')
  writeFileSync(at('src/styles/fonts.css'), css, 'utf8')

  const manifest = {
    serifChars: wanted,
    serifBytes: statSync(at(SERIF_OUT)).size,
    numChars: NUM_CHARS,
    numBytes: statSync(at(NUM_OUT)).size,
    metrics: { serif, num, fallbackDigitEm: FALLBACK_DIGIT_EM },
  }
  writeFileSync(at('src/styles/fonts-manifest.json'), JSON.stringify(manifest, null, 2) + '\n', 'utf8')
  console.log(`宋体子集 ${Array.from(wanted).length} 字，${manifest.serifBytes} 字节；`
    + `数字子集 ${Array.from(NUM_CHARS).length} 字，${manifest.numBytes} 字节`)
} finally {
  rmSync(scratch, { recursive: true, force: true })
}
