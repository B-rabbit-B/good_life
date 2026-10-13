import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import {
  ASSIGN_WARNING, BAD_KEY, BAD_URL_MESSAGE, GOOD_KEY, INVALID_KEY_MESSAGE, LACKS_VISION_MESSAGE, LISTING_MESSAGE, NEW_KEY,
  okReport, TIMEOUT_MESSAGE, timeoutReport,
} from '../../test/fixtures/llm'
import { gate } from '../../test/chat'
import { llmHandlers, type LlmOptions } from '../../test/msw/handlers/llm'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const URL_V1 = 'https://llm.example.com/v1'
type User = ReturnType<typeof userEvent.setup>

function renderFlow(opts: LlmOptions = {}) {
  const llm = llmHandlers(opts)
  server.use(...llm.handlers)
  return { ...renderRoute('/settings/models/new'), llm }
}

const step = (n: number) => {
  const el = document.querySelector<HTMLElement>(`[data-step="${n}"]`)
  if (!el) throw new Error(`没有第 ${n} 步`)
  return el
}

async function fillStepOne(user: User, key: string, name = '测试服务') {
  await user.type(await screen.findByLabelText('名称'), name)
  await user.type(screen.getByLabelText('服务地址'), URL_V1)
  await user.type(screen.getByLabelText('密钥'), key)
  await user.click(screen.getByRole('button', { name: '保存并获取模型' }))
}

async function toStepFour(user: User) {
  await fillStepOne(user, GOOD_KEY)
  await user.click(await within(step(3)).findByRole('button', { name: '测试连通' }))
  return within(step(4)).findByRole('button', { name: '保存用途' })
}

beforeAll(async () => {
  await import('./ModelNewPage')
}, 60_000)

