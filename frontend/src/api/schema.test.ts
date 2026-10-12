// @vitest-environment node
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { generateSchemaSource } from '../../scripts/gen-api-lib.mjs'

const here = (name: string) => new URL(name, import.meta.url)
// Windows 检出时 git 可能把换行改成 CRLF，比较前统一成 LF
const lf = (text: string) => text.replace(/\r\n/g, '\n')

describe('api schema', () => {
  it('generated api types match the committed openapi snapshot', async () => {
    const openapi = JSON.parse(readFileSync(here('./openapi.json'), 'utf8')) as object
    const generated = await generateSchemaSource(openapi)
    const committed = lf(readFileSync(here('./schema.d.ts'), 'utf8'))
    expect(lf(generated) === committed, 'src/api/schema.d.ts 已过期：在 frontend 下运行 pnpm api:gen').toBe(true)
  })
})
