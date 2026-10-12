// 由后端导出接口快照 src/api/openapi.json，再生成类型 src/api/schema.d.ts。两个文件都提交进仓库。
import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { generateSchemaSource } from './gen-api-lib.mjs'

const frontend = fileURLToPath(new URL('..', import.meta.url))
const snapshot = new URL('../src/api/openapi.json', import.meta.url)
const schema = new URL('../src/api/schema.d.ts', import.meta.url)

const exported = spawnSync(
  'uv',
  ['run', '--directory', '../backend', 'python', '-m', 'app.openapi_export', '../frontend/src/api/openapi.json'],
  { stdio: 'inherit', cwd: frontend, env: { ...process.env, PYTHONUTF8: '1' } },
)
if (exported.error) throw exported.error
if (exported.status !== 0) {
  console.error(`导出接口快照失败（退出码 ${exported.status}）`)
  process.exit(exported.status ?? 1)
}

const openapi = JSON.parse(readFileSync(snapshot, 'utf8'))
writeFileSync(schema, await generateSchemaSource(openapi), 'utf8')
console.log('已写出 src/api/schema.d.ts')
