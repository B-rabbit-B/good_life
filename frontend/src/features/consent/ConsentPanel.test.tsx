import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { CONSENT_TEXTS, CONSENT_VERSION } from '../../test/fixtures/consents'
import { consentHandlers, type ConsentOptions } from '../../test/msw/handlers/consents'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderGated(path: string, opts: ConsentOptions) {
  const result = renderRoute(path)
  const consents = consentHandlers(opts)
  server.use(...consents.handlers)
  return { ...result, consents }
}

// 健康页与录入医嘱页都是按需加载的大块：先加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
  await import('../medical/MedicalNewPage')
}, 60_000)

describe('consent panel', { timeout: 15_000 }, () => {
  it('keeps agree disabled until read and agree is checked', async () => {
    const user = userEvent.setup()
    renderGated('/health/cycle', { granted: { cycle: false } })
    expect(await screen.findByRole('heading', { name: '单独同意：经期记录' })).toBeInTheDocument()
    const agree = screen.getByRole('button', { name: '同意并开始使用' })
    expect(agree).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并同意' }))
    expect(agree).toBeEnabled()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并同意' }))
    expect(agree).toBeDisabled()
  })

  it('shows the backend text and grants on agree', async () => {
    const user = userEvent.setup()
    const { consents } = renderGated('/health/medical/new', { granted: { medical: false } })
    expect(await screen.findByRole('heading', { name: '单独同意：医嘱' })).toBeInTheDocument()
    for (const line of CONSENT_TEXTS.medical.split('\n')) expect(screen.getByText(line)).toBeInTheDocument()
    // 同意之前录入页不出现
    expect(screen.queryByRole('heading', { name: '录入医嘱' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并同意' }))
    await user.click(screen.getByRole('button', { name: '同意并开始使用' }))
    expect(await screen.findByRole('heading', { name: '录入医嘱' })).toBeInTheDocument()
    expect(consents.record.grants).toEqual([{ kind: 'medical', version: CONSENT_VERSION }])
    expect(screen.queryByRole('heading', { name: '单独同意：医嘱' })).not.toBeInTheDocument()
  })

  it('declining does not open the module', async () => {
    const user = userEvent.setup()
    const { router, consents } = renderGated('/me', { granted: { medical: false } })
    expect(await screen.findByRole('heading', { level: 1, name: '我的' })).toBeInTheDocument()
    let medicalRequests = 0
    const count = ({ request }: { request: Request }) => {
      if (new URL(request.url).pathname.startsWith('/api/medical/')) medicalRequests += 1
    }
    server.events.on('request:start', count)
    try {
      await act(async () => {
        await router.navigate('/health/medical')
      })
      await screen.findByRole('heading', { name: '单独同意：医嘱' })
      expect(screen.queryByRole('tablist', { name: '医嘱分类' })).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: '暂不使用' }))
      await waitFor(() => expect(router.state.location.pathname).toBe('/me'))
      expect(consents.record.grants).toEqual([])
      expect(medicalRequests).toBe(0)
    } finally {
      server.events.removeListener('request:start', count)
    }
  })
})
