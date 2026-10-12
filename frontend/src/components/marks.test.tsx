import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConfidenceCells } from './ConfidenceCells'
import { RefTag } from './RefTag'
import { VerdictMark } from './VerdictMark'

describe('marks', () => {
  it('renders the reference tag', () => {
    render(<RefTag />)
    const tag = screen.getByText('仅供参考')
    expect(tag.tagName).toBe('SPAN')
    expect(tag).toHaveClass('ref')
  })

  it('renders the four verdict shapes with default words', () => {
    const cases = [
      ['suitable', 'vd-ok', '适合'],
      ['caution', 'vd-warn', '注意'],
      ['not_recommended', 'vd-no', '不建议'],
      ['unchecked', 'vd-un', '未核对'],
    ] as const
    for (const [conclusion, cls, word] of cases) {
      const { unmount } = render(<VerdictMark conclusion={conclusion} />)
      expect(screen.getByText(word)).toHaveClass('vd', cls)
      unmount()
    }
    render(<VerdictMark conclusion="suitable" label="已连通" />)
    expect(screen.getByText('已连通')).toHaveClass('vd', 'vd-ok')
  })

  it('lights confidence cells and names the level', () => {
    const cases = [
      [0.91, 5, '高', '把握程度 0.91，高'],
      [0.84, 4, '中', '把握程度 0.84，中'],
      [0.58, 3, '低', '把握程度 0.58，低'],
      [0.05, 1, '低', '把握程度 0.05，低'],
    ] as const
    for (const [value, lit, word, label] of cases) {
      const { unmount } = render(<ConfidenceCells value={value} />)
      const img = screen.getByRole('img', { name: label })
      expect(img).toHaveClass('conf')
      expect(img.querySelectorAll('.cells b')).toHaveLength(5)
      expect(img.querySelectorAll('.cells b.on')).toHaveLength(lit)
      expect(img).toHaveTextContent(word)
      unmount()
    }
  })
})
