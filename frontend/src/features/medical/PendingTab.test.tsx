import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { formatMonthDay, todayISO } from '../../lib/dates'
import { evidence, order, ORDER_ID, pendingItem, SOURCE_TEXT } from '../../test/fixtures/medical'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const SECOND_ORDER = '00000000-0000-4000-8000-0000000000f2'

function renderPending(opts: MedicalOptions) {
  const result = renderRoute('/health/medical?tab=pending')
  const medical = medicalHandlers(opts)
  server.use(...medical.handlers)
  return { ...result, medical }
}

const itemOf = (content: string) => screen.getByText(content, { selector: '.fields dd' }).closest('.mo') as HTMLElement

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
}, 60_000)

describe('pending tab', { timeout: 15_000 }, () => {
  it('groups pending items under their order source', async () => {
    const first = pendingItem()
    const manual = pendingItem({
      id: '00000000-0000-4000-8000-0000000000c2', order_id: SECOND_ORDER, origin: 'manual', confidence: null,
      category: 'diet_avoid', content: '两周内忌食辛辣', subjects: ['辛辣'], source_excerpt: null, end_date: null, notes: [],
    })
    const confirmed = pendingItem({ id: '00000000-0000-4000-8000-0000000000c3', status: 'active', content: '已经生效的一条' })
    renderPending({
      items: [first, manual, confirmed],
      orders: [
        order({ id: SECOND_ORDER, evidence: [], ignored: [], created_at: '2026-10-12T02:00:00Z', source_text: '两周内忌食辛辣。' }),
        order(),
      ],
    })
    expect(await screen.findByText('提取出来的条目要逐条核对，确认前不参与任何建议。')).toBeInTheDocument()
    expect(await screen.findAllByRole('region')).toHaveLength(2)

    const withEvidence = screen.getByRole('region', { name: '出院小结.jpg' })
    expect(within(withEvidence).getByText(`${formatMonthDay('2026-10-11')} 录入，提取出 2 条`)).toBeInTheDocument()
    expect(within(withEvidence).getByText('服药期间及停药后 7 天内禁止饮酒', { selector: '.fields dd' })).toBeInTheDocument()
    expect(within(withEvidence).queryByText('已经生效的一条')).not.toBeInTheDocument()
    expect(within(withEvidence).getByRole('button', { name: '手动补充一条' })).toBeInTheDocument()

    const plain = screen.getByRole('region', { name: '原文' })
    expect(within(plain).getByText(`${formatMonthDay(todayISO(new Date('2026-10-12T02:00:00Z')))} 录入，提取出 0 条`)).toBeInTheDocument()
    expect(within(plain).getByText('两周内忌食辛辣', { selector: '.fields dd' })).toBeInTheDocument()

    // 原文、字段表与类别
    const item = itemOf('服药期间及停药后 7 天内禁止饮酒')
    expect(within(item).getByText('用药相关饮食注意')).toBeInTheDocument()
    expect(within(item).getByText('待核对')).toBeInTheDocument()
    expect(within(item).getByText(SOURCE_TEXT)).toHaveClass('orig')
    expect(within(item).getByText('酒精饮品、含酒精的菜（如醉虾、酒酿）')).toBeInTheDocument()
    expect(within(item).getByText('中')).toBeInTheDocument()
    expect(within(item).getByText('涉及用药，时间范围可能以用药或停药为起点，请务必对照原文核对')).toBeInTheDocument()
    // 未提取的句子折叠在来源下
    expect(within(withEvidence).getByRole('button', { name: /未提取的句子/ })).toHaveAttribute('aria-expanded', 'false')

    // 整块内容在敏感区里
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'medical', missing: [], unexpected: [] })
    expect(withEvidence.closest('[data-sensitive-area="content"]')).not.toBeNull()
  })

  it('warns about auto voiding after the end date', async () => {
    const dated = pendingItem()
    const open = pendingItem({ id: '00000000-0000-4000-8000-0000000000c2', content: '没有结束日期的一条', end_date: null })
    renderPending({ items: [dated, open], orders: [order()] })
    await screen.findByText('2026-10-25 之后仍未确认，会自动作废')
    expect(within(itemOf('服药期间及停药后 7 天内禁止饮酒')).getByText('2026-10-25 之后仍未确认，会自动作废')).toBeInTheDocument()
    expect(within(itemOf('没有结束日期的一条')).queryByText(/之后仍未确认/)).not.toBeInTheDocument()
  })

  it('spells out missing fields and their consequence', async () => {
    renderPending({
      items: [pendingItem({ end_date: null, review_date: null, subjects: [], missing_fields: ['end_date', 'subjects'] })],
      orders: [order()],
    })
    await screen.findByText('原文没有写明涉及的食物或行为，确认前需要补上')
    const item = itemOf('服药期间及停药后 7 天内禁止饮酒')
    expect(within(item).getByText('原文没有写明涉及的食物或行为，确认前需要补上')).toHaveClass('miss')
    expect(within(item).getByText('没有写明。确认后视为长期有效，可先补上')).toHaveClass('miss')
    expect(within(item).getByText('没有写明。确认后不设复查日期，可先补上')).toHaveClass('miss')
  })

  it('voids with an optional reason', async () => {
    const user = userEvent.setup()
    const first = pendingItem()
    const second = pendingItem({ id: '00000000-0000-4000-8000-0000000000c2', content: '第二条' })
    const { medical } = renderPending({ items: [first, second], orders: [order()] })
    await screen.findByText('第二条', { selector: '.fields dd' })

    await user.click(within(itemOf('服药期间及停药后 7 天内禁止饮酒')).getByRole('button', { name: '作废' }))
    let sheet = await screen.findByRole('dialog', { name: '作废这条医嘱' })
    expect(within(sheet).getByText('作废不能撤销。以后需要时，请重新录入。')).toBeInTheDocument()
    await user.type(within(sheet).getByLabelText('原因（可不填）'), '重复录入')
    await user.click(within(sheet).getByRole('button', { name: '作废' }))
    await waitFor(() => expect(medical.voids).toEqual([{ id: first.id, body: { reason: '重复录入' } }]))
    await waitFor(() => expect(screen.queryByText('服药期间及停药后 7 天内禁止饮酒', { selector: '.fields dd' })).not.toBeInTheDocument())

    await user.click(within(itemOf('第二条')).getByRole('button', { name: '作废' }))
    sheet = await screen.findByRole('dialog', { name: '作废这条医嘱' })
    await user.click(within(sheet).getByRole('button', { name: '作废' }))
    await waitFor(() => expect(medical.voids).toHaveLength(2))
    expect(medical.voids[1]).toEqual({ id: second.id, body: undefined })
  })

  it('edits only the changed fields', async () => {
    const user = userEvent.setup()
    const item = pendingItem()
    const { medical } = renderPending({ items: [item], orders: [order()] })
    await screen.findByText('服药期间及停药后 7 天内禁止饮酒', { selector: '.fields dd' })
    await user.click(within(itemOf('服药期间及停药后 7 天内禁止饮酒')).getByRole('button', { name: '修改' }))
    const sheet = await screen.findByRole('dialog', { name: '修改这条医嘱' })
    const content = within(sheet).getByLabelText('内容')
    // 表单里的医嘱内容在敏感区里（遮盖时一起盖住），按钮在外面
    expect(content.closest('[data-sensitive-area="content"]')).not.toBeNull()
    expect(within(sheet).getByRole('button', { name: '保存' }).closest('[data-sensitive]')).toBeNull()
    await user.clear(content)
    await user.type(content, '服药期间及停药后 7 天内禁酒')
    fireEvent.change(within(sheet).getByLabelText('复查日期'), { target: { value: '2026-10-18' } })
    await user.click(within(sheet).getByRole('button', { name: '清除预计结束' }))
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(medical.updates).toHaveLength(1))
    expect(medical.updates[0]).toEqual({
      id: item.id, body: { content: '服药期间及停药后 7 天内禁酒', end_date: null, review_date: '2026-10-18' },
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('服药期间及停药后 7 天内禁酒', { selector: '.fields dd' })).toBeInTheDocument()
  })

  it('adds a manual item to an order', async () => {
    const user = userEvent.setup()
    const { medical } = renderPending({ items: [pendingItem()], orders: [order()] })
    const group = await screen.findByRole('region', { name: '出院小结.jpg' })
    await user.click(within(group).getByRole('button', { name: '手动补充一条' }))
    const sheet = await screen.findByRole('dialog', { name: '手动补充一条' })
    // 生效日期默认是医嘱的开具日期
    expect(within(sheet).getByLabelText('生效日期')).toHaveValue('2026-10-11')
    await user.selectOptions(within(sheet).getByLabelText('类别'), 'diet_avoid')
    await user.type(within(sheet).getByLabelText('内容'), '一周内忌食辛辣')
    await user.click(within(sheet).getByRole('button', { name: '添加' }))
    await user.type(within(sheet).getByRole('textbox', { name: '添加涉及的食物或行为' }), '辛辣{Enter}')
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(medical.added).toHaveLength(1))
    expect(medical.added[0]).toEqual({
      orderId: ORDER_ID,
      body: { category: 'diet_avoid', content: '一周内忌食辛辣', subjects: ['辛辣'], start_date: '2026-10-11', end_date: null, review_date: null },
    })
    expect(await within(group).findByText('一周内忌食辛辣', { selector: '.fields dd' })).toBeInTheDocument()
  })

  it('opens the evidence viewer with the source text', async () => {
    const user = userEvent.setup()
    const { medical } = renderPending({ items: [pendingItem()], orders: [order({ evidence: [evidence()] })] })
    const group = await screen.findByRole('region', { name: '出院小结.jpg' })
    await user.click(within(group).getByRole('button', { name: '查看' }))
    const sheet = await screen.findByRole('dialog', { name: '原文与证据' })
    expect(within(sheet).getByText(`${SOURCE_TEXT}一周后门诊复查。`)).toBeInTheDocument()
    expect(within(sheet).getByText('出院小结.jpg')).toBeInTheDocument()
    await waitFor(() => expect(medical.evidenceRequests).toEqual([evidence().id]))
  })
})
