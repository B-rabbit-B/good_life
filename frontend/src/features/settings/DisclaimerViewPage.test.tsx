import { screen } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'
import { formatTime, todayISO } from '../../lib/dates'
import { DISCLAIMER_VERSION } from '../../test/fixtures/core'
import { renderRoute } from '../../test/render'

beforeAll(async () => {
  await import('./DisclaimerViewPage')
}, 60_000)

describe('disclaimer view page', { timeout: 15_000 }, () => {
  it('shows the text line by line with the version and the confirmation time', async () => {
    renderRoute('/settings/disclaimer')
    expect(await screen.findByText('所有内容仅用于日常生活方式参考。')).toBeInTheDocument()
    expect(screen.getByText('如果身体不适，请以医嘱为准并及时就医。').tagName).toBe('P')
    expect(screen.getByText('经期预测不能用于避孕或诊断。')).toBeInTheDocument()
    expect(screen.getByText(`版本 ${DISCLAIMER_VERSION}`)).toBeInTheDocument()
    const at = '2026-10-01T08:00:00Z'
    expect(await screen.findByText(`已于 ${todayISO(new Date(at))} ${formatTime(at)} 确认这个版本。`)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /确认|同意/ })).not.toBeInTheDocument()
  })
})
