import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { order, pendingItem } from '../../test/fixtures/medical'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { gate } from '../../test/chat'
import { renderRoute } from '../../test/render'

function renderPending(opts: MedicalOptions = { items: [pendingItem()], orders: [order()] }) {
  const result = renderRoute('/health/medical?tab=pending')
  const medical = medicalHandlers(opts)
  server.use(...medical.handlers)
  return { ...result, medical }
}

const openConfirm = async (user: ReturnType<typeof userEvent.setup>) => {
  const item = (await screen.findByText('服药期间及停药后 7 天内禁止饮酒', { selector: '.fields dd' })).closest('.mo') as HTMLElement
  await user.click(within(item).getByRole('button', { name: '确认生效' }))
  return screen.findByRole('dialog', { name: '确认这条医嘱生效' })
}

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
}, 60_000)

describe('confirm effect sheet', { timeout: 15_000 }, () => {
  it('lists what will happen before confirming', async () => {
    const user = userEvent.setup()
    renderPending()
    const sheet = await openConfirm(user)
    const quote = sheet.querySelector('.quote') as HTMLElement
    expect(within(quote).getByText('用药相关饮食注意')).toBeInTheDocument()
    expect(within(quote).getByText('服药期间及停药后 7 天内禁止饮酒')).toBeInTheDocument()
    expect(within(quote).getByText('来源：出院小结.jpg，提取把握 中')).toBeInTheDocument()
    expect(quote.querySelector('[data-sensitive-area="content"]')).not.toBeNull()
    expect(within(sheet).getByText('确认后会发生：')).toBeInTheDocument()
    expect(Array.from(sheet.querySelectorAll('.will li')).map((li) => li.textContent)).toEqual([
      '状态从“待核对”变为“生效中”。',
      '之后的对话、拍照评价和附近餐厅推荐都按它约束。',
      '预计结束 2026-10-25。结束前一天起进入待复核，那天打开应用时会提醒你。',
      '记一条审计：时间、由你本人确认、来源与修改过的字段。',
    ])
    expect(within(sheet).getByText('医嘱只能在这里确认或解除，对话里无法完成。')).toBeInTheDocument()
    // 确认生效之后仍可修改或解除，所以不加勾选
    expect(within(sheet).queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('says a confirmed item without an end date stays in effect', async () => {
    const user = userEvent.setup()
    renderPending({ items: [pendingItem({ end_date: null, origin: 'manual', confidence: null })], orders: [order({ evidence: [] })] })
    const sheet = await openConfirm(user)
    expect(within(sheet).getByText('没有预计结束日期，视为长期有效。')).toBeInTheDocument()
    expect(within(sheet).getByText('来源：原文')).toBeInTheDocument()
  })

  it('confirms only through the explicit button', async () => {
    const user = userEvent.setup()
    const item = pendingItem()
    const { medical } = renderPending()
    const sheet = await openConfirm(user)
    // 打开面板不发任何请求
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(medical.confirms).toEqual([])
    await user.click(within(sheet).getByRole('button', { name: '确认生效' }))
    await waitFor(() => expect(medical.confirms).toEqual([{ id: item.id, body: '' }]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.queryByText('服药期间及停药后 7 天内禁止饮酒', { selector: '.fields dd' })).not.toBeInTheDocument()
    expect(await screen.findByText('已确认生效，可在“生效中”查看')).toBeInTheDocument()
    expect(medical.confirms).toHaveLength(1)
  })

  it('confirms once on a double press', async () => {
    const user = userEvent.setup({ delay: null })
    const { medical } = renderPending()
    const sheet = await openConfirm(user)
    await user.dblClick(within(sheet).getByRole('button', { name: '确认生效' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.confirms).toHaveLength(1)
  })

  it('blocks returning to editing and closing while confirming', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { medical } = renderPending({ items: [pendingItem()], orders: [order()], hold: { confirm: held.promise } })
    const sheet = await openConfirm(user)
    await user.click(within(sheet).getByRole('button', { name: '确认生效' }))
    await waitFor(() => expect(medical.confirms).toHaveLength(1))
    const back = within(sheet).getByRole('button', { name: '返回修改' })
    expect(back).toBeDisabled()
    await user.click(back)
    await user.click(within(sheet).getByRole('button', { name: '确认生效' }))
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '确认这条医嘱生效' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: '修改这条医嘱' })).not.toBeInTheDocument()
    held.open()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.confirms).toHaveLength(1)
  })

  it('returns to editing', async () => {
    const user = userEvent.setup()
    const { medical } = renderPending()
    const sheet = await openConfirm(user)
    await user.click(within(sheet).getByRole('button', { name: '返回修改' }))
    expect(await screen.findByRole('dialog', { name: '修改这条医嘱' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: '确认这条医嘱生效' })).not.toBeInTheDocument()
    expect(medical.confirms).toEqual([])
  })

  it('shows backend errors verbatim', async () => {
    const user = userEvent.setup()
    const message = '请至少填写一个涉及的食物或行为，再确认这条医嘱'
    renderPending({
      items: [pendingItem({ subjects: [] })], orders: [order()],
      errors: { confirm: { status: 422, code: 'subjects_required', message } },
    })
    const sheet = await openConfirm(user)
    await user.click(within(sheet).getByRole('button', { name: '确认生效' }))
    const alert = await within(sheet).findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent('错误码 subjects_required')
    expect(screen.getByRole('dialog', { name: '确认这条医嘱生效' })).toBeInTheDocument()
    expect(within(sheet).getByRole('button', { name: '确认生效' })).toBeEnabled()
  })
})
