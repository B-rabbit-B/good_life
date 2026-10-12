// @vitest-environment node
import { describe, expect, it } from 'vitest'
import manifest from '../styles/fonts-manifest.json'
import { SERIF_EXTRA, TITLES } from './titles'

const SERIF_MAX_BYTES = 40 * 1024
const PRELOAD_MAX_BYTES = 45 * 1024 // 45,056 B：宋体上限 40 KB 加数字子集与约 2 KB 余量

describe('fixed titles and font subsets', () => {
  it('serif subset covers every fixed title', () => {
    const covered = new Set(Array.from(manifest.serifChars))
    const needed = new Set(Array.from(Object.values(TITLES).join('') + SERIF_EXTRA))
    const missing = [...needed].filter((char) => !covered.has(char))
    expect(missing, '宋体子集缺字：在 frontend 下运行 pnpm fonts').toEqual([])
  })

  it('font subsets stay within budget', () => {
    expect(manifest.serifBytes).toBeLessThanOrEqual(SERIF_MAX_BYTES)
    expect(manifest.serifBytes + manifest.numBytes).toBeLessThanOrEqual(PRELOAD_MAX_BYTES)
  })
})
