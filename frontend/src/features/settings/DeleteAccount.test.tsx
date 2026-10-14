import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { qk } from '../../api/keys'
import { getToken } from '../../api/token'
import { peekPendingPhoto, setPendingPhoto } from '../../lib/photoHandoff'
import { TEST_PASSWORD } from '../../test/fixtures/profile'
import { accountHandlers, PASSWORD_INCORRECT_MESSAGE } from '../../test/msw/handlers/account'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const ACK = '我知道删除后所有数据立即清除、不能恢复'

function renderDelete(hold?: Promise<void>) {
  const account = accountHandlers({ hold: { delete: hold } })
  server.use(...account.handlers)
  return { ...renderRoute('/settings/privacy'), account }
}

async function openSheet(user: ReturnType<typeof userEvent.setup>) {
  const section = (await screen.findByRole('heading', { name: '删除账号与全部数据' })).closest('section') as HTMLElement
  await user.click(within(section).getByRole('button', { name: '删除账号' }))
  return screen.findByRole('dialog', { name: '删除账号与全部数据' })
}

beforeAll(async () => {
  await import('./PrivacyPage')
  await import('../auth/LoginPage')
}, 60_000)

describe('delete account', { timeout: 15_000 }, () => {
  it('keeps delete disabled until the password and the acknowledgement are given', async () => {
    const user = userEvent.setup()
    const { account } = renderDelete()
    const dialog = await openSheet(user)
    const confirm = within(dialog).getByRole('button', { name: '删除账号' })
    const ack = within(dialog).getByRole('checkbox', { name: ACK })
    expect(confirm).toBeDisabled()
    await user.click(ack)
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText('登录密码'), TEST_PASSWORD)
    expect(confirm).toBeEnabled()
    await user.click(ack)
    expect(confirm).toBeDisabled()
    await user.click(ack)
    await user.clear(within(dialog).getByLabelText('登录密码'))
    expect(confirm).toBeDisabled()
    expect(account.record.deletes).toEqual([])
  })

  it('locks the sheet while the request is running', async () => {
    const user = userEvent.setup()
    let release = () => {}
    const { account } = renderDelete(new Promise<void>((resolve) => {
      release = resolve
    }))
    const dialog = await openSheet(user)
    const field = within(dialog).getByLabelText('登录密码')
    await user.type(field, 'not-my-password')
    await user.click(within(dialog).getByRole('checkbox', { name: ACK }))
    await user.click(within(dialog).getByRole('button', { name: '删除账号' }))
    await waitFor(() => expect(account.record.deletes).toHaveLength(1))
    expect(account.record.deletes[0]?.body).toEqual({ password: 'not-my-password', confirm: true })

    // 进行中的确认按钮是 aria-disabled（焦点留在按钮上），取消按钮停用
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '删除账号' })).toHaveAttribute('aria-disabled', 'true'))
    expect(within(dialog).getByRole('button', { name: '取消' })).toBeDisabled()
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '删除账号与全部数据' })).toBeInTheDocument()

    release()
    await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'))
    expect(field).toHaveAccessibleDescription(new RegExp(`${PASSWORD_INCORRECT_MESSAGE}错误码 password_incorrect`))
    expect(within(dialog).getByRole('button', { name: '取消' })).toBeEnabled()
    expect(getToken()).not.toBeNull()
  })

  it('clears the token and cache and returns to login with a notice', async () => {
    const user = userEvent.setup()
    const { account, router, queryClient } = renderDelete()
    setPendingPhoto(new File(['x'], 'meal.jpg', { type: 'image/jpeg' }))
    const dialog = await openSheet(user)
    expect(queryClient.getQueryData(qk.profile)).toBeDefined()
    await user.type(within(dialog).getByLabelText('登录密码'), TEST_PASSWORD)
    await user.click(within(dialog).getByRole('checkbox', { name: ACK }))
    await user.click(within(dialog).getByRole('button', { name: '删除账号' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(await screen.findByText('账号与全部数据已删除')).toHaveAttribute('role', 'status')
    expect(account.record.deletes.map((d) => d.body)).toEqual([{ password: TEST_PASSWORD, confirm: true }])
    expect(account.record.deletes[0]?.url).not.toContain(TEST_PASSWORD)
    expect(getToken()).toBeNull()
    expect(peekPendingPhoto()).toBeNull()
    await waitFor(() => expect(queryClient.getQueryData(qk.profile)).toBeUndefined())
    expect(queryClient.getQueryData(qk.capabilities)).toBeUndefined()
    expect(queryClient.getMutationCache().getAll()).toEqual([])
    expect(screen.queryByRole('heading', { name: '登录已过期' })).not.toBeInTheDocument()
  })
})