describe('provider flow', { timeout: 15_000 }, () => {
  it('fills the type, name and address from a preset', async () => {
    const user = userEvent.setup()
    renderFlow()
    const type = await screen.findByLabelText('类型')
    await waitFor(() => expect(within(type).getAllByRole('option').length).toBeGreaterThan(3))
    await user.selectOptions(type, '通义千问（OpenAI 兼容格式）')
    expect(screen.getByLabelText('名称')).toHaveValue('通义千问')
    expect(screen.getByLabelText('服务地址')).toHaveValue('https://dashscope.aliyuncs.com/compatible-mode/v1')
    await user.selectOptions(type, '自定义（Anthropic）')
    expect(type).toHaveValue('kind:anthropic')
  })

  it('creates the provider and fetches models', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow()
    await fillStepOne(user, GOOD_KEY)
    expect(await within(step(2)).findByText('4 个')).toBeInTheDocument()
    expect(within(step(2)).getByText('其中 1 个能看图，2 个能调用工具。')).toBeInTheDocument()
    expect(llm.record.creates).toEqual([{ name: '测试服务', kind: 'openai_compatible', base_url: URL_V1, api_key: GOOD_KEY }])
    expect(llm.record.fetches).toHaveLength(1)
    expect(within(step(1)).getByText('已保存')).toBeInTheDocument()
    expect(within(step(1)).getByText(URL_V1)).toBeInTheDocument()
    expect(within(step(1)).getByLabelText('密钥 ****0001')).toBeInTheDocument()
  })

  it('clears the key input and shows only the backend mask after saving', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderFlow()
    expect(await screen.findByLabelText('密钥')).toHaveAttribute('autocomplete', 'new-password')
    await fillStepOne(user, GOOD_KEY)
    await within(step(2)).findByText('4 个')
    expect(screen.queryByLabelText('密钥')).not.toBeInTheDocument()
    const values = Array.from(document.querySelectorAll('input, select, textarea')).map((el) => (el as HTMLInputElement).value)
    expect(values).not.toContain(GOOD_KEY)
    expect(document.body.textContent).not.toContain(GOOD_KEY)
    expect(document.body.textContent).toContain('****0001')
    expect(JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage })).not.toContain(GOOD_KEY)
    await waitFor(() => {
      const mutations = queryClient.getMutationCache().getAll().map((m) => [m.options.mutationKey, m.state])
      expect(JSON.stringify(mutations)).not.toContain(GOOD_KEY)
    })
    expect(JSON.stringify(queryClient.getQueryCache().getAll().map((q) => [q.queryKey, q.state]))).not.toContain(GOOD_KEY)
  })

  it('marks the key field on llm_invalid_key and resaves with a patch', async () => {
    const user = userEvent.setup()
    const { llm, queryClient } = renderFlow()
    await fillStepOne(user, BAD_KEY)
    const key = await within(step(1)).findByLabelText('密钥')
    expect(key).toHaveAttribute('aria-invalid', 'true')
    expect(key.closest('.fld-i')).toHaveClass('bad')
    expect(key).toHaveValue('')
    expect(within(step(1)).getByText('密钥无效')).toBeInTheDocument()
    expect(within(step(1)).getByText(INVALID_KEY_MESSAGE)).toBeInTheDocument()
    expect(within(step(1)).getByText('错误码 llm_invalid_key')).toBeInTheDocument()
    expect(screen.getByLabelText('类型')).toBeDisabled()
    await user.type(key, NEW_KEY)
    await user.click(within(step(1)).getByRole('button', { name: '重新保存并获取模型' }))
    expect(await within(step(2)).findByText('4 个')).toBeInTheDocument()
    expect(llm.record.creates).toHaveLength(1)
    expect(llm.record.updates).toEqual([{ id: expect.any(String) as string, body: { api_key: NEW_KEY } }])
    expect(within(step(1)).getByLabelText('密钥 ****4242')).toBeInTheDocument()
    await waitFor(() => expect(JSON.stringify(queryClient.getMutationCache().getAll().map((m) => m.state))).not.toContain(NEW_KEY))
  })

  it('sends the user back to the address on llm_bad_url', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow({ fetchErrors: [{ status: 400, code: 'llm_bad_url', message: BAD_URL_MESSAGE }] })
    await fillStepOne(user, GOOD_KEY)
    expect(await within(step(2)).findByText('地址有误')).toBeInTheDocument()
    expect(within(step(2)).getByText(BAD_URL_MESSAGE)).toBeInTheDocument()
    expect(within(step(2)).getByText('错误码 llm_bad_url')).toBeInTheDocument()
    await user.click(within(step(2)).getByRole('button', { name: '修改地址' }))
    const url = within(step(1)).getByLabelText('服务地址')
    expect(url).toHaveAttribute('aria-invalid', 'true')
    expect(url).toHaveFocus()
    expect(within(step(1)).getByText(BAD_URL_MESSAGE)).toBeInTheDocument()
    await user.clear(url)
    await user.type(url, 'https://llm.example.com/v2')
    await user.click(within(step(1)).getByRole('button', { name: '重新保存并获取模型' }))
    expect(await within(step(2)).findByText('4 个')).toBeInTheDocument()
    expect(llm.record.updates.map((u) => u.body)).toEqual([{ base_url: 'https://llm.example.com/v2' }])
  })

  it('offers adding a model id when the service cannot list models', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow({ fetchErrors: [{ status: 400, code: 'llm_listing_unsupported_or_bad_url', message: LISTING_MESSAGE }] })
    await fillStepOne(user, GOOD_KEY)
    expect(await within(step(2)).findByText(LISTING_MESSAGE)).toBeInTheDocument()
    await user.type(within(step(2)).getByLabelText('模型编号'), 'my-model')
    await user.click(within(step(2)).getByRole('button', { name: '添加' }))
    expect(await within(step(3)).findByRole('button', { name: '测试连通' })).toBeInTheDocument()
    expect(llm.record.manual).toEqual([{ model_id: 'my-model' }])
    expect(within(step(3)).getByLabelText('测试用的模型')).toHaveValue('my-model')
  })

  it('offers adding a model id when the fetch finds no models', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow({ fetched: () => [] })
    await fillStepOne(user, GOOD_KEY)
    expect(await within(step(2)).findByText('其中 0 个能看图，0 个能调用工具。')).toBeInTheDocument()
    await user.type(within(step(2)).getByLabelText('模型编号'), 'my-model')
    await user.click(within(step(2)).getByRole('button', { name: '添加' }))
    await waitFor(() => expect(within(step(3)).getByLabelText('测试用的模型')).toHaveValue('my-model'))
    expect(llm.record.manual).toEqual([{ model_id: 'my-model' }])
    expect(within(step(2)).queryByLabelText('模型编号')).not.toBeInTheDocument()
  })

  it('shows the report message in step three when the listing is unsupported', async () => {
    const user = userEvent.setup()
    const message = '模型 qwen-plus 对话成功，但该服务不支持拉取模型列表，请手动添加模型编号。'
    renderFlow({ testReports: [{
      ...okReport('qwen-plus'), conclusion: 'ok_listing_unsupported', message,
      listing: { ok: false, code: 'llm_listing_unsupported_or_bad_url', message: LISTING_MESSAGE },
    }] })
    await fillStepOne(user, GOOD_KEY)
    await user.click(await within(step(3)).findByRole('button', { name: '测试连通' }))
    expect(await within(step(3)).findByText(message)).toBeInTheDocument()
    expect(within(step(3)).queryByText('模型 qwen-plus 对话成功')).not.toBeInTheDocument()
  })

  it('tests a model and shows the backend message', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow()
    await fillStepOne(user, GOOD_KEY)
    const model = await within(step(3)).findByLabelText('测试用的模型')
    expect(model).toHaveValue('qwen-plus')
    await user.click(within(step(3)).getByRole('button', { name: '测试连通' }))
    expect(await within(step(3)).findByText('模型 qwen-plus 对话成功')).toBeInTheDocument()
    expect(within(step(3)).getByText(/^用时(不到 0\.1| \d+(\.\d)?) 秒$/)).toBeInTheDocument()
    expect(llm.record.tests.map((t) => t.body)).toEqual([{ model_id: 'qwen-plus' }])
  })

  it('shows a timeout in step three with a retest action', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow({ testReports: [timeoutReport()] })
    await fillStepOne(user, GOOD_KEY)
    await user.click(await within(step(3)).findByRole('button', { name: '测试连通' }))
    expect(await within(step(3)).findByText('超时')).toBeInTheDocument()
    expect(within(step(3)).getByText(TIMEOUT_MESSAGE)).toBeInTheDocument()
    expect(within(step(3)).getByText('错误码 llm_timeout')).toBeInTheDocument()
    await user.click(within(step(3)).getByRole('button', { name: '重新测试' }))
    expect(await within(step(4)).findByRole('button', { name: '保存用途' })).toBeInTheDocument()
    expect(llm.record.tests).toHaveLength(2)
  })

  it('assigns chat and vision models', async () => {
    const user = userEvent.setup()
    const { llm, router } = renderFlow()
    const save = await toStepFour(user)
    const chat = within(screen.getByRole('group', { name: '日常对话用的模型' }))
    const vision = within(screen.getByRole('group', { name: '看图识别用的模型' }))
    expect(chat.getByLabelText('日常对话')).toHaveValue('qwen-plus')
    expect(vision.getByLabelText('看图识别')).toHaveValue('qwen-vl-max')
    expect(vision.getByText('看图')).toBeInTheDocument()
    await user.click(save)
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/models'))
    expect(await screen.findByText('已保存')).toBeInTheDocument()
    const models = llm.record.assigns.map((a) => a.purpose)
    expect(models).toEqual(['chat', 'vision'])
  })

  it('marks capabilities manually and shows assignment warnings', async () => {
    const user = userEvent.setup()
    const { llm } = renderFlow({
      warnings: [ASSIGN_WARNING],
      assignErrors: { vision: { status: 422, code: 'llm_model_lacks_vision', message: LACKS_VISION_MESSAGE } },
    })
    const save = await toStepFour(user)
    const group = screen.getByRole('group', { name: '看图识别用的模型' })
    await user.selectOptions(within(group).getByLabelText('看图识别'), 'qwen-custom')
    expect(within(group).queryByText('看图')).not.toBeInTheDocument()
    await user.click(within(group).getByRole('checkbox', { name: '能看图（手动标注）' }))
    const manual = await within(group).findByText('看图 手动')
    expect(manual).toHaveClass('man')
    expect(within(group).getByRole('checkbox', { name: '能看图（手动标注）' })).toBeChecked()
    expect(await screen.findByText(ASSIGN_WARNING)).toBeInTheDocument()
    await user.click(within(group).getByRole('checkbox', { name: '能看图（手动标注）' }))
    await waitFor(() => expect(within(group).queryByText('看图 手动')).not.toBeInTheDocument())
    expect(llm.record.overrides.map((o) => o.body)).toEqual([{ vision: true }, { vision: null }])

    await user.click(save)
    expect(await within(group).findByText(LACKS_VISION_MESSAGE)).toBeInTheDocument()
    expect(within(group).getByText('错误码 llm_model_lacks_vision')).toBeInTheDocument()
    expect(llm.record.assigns.map((a) => a.purpose)).toEqual(['chat', 'vision'])
    expect(screen.getByRole('button', { name: '保存用途' })).toBeInTheDocument()
  })

  it('locks saving and the manual marks while either request is pending', async () => {
    const user = userEvent.setup()
    const assign = gate()
    const override = gate()
    const { llm } = renderFlow({ hold: { assign: assign.promise, override: override.promise } })
    const save = await toStepFour(user)
    const group = screen.getByRole('group', { name: '看图识别用的模型' })
    const mark = () => within(group).getByRole('checkbox', { name: '能看图（手动标注）' })

    await user.click(mark())
    await waitFor(() => expect(llm.record.overrides).toHaveLength(1))
    expect(mark()).toBeDisabled()
    expect(screen.getByRole('button', { name: '保存用途' })).toBeDisabled()
    override.open()
    await waitFor(() => expect(mark()).toBeEnabled())

    await user.click(save)
    await waitFor(() => expect(llm.record.assigns).toHaveLength(1))
    expect(mark()).toBeDisabled()
    expect(within(screen.getByRole('group', { name: '日常对话用的模型' })).getByRole('checkbox')).toBeDisabled()
    assign.open()
    await waitFor(() => expect(llm.record.assigns).toHaveLength(2))
  })
})
