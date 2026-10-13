import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { todayISO } from '../../lib/dates'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const TEXT = '头孢呋辛酯片 0.25g，每日两次，连服 7 天。服药期间及停药后 7 天内禁止饮酒。一周后门诊复查。'

function renderNew(opts: MedicalOptions = {}) {
  const result = renderRoute('/health/medical/new')
  const medical = medicalHandlers({
    extract: () => [{ category: 'medication_diet', content: '服药期间及停药后 7 天内禁止饮酒', subjects: ['饮酒'] }],
    ...opts,
  })
  server.use(...medical.handlers)
  return { ...result, medical }
}

// 文件内容就是文件名：测试环境的 fetch 不带文件名，模拟接口按内容认出是哪个文件（见 msw/handlers/medical.ts）
const jpg = (name: string) => new File([name], name, { type: 'image/jpeg' })
const pdf = (name: string) => new File([name], name, { type: 'application/pdf' })

async function fill(user: ReturnType<typeof userEvent.setup>, files: File[]) {
  const text = await screen.findByLabelText('医嘱原文')
  fireEvent.change(text, { target: { value: TEXT } })
  const album = document.querySelector('input[type="file"]:not([capture])') as HTMLInputElement
  await user.upload(album, files)
}

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('./MedicalNewPage')
}, 60_000)

describe('medical new page', { timeout: 15_000 }, () => {
  it('creates the order then uploads each evidence file', async () => {
    const user = userEvent.setup()
    const { medical } = renderNew()
    await fill(user, [jpg('出院小结.jpg'), pdf('复诊单.pdf')])
    const list = screen.getByRole('list', { name: '证据' })
    expect(within(list).getByText('出院小结.jpg')).toBeInTheDocument()
    expect(within(list).getByText('复诊单.pdf')).toBeInTheDocument()
    expect(within(list).getAllByText(/，加密保存$/)).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: '提取条目' }))
    await waitFor(() => expect(medical.uploads).toHaveLength(2))
    expect(medical.createdOrders).toEqual([{ text: TEXT, order_date: todayISO() }])
    const orderId = medical.items()[0]?.order_id
    expect(medical.uploads.map((upload) => [upload.orderId, upload.name])).toEqual([[orderId, '出院小结.jpg'], [orderId, '复诊单.pdf']])
  })

  it('removes a picked file before submitting', async () => {
    const user = userEvent.setup()
    const { medical } = renderNew()
    await fill(user, [jpg('出院小结.jpg'), pdf('复诊单.pdf')])
    await user.click(screen.getByRole('button', { name: '移除复诊单.pdf' }))
    expect(screen.queryByText('复诊单.pdf')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '提取条目' }))
    await waitFor(() => expect(medical.uploads.map((upload) => upload.name)).toEqual(['出院小结.jpg']))
  })

  it('goes to the pending tab after extraction', async () => {
    const user = userEvent.setup()
    const { router } = renderNew()
    await fill(user, [])
    await user.click(screen.getByRole('button', { name: '提取条目' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/health/medical'))
    expect(router.state.location.search).toBe('?tab=pending')
    expect(await screen.findByText('服药期间及停药后 7 天内禁止饮酒', { selector: '.fields dd' })).toBeInTheDocument()
  })

  it('does not resubmit the order when an upload fails', async () => {
    const user = userEvent.setup()
    const message = '文件不能超过 10 MB'
    const { medical, router } = renderNew({
      uploadErrors: { '复诊单.pdf': { status: 413, code: 'evidence_too_large', message } },
    })
    await fill(user, [jpg('出院小结.jpg'), pdf('复诊单.pdf'), jpg('化验单.jpg')])
    await user.click(screen.getByRole('button', { name: '提取条目' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(`复诊单.pdf：${message}`)
    expect(alert).toHaveTextContent('错误码 evidence_too_large')
    expect(router.state.location.pathname).toBe('/health/medical/new')
    expect(medical.uploads.map((upload) => upload.name)).toEqual(['出院小结.jpg', '复诊单.pdf'])

    await user.click(screen.getByRole('button', { name: '重试上传证据' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/health/medical'))
    expect(medical.createdOrders).toHaveLength(1)
    expect(medical.uploads.map((upload) => upload.name)).toEqual(['出院小结.jpg', '复诊单.pdf', '复诊单.pdf', '化验单.jpg'])
  })

  it('shows an order error verbatim and keeps the text', async () => {
    const user = userEvent.setup()
    const message = '医嘱日期不能晚于今天'
    const { medical } = renderNew({ errors: { createOrder: { status: 422, code: 'order_in_future', message } } })
    await fill(user, [jpg('出院小结.jpg')])
    await user.click(screen.getByRole('button', { name: '提取条目' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByLabelText('医嘱原文')).toHaveValue(TEXT)
    expect(medical.uploads).toEqual([])
    await user.click(screen.getByRole('button', { name: '提取条目' }))
    await waitFor(() => expect(medical.createdOrders).toHaveLength(2))
  })

  it('counts characters up to 5000', async () => {
    const user = userEvent.setup()
    renderNew()
    const text = await screen.findByLabelText('医嘱原文')
    expect(screen.getByText('0 / 5000')).toBeInTheDocument()
    expect(text).toHaveAttribute('maxlength', '5000')
    await user.type(text, '每日饮水')
    expect(screen.getByText('4 / 5000')).toBeInTheDocument()
    fireEvent.change(text, { target: { value: TEXT } })
    expect(screen.getByText(`${TEXT.length} / 5000`)).toBeInTheDocument()
    expect(screen.getByLabelText('开具日期')).toHaveValue(todayISO())
    expect(screen.getByLabelText('开具日期')).toHaveAttribute('max', todayISO())
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'medicalNew', missing: [], unexpected: [] })
  })
})
