import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { assignment, fetchedModels, provider, timeoutReport, TIMEOUT_MESSAGE } from '../../test/fixtures/llm'
import { SAVED_AREA } from '../../test/fixtures/restaurants'
import { llmHandlers, type LlmOptions } from '../../test/msw/handlers/llm'
import { restaurantHandlers } from '../../test/msw/handlers/restaurants'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const deepseek = provider()
const qwen = provider({ id: '71000000-0000-4000-8000-000000000002', name: '通义千问', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', key_hint: '****a41f' })
const [, qwenPlus, qwenVl] = fetchedModels(qwen.id)

function renderModels(opts: LlmOptions = {}, area = false) {
  const llm = llmHandlers({
    providers: [deepseek, qwen],
    assignments: qwenPlus && qwenVl ? [assignment('chat', qwenPlus, '通义千问'), assignment('vision', qwenVl, '通义千问')] : [],
    ...opts,
  })
  server.use(...llm.handlers, ...restaurantHandlers({ settings: { location_consent: 'denied', area: area ? SAVED_AREA : null } }).handlers)
  return { ...renderRoute('/settings/models'), llm }
}

const row = (name: string) => {
  const list = screen.getByRole('list', { name: '模型服务' })
  const item = within(list).getAllByRole('listitem').find((li) => li.querySelector('b')?.textContent === name)
  if (!item) throw new Error(`没有 ${name}`)
  return item
}

beforeAll(async () => {
  await import('./ModelsPage')
}, 60_000)

describe('models page', { timeout: 15_000 }, () => {
  it('lists providers with only the key mask', async () => {
    renderModels()
    await screen.findByRole('list', { name: '模型服务' })
    const item = row('DeepSeek')
    expect(within(item).getByText('https://api.deepseek.com/v1')).toBeInTheDocument()
    expect(within(item).getByLabelText('密钥 ****7c2e')).toBeInTheDocument()
    expect(within(row('通义千问')).getByText('https://dashscope.aliyuncs.com/compatible-mode/v1')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '添加模型服务' })).toHaveAttribute('href', '/settings/models/new')
  })

  it('tests a provider and shows the verdict with the backend message', async () => {
    const user = userEvent.setup()
    const { llm } = renderModels({ testReports: [timeoutReport()] })
    await screen.findByRole('list', { name: '模型服务' })
    await user.click(within(row('通义千问')).getByRole('button', { name: '测试连通' }))
    expect(await within(row('通义千问')).findByText(TIMEOUT_MESSAGE)).toBeInTheDocument()
    expect(within(row('通义千问')).getByText('未连通')).toBeInTheDocument()
    expect(within(row('通义千问')).getByText('错误码 llm_timeout')).toBeInTheDocument()
    expect(llm.record.tests).toEqual([{ id: qwen.id, body: { model_id: 'qwen-plus' } }])

    await user.click(within(row('DeepSeek')).getByRole('button', { name: '测试连通' }))
    expect(await within(row('DeepSeek')).findByText('已连通')).toBeInTheDocument()
    await waitFor(() => expect(llm.record.tests[1]).toEqual({ id: deepseek.id, body: {} }))
  })

  it('deletes a provider after confirming', async () => {
    const user = userEvent.setup()
    const { llm } = renderModels()
    await screen.findByRole('list', { name: '模型服务' })
    expect(screen.getByRole('list', { name: '当前用途' })).toHaveTextContent('日常对话qwen-plus（通义千问）')
    await user.click(within(row('通义千问')).getByRole('button', { name: '删除' }))
    const dialog = await screen.findByRole('dialog', { name: '删除这个模型服务' })
    expect(within(dialog).getByText('通义千问')).toBeInTheDocument()
    expect(within(dialog).getByText('模型与用途分配', { exact: false })).toBeInTheDocument()
    expect(within(dialog).getByText('密钥', { exact: false })).toBeInTheDocument()
    expect(llm.record.deletes).toEqual([])
    await user.click(within(dialog).getByRole('button', { name: '删除' }))

    await waitFor(() => expect(llm.record.deletes).toEqual([qwen.id]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(within(screen.getByRole('list', { name: '模型服务' })).getAllByRole('listitem')).toHaveLength(1))
    expect(row('DeepSeek')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('list', { name: '当前用途' })).toHaveTextContent('日常对话未设置'))
    expect(await screen.findByText('已删除')).toBeInTheDocument()
  })

  it('shows the current assignments', async () => {
    renderModels()
    const uses = await screen.findByRole('list', { name: '当前用途' })
    expect(uses).toHaveTextContent('日常对话qwen-plus（通义千问）')
    expect(uses).toHaveTextContent('看图识别qwen-vl-max（通义千问）')
  })

  it('shows unassigned purposes', async () => {
    renderModels({ assignments: [] })
    const uses = await screen.findByRole('list', { name: '当前用途' })
    expect(uses).toHaveTextContent('日常对话未设置')
  })

  it('links to the other settings with the saved area', async () => {
    renderModels({}, true)
    const link = await screen.findByRole('link', { name: /已保存的大致区域/ })
    expect(link).toHaveAttribute('href', '/settings/privacy')
    expect(await within(link).findByText(SAVED_AREA.name)).toBeInTheDocument()
    expect(within(link).getByText(SAVED_AREA.name).closest('[data-sensitive]')).not.toBeNull()
    expect(screen.getByRole('link', { name: '隐私与数据' })).toHaveAttribute('href', '/settings/privacy')
    expect(screen.getByRole('link', { name: '免责声明' })).toHaveAttribute('href', '/settings/disclaimer')
  })
})
