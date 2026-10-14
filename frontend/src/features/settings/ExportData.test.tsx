import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, onTestFinished, vi } from 'vitest'
import { TEST_PASSWORD } from '../../test/fixtures/profile'
import { accountHandlers, EXPORT_FILENAME, PASSWORD_INCORRECT_MESSAGE } from '../../test/msw/handlers/account'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderExport() {
  const account = accountHandlers()
  server.use(...account.handlers)
  return { ...renderRoute('/settings/privacy'), account }
}

/** 换掉对象地址与链接点击（jsdom 没有对象地址，也不真的下载），记下每次点击时链接的地址与文件名 */
function captureDownloads() {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:export-zip')
  const revokeObjectURL = vi.fn()
  class TestURL extends URL {
    static override createObjectURL = createObjectURL
    static override revokeObjectURL = revokeObjectURL
  }
  vi.stubGlobal('URL', TestURL)
  const clicks: { href: string; download: string }[] = []
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    clicks.push({ href: this.getAttribute('href') ?? '', download: this.download })
  })
  onTestFinished(() => {
    click.mockRestore()
    vi.unstubAllGlobals()
  })
  return { createObjectURL, revokeObjectURL, clicks }
}

async function openSheet(user: ReturnType<typeof userEvent.setup>) {
  const section = (await screen.findByRole('heading', { name: '导出我的数据' })).closest('section') as HTMLElement
  await user.click(within(section).getByRole('button', { name: '导出我的数据' }))
  return screen.findByRole('dialog', { name: '导出我的数据' })
}

beforeAll(async () => {
  await import('./PrivacyPage')
}, 60_000)

describe('export data', { timeout: 15_000 }, () => {
  it('lists every kind of data the archive holds, matching the thirteen files the backend exports', async () => {
    const user = userEvent.setup()
    renderExport()
    const dialog = await openSheet(user)
    for (const kind of ['账号', '偏好与开场记录', '餐厅设置', '免责与同意记录']) {
      expect(within(dialog).getByText(kind, { exact: false }), kind).toBeInTheDocument()
    }
  })

  it('asks for the password before exporting', async () => {
    const user = userEvent.setup()
    const { account } = renderExport()
    const dialog = await openSheet(user)
    expect(within(dialog).getByText('密钥只含掩码', { exact: false })).toBeInTheDocument()
    const confirm = within(dialog).getByRole('button', { name: '导出并下载' })
    expect(confirm).toBeDisabled()
    const field = within(dialog).getByLabelText('登录密码')
    expect(field).toHaveAttribute('type', 'password')
    expect(field).toHaveAttribute('autocomplete', 'current-password')
    await user.type(field, 'x')
    expect(confirm).toBeEnabled()
    await user.clear(field)
    expect(confirm).toBeDisabled()
    expect(account.record.exports).toEqual([])
  })

  it('starts the download and clears the password', async () => {
    const user = userEvent.setup()
    const downloads = captureDownloads()
    const { account } = renderExport()
    let dialog = await openSheet(user)
    await user.type(within(dialog).getByLabelText('登录密码'), TEST_PASSWORD)
    await user.click(within(dialog).getByRole('button', { name: '导出并下载' }))

    await waitFor(() => expect(downloads.clicks).toEqual([{ href: 'blob:export-zip', download: EXPORT_FILENAME }]))
    expect(account.record.exports).toHaveLength(1)
    expect(account.record.exports[0]?.body).toEqual({ password: TEST_PASSWORD })
    expect(account.record.exports[0]?.url).not.toContain(TEST_PASSWORD)
    expect(downloads.createObjectURL.mock.calls[0]?.[0].size).toBe(6)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('已开始下载')).toBeInTheDocument()
    await waitFor(() => expect(downloads.revokeObjectURL).toHaveBeenCalledWith('blob:export-zip'), { timeout: 3000 })
    expect(document.querySelector('a[download]')).toBeNull()
    expect(JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage })).not.toContain(TEST_PASSWORD)

    dialog = await openSheet(user)
    expect(within(dialog).getByLabelText('登录密码')).toHaveValue('')
  })

  it('shows password_incorrect under the field', async () => {
    const user = userEvent.setup()
    const downloads = captureDownloads()
    const { account } = renderExport()
    const dialog = await openSheet(user)
    const field = within(dialog).getByLabelText('登录密码')
    await user.type(field, 'not-my-password')
    await user.click(within(dialog).getByRole('button', { name: '导出并下载' }))
    await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'))
    expect(field).toHaveAccessibleDescription(new RegExp(`${PASSWORD_INCORRECT_MESSAGE}错误码 password_incorrect`))
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
    expect(downloads.clicks).toEqual([])
    expect(account.record.exports).toHaveLength(1)
    expect(within(dialog).getByRole('button', { name: '导出并下载' })).toBeEnabled()
  })
})
