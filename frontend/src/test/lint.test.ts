// @vitest-environment node
// 证明 eslint.config.js 里的几条禁令确实会报错：把代码片段当作仓库里已有文件的内容交给 ESLint（类型信息照常可用）。
import { ESLint } from 'eslint'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const cwd = fileURLToPath(new URL('../../', import.meta.url))
const eslint = new ESLint({ cwd })

async function rulesFired(code: string, filePath = 'src/lib/titles.ts'): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath })
  return (result?.messages ?? []).map((message) => message.ruleId ?? 'fatal')
}

const ANIMATION_IMPORTS = ['framer-motion', 'motion', 'gsap', 'react-spring', '@react-spring/web', 'animejs', 'react-bits',
  'framer-motion/dom']

describe('lint bans', () => {
  it('bans the eventsource global and its property forms', async () => {
    expect(await rulesFired('export const a = new EventSource("/x")\n')).toContain('no-restricted-globals')
    for (const object of ['window', 'globalThis', 'self']) {
      expect(await rulesFired(`export const a = ${object}.EventSource\n`), object).toContain('no-restricted-properties')
    }
    expect(await rulesFired('export const a = window.fetch\n')).not.toContain('no-restricted-properties')
  }, 60_000)

  it('bans every animation library import', async () => {
    for (const name of ANIMATION_IMPORTS) {
      expect(await rulesFired(`import x from '${name}'\nexport default x\n`), name).toContain('no-restricted-imports')
    }
    expect(await rulesFired("import { useState } from 'react'\nexport default useState\n"))
      .not.toContain('no-restricted-imports')
  }, 60_000)

  it('requires e2e specs to take test from the support module', async () => {
    const spec = 'e2e/pages/smoke.spec.ts'
    expect(await rulesFired("import { test } from '@playwright/test'\ntest('x', () => {})\n", spec))
      .toContain('no-restricted-imports')
    expect(await rulesFired("import { expect } from '@playwright/test'\nexport default expect\n", spec))
      .not.toContain('no-restricted-imports')
    expect(await rulesFired("import { test } from '../support/test'\ntest('x', () => {})\n", spec))
      .not.toContain('no-restricted-imports')
    // 同一条规则也管 e2e 里的 js 与 mjs 文件（路径不必真实存在：这些文件不需要类型信息）
    for (const other of ['e2e/pages/lint-case.js', 'e2e/support/lint-case.mjs']) {
      expect(await rulesFired("import { test } from '@playwright/test'\ntest('x', () => {})\n", other), other)
        .toContain('no-restricted-imports')
    }
  }, 60_000)
})
