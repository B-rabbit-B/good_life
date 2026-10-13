import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { gate } from '../../test/chat'
import { DISCLAIMER_VERSION, disclaimerStatus } from '../../test/fixtures/core'
import { disclaimerText, emptyProfile } from '../../test/fixtures/profile'
import { profileStore } from '../../test/msw/handlers/auth'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const confirmButton = () => screen.getByRole('button', { name: '确认并继续' })

describe('disclaimer page', () => {
  it('shows the backend text line by line with its version', async () => {
    renderRoute('/disclaimer', { accepted: false })
    const list = await screen.findByRole('list')
    expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      '所有内容仅用于日常生活方式参考。',
      '如果身体不适，请以医嘱为准并及时就医。',
      '经期预测不能用于避孕或诊断。',
    ])
    expect(screen.getByRole('heading', { level: 1, name: '免责声明' })).toBeInTheDocument()
    expect(screen.getByText(`版本 ${DISCLAIMER_VERSION}`)).toBeInTheDocument()
  })

  it('enables confirm only after the checkbox', async () => {
    const user = userEvent.setup()
    renderRoute('/disclaimer', { accepted: false })
    await screen.findByRole('list')
    expect(confirmButton()).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' }))
    expect(confirmButton()).toBeEnabled()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' }))
    expect(confirmButton()).toBeDisabled()
  })

  it('accepts the shown version and continues to onboarding', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/disclaimer', { accepted: false })
    let accepted = false
    const sent: unknown[] = []
    const store = profileStore(emptyProfile())
    server.use(
      ...store.handlers,
      http.get('/api/disclaimer/status', () => HttpResponse.json(disclaimerStatus(accepted))),
      http.post('/api/disclaimer/accept', async ({ request }) => {
        sent.push(await request.json())
        accepted = true
        return HttpResponse.json(disclaimerStatus(true))
      }),
    )
    await screen.findByRole('list')
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' }))
    await user.click(confirmButton())

    await waitFor(() => expect(router.state.location.pathname).toBe('/onboarding/1'))
    expect(sent).toEqual([{ version: DISCLAIMER_VERSION }])
    expect(await screen.findByRole('heading', { level: 1, name: '基本信息' })).toBeInTheDocument()
  })

  it('reloads on disclaimer_outdated and shows the message', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/disclaimer', { accepted: false })
    let version = DISCLAIMER_VERSION
    server.use(
      http.get('/api/disclaimer', () => HttpResponse.json(disclaimerText({
        version, text: version === DISCLAIMER_VERSION ? '旧的第一条。' : '新的第一条。\n新的第二条。',
      }))),
      http.post('/api/disclaimer/accept', () => {
        version = '2026-12-01'
        return HttpResponse.json(
          { error: { code: 'disclaimer_outdated', message: '免责声明已更新，请重新阅读最新版本后确认' } }, { status: 409 },
        )
      }),
    )
    expect(await screen.findByText('旧的第一条。')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' }))
    await user.click(confirmButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('免责声明已更新，请重新阅读最新版本后确认')
    expect(await screen.findByText('新的第二条。')).toBeInTheDocument()
    expect(screen.getByText('版本 2026-12-01')).toBeInTheDocument()
    expect(screen.queryByText('旧的第一条。')).not.toBeInTheDocument()
    // 正文换了，要重新勾选
    expect(screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' })).not.toBeChecked()
    expect(confirmButton()).toBeDisabled()
    expect(router.state.location.pathname).toBe('/disclaimer')
  })

  it('has no back button', async () => {
    renderRoute('/disclaimer', { accepted: false })
    await screen.findByRole('list')
    expect(screen.queryByRole('button', { name: '返回' })).not.toBeInTheDocument()
  })

  it('keeps confirm disabled while the new text loads', async () => {
    const user = userEvent.setup()
    renderRoute('/disclaimer', { accepted: false })
    const held = gate()
    let heldStarted = false
    let outdated = false
    const accepts: unknown[] = []
    server.use(
      http.get('/api/disclaimer', async () => {
        if (outdated) {
          heldStarted = true
          await held.promise
        }
        return HttpResponse.json(disclaimerText({ version: outdated ? '2026-12-01' : DISCLAIMER_VERSION }))
      }),
      http.post('/api/disclaimer/accept', async ({ request }) => {
        accepts.push(await request.json())
        outdated = true
        return HttpResponse.json(
          { error: { code: 'disclaimer_outdated', message: '免责声明已更新，请重新阅读最新版本后确认' } }, { status: 409 },
        )
      }),
    )
    await screen.findByRole('list')
    const checkbox = () => screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' })
    await user.click(checkbox())
    await user.click(confirmButton())
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    // 新正文还没到：重新勾选也不能确认（否则会再交一次旧版本）
    await user.click(checkbox())
    expect(confirmButton()).toBeDisabled()
    // 先确认扣住的那次重新读取已经发出，再放行（否则放行时它还没开始，之后仍会一直等）
    await waitFor(() => expect(heldStarted).toBe(true))
    held.open()
    expect(await screen.findByText('版本 2026-12-01')).toBeInTheDocument()
    await waitFor(() => expect(confirmButton()).toBeEnabled())
    expect(accepts).toEqual([{ version: DISCLAIMER_VERSION }])
  })
})
