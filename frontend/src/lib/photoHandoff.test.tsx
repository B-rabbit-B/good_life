import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { api } from '../api/client'
import { server } from '../test/msw/server'
import { renderRoute } from '../test/render'
import { clearPendingPhoto, setPendingPhoto, takePendingPhoto } from './photoHandoff'

const photo = () => new File(['jpeg'], 'dinner.jpg', { type: 'image/jpeg' })

describe('photo handoff', () => {
  it('hands a photo over once', () => {
    const file = photo()
    setPendingPhoto(file)
    expect(takePendingPhoto()).toBe(file)
    expect(takePendingPhoto()).toBeNull()
    setPendingPhoto(file)
    clearPendingPhoto()
    expect(takePendingPhoto()).toBeNull()
  })

  it('drops a pending photo on logout', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/me')
    setPendingPhoto(photo())
    await user.click(await screen.findByRole('button', { name: '退出登录' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(takePendingPhoto()).toBeNull()
  })

  it('drops a pending photo when the session expires', async () => {
    const { router } = renderRoute('/me')
    expect(await screen.findByRole('heading', { name: '我的', level: 1 })).toBeInTheDocument()
    setPendingPhoto(photo())
    server.use(http.get('/api/auth/me', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    await act(async () => {
      await api('/api/auth/me').catch(() => undefined)
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(takePendingPhoto()).toBeNull()
  })
})
