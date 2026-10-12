import { render, screen } from '@testing-library/react'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { describe, expect, it } from 'vitest'
import { Title } from './Title'

// vitest 的工作目录是 frontend/
const SRC = join(process.cwd(), 'src')
const SERIF_CLASS = /(?<![\w-])(t-display|t-title|t-h|st-h)(?![\w-])/

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return tsxFiles(path)
    return path.endsWith('.tsx') && !path.endsWith('.test.tsx') ? [path] : []
  })
}

describe('Title', () => {
  it('renders the fixed title with the serif class of its level', () => {
    const cases = [
      ['display', 'records', 'H1', 't-display', '记录'],
      ['title', 'resolveSheet', 'H2', 't-title', '确认解除这条医嘱'],
      ['h', 'mealEval', 'H3', 't-h', '整餐评价'],
      ['state', 'loadFailed', 'H2', 'st-h', '没能读取'],
    ] as const
    for (const [level, k, tag, cls, text] of cases) {
      const { unmount } = render(<Title k={k} level={level} />)
      const heading = screen.getByRole('heading', { name: text })
      expect(heading.tagName).toBe(tag)
      expect(heading).toHaveClass(cls)
      unmount()
    }
    render(<Title k="chat" level="title" as="h1" id="t-chat" />)
    const heading = screen.getByRole('heading', { name: '对话' })
    expect(heading.tagName).toBe('H1')
    expect(heading).toHaveAttribute('id', 't-chat')
  })

  it('only the title component renders serif title classes', () => {
    const offenders = tsxFiles(SRC)
      .filter((path) => relative(SRC, path).split(sep).join('/') !== 'components/Title.tsx')
      .filter((path) => SERIF_CLASS.test(readFileSync(path, 'utf8')))
      .map((path) => relative(SRC, path))
    expect(offenders).toEqual([])
  })
})
