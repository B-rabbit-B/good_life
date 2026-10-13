// 添加模型服务的四步（设计稿 10a、10b）：1 填写地址与密钥 → 保存（创建，之后改动用 PATCH 只带改了的字段）并立即清空密钥输入框；
// 2 获取模型；3 测试连通（前端计时）；4 选择用途模型。失败写在出错的那一步里（flowReducer.stepForError）。
// 密钥只在这里的局部状态里：不进 URL、存储与查询缓存；创建与修改的变更用完就 reset（变更缓存里不留请求体）。
import { useEffect, useReducer, useRef, useState, type ReactNode } from 'react'
import { type ApiError, asApiError } from '../../api/errors'
import {
  useAddModel, useCreateProvider, useFetchModels, usePresets, useProviderModels, useTestProvider, useUpdateProvider,
  type ProviderChanges,
} from '../../api/hooks/llmSettings'
import type { ProviderOut } from '../../api/types'
import { StatusMark, type StatusState } from '../../components/StatusMark'
import { fmtNum } from '../../lib/format'
import type { ProviderKind } from '../../lib/labels'
import { useSingleFlight } from '../../lib/singleFlight'
import { llmErrorShort, PROVIDER_KIND_LABELS } from '../../lib/settingsLabels'
import '../../styles/components/settings.css'
import '../../styles/components/status-mark.css'
import { flowReducer, initialFlow, type StepNo, type StepStatus } from './flowReducer'
import { StepAssign } from './StepAssign'
import { StepCredentials, type CredentialsForm } from './StepCredentials'
import { StepFetch } from './StepFetch'
import { defaultTestModel, StepTest } from './StepTest'

const TITLES: Record<StepNo, string> = { 1: '填写地址与密钥', 2: '获取模型', 3: '测试连通', 4: '选择用途模型' }
const STATE_TEXT: Record<StepStatus['state'], string> = { todo: '未开始', current: '进行中', ok: '已完成', bad: '失败' }
const LI_CLASS: Record<StepStatus['state'], string> = { todo: 'fs off', current: 'fs cur', ok: 'fs ok', bad: 'fs bad' }
const KINDS = Object.keys(PROVIDER_KIND_LABELS) as ProviderKind[]

function Step({ n, status, running, small, children }: {
  n: StepNo
  status: StepStatus
  running: boolean
  small?: string | null
  children?: ReactNode
}) {
  const mark: StatusState = running ? 'running' : status.state
  return (
    <li className={LI_CLASS[status.state]} data-step={n}>
      <StatusMark state={mark} index={n} />
      <div className="fs-c">
        <div className="fs-t">
          <span>{TITLES[n]}<span className="sr-only">（{running ? '进行中' : STATE_TEXT[status.state]}）</span></span>
          {small && <small>{small}</small>}
        </div>
        {children}
      </div>
    </li>
  )
}

export function ProviderFlow({ onDone }: { onDone: () => void }) {
  const [flow, dispatch] = useReducer(flowReducer, initialFlow)
  const [form, setForm] = useState<CredentialsForm>({ type: 'kind:openai_compatible', name: '', baseUrl: '', apiKey: '' })
  const [saved, setSaved] = useState<ProviderOut | null>(null)
  const [running, setRunning] = useState<'save' | 'fetch' | 'add' | 'test' | null>(null)
  const [fetchSummary, setFetchSummary] = useState<{ small: string; body: string; count: number } | null>(null)
  const [testModel, setTestModel] = useState('')
  const [testResult, setTestResult] = useState<{ small: string; body: string } | null>(null)
  const [addError, setAddError] = useState<ApiError | null>(null)
  const [focusUrl, setFocusUrl] = useState(0)
  const urlBox = useRef<HTMLDivElement>(null)

  const presets = usePresets()
  const create = useCreateProvider()
  const update = useUpdateProvider()
  const fetchModels = useFetchModels()
  const models = useProviderModels(flow.providerId)
  const addModel = useAddModel(flow.providerId)
  const test = useTestProvider(flow.providerId)
  const flight = useSingleFlight()

  useEffect(() => {
    if (focusUrl > 0) urlBox.current?.querySelector('input')?.focus()
  }, [focusUrl])

  const types = [
    ...(presets.data ?? []).map((p) => ({ value: `preset:${p.id}`, label: `${p.name}（${PROVIDER_KIND_LABELS[p.kind]}）` })),
    ...KINDS.map((kind) => ({ value: `kind:${kind}`, label: `自定义（${PROVIDER_KIND_LABELS[kind]}）` })),
  ]
  const kindOf = (type: string): ProviderKind =>
    presets.data?.find((p) => `preset:${p.id}` === type)?.kind ?? (type.replace('kind:', '') as ProviderKind)
  const changeForm = (next: CredentialsForm) => {
    const preset = next.type !== form.type ? presets.data?.find((p) => `preset:${p.id}` === next.type) : undefined
    setForm(preset ? { ...next, name: preset.name, baseUrl: preset.base_url } : next)
  }

  const runFetch = async (providerId: string) => {
    setRunning('fetch')
    try {
      const result = await fetchModels.mutateAsync(providerId)
      const vision = result.models.filter((m) => m.capabilities.vision === true).length
      const tools = result.models.filter((m) => m.capabilities.tools === true).length
      setFetchSummary({ small: `${result.total} 个`, body: `其中 ${vision} 个能看图，${tools} 个能调用工具。`, count: result.total })
      setTestModel(defaultTestModel(result.models))
      dispatch({ type: 'fetched' })
    } catch (caught) {
      const error = asApiError(caught)
      dispatch({ type: 'failed', phase: 'fetch', code: error.code, message: error.message })
    } finally {
      setRunning(null)
    }
  }

  /** 第一次是创建；之后（第 1 步出错回来）只 PATCH 改了的字段，改了密钥才带密钥 */
  const changes = (current: ProviderOut): ProviderChanges => ({
    ...(form.name.trim() !== current.name ? { name: form.name.trim() } : {}),
    ...(form.baseUrl.trim() !== current.base_url ? { base_url: form.baseUrl.trim() } : {}),
    ...(form.apiKey.trim() ? { api_key: form.apiKey.trim() } : {}),
  })

  const saveAndFetch = () => flight(async () => {
    setRunning('save')
    let provider = saved
    try {
      if (!provider) {
        provider = await create.mutateAsync({
          name: form.name.trim(), kind: kindOf(form.type), base_url: form.baseUrl.trim(), api_key: form.apiKey.trim(),
        })
      } else {
        const patch = changes(provider)
        if (Object.keys(patch).length > 0) provider = await update.mutateAsync({ id: provider.id, changes: patch })
      }
    } catch (caught) {
      const error = asApiError(caught)
      dispatch({ type: 'failed', phase: 'save', code: error.code, message: error.message })
      setRunning(null)
      return
    } finally {
      // 请求体里有密钥：不论成败都立即从变更缓存里清掉
      create.reset()
      update.reset()
    }
    setForm((current) => ({ ...current, apiKey: '', name: provider.name, baseUrl: provider.base_url }))
    setSaved(provider)
    dispatch({ type: 'saved', providerId: provider.id })
    await runFetch(provider.id)
  })

  const retryFetch = () => flight(async () => {
    if (!flow.providerId) return
    dispatch({ type: 'retry', step: 2 })
    await runFetch(flow.providerId)
  })

  const addManual = (modelId: string) => flight(async () => {
    setRunning('add')
    setAddError(null)
    try {
      await addModel.mutateAsync(modelId)
      setFetchSummary({ small: '1 个', body: `已手动添加 ${modelId}。`, count: 1 })
      setTestModel(modelId)
      dispatch({ type: 'fetched' })
    } catch (caught) {
      setAddError(asApiError(caught))
    } finally {
      setRunning(null)
    }
  })

  const runTest = () => flight(async () => {
    setRunning('test')
    const started = performance.now()
    try {
      const report = await test.mutateAsync(testModel)
      const seconds = (performance.now() - started) / 1000
      if (report.ok) {
        // 列不出模型但对话成功（ok_listing_unsupported）：后端的总结里说了要手动添加模型编号，写它而不是只写对话成功
        const body = report.conclusion === 'ok_listing_unsupported' ? report.message : (report.chat?.message ?? report.message)
        setTestResult({ small: seconds < 0.1 ? '用时不到 0.1 秒' : `用时 ${fmtNum(seconds, 1)} 秒`, body })
        dispatch({ type: 'tested' })
      } else {
        const code = report.chat?.code ?? report.listing.code ?? report.conclusion
        dispatch({ type: 'failed', phase: 'test', code, message: report.message })
      }
    } catch (caught) {
      const error = asApiError(caught)
      dispatch({ type: 'failed', phase: 'test', code: error.code, message: error.message })
    } finally {
      setRunning(null)
    }
  })

  const { steps } = flow
  const shortFor = (status: StepStatus, ok: string | null | undefined) =>
    status.state === 'bad' ? llmErrorShort(status.code) : status.state === 'ok' ? ok : null
  const list = models.data ?? []
  return (
    <ol className="flow" aria-label="添加步骤">
      <Step n={1} status={steps[1]} running={running === 'save'} small={shortFor(steps[1], '已保存')}>
        <StepCredentials
          status={steps[1]} saved={saved} form={form} types={types} onChange={changeForm}
          onSubmit={() => void saveAndFetch()} pending={running === 'save'} urlBox={urlBox}
        />
      </Step>
      <Step n={2} status={steps[2]} running={running === 'fetch' || running === 'add'} small={shortFor(steps[2], fetchSummary?.small)}>
        <StepFetch
          status={steps[2]} running={running === 'fetch'} summary={fetchSummary?.body ?? null} empty={fetchSummary?.count === 0}
          onEditUrl={() => {
            dispatch({ type: 'editUrl' })
            setFocusUrl((n) => n + 1)
          }}
          onRetry={() => void retryFetch()} onAdd={(id) => void addManual(id)} adding={running === 'add'} addError={addError}
        />
      </Step>
      <Step n={3} status={steps[3]} running={running === 'test'} small={shortFor(steps[3], testResult?.small)}>
        <StepTest
          status={steps[3]} models={list} model={testModel} onModel={setTestModel} onTest={() => void runTest()}
          running={running === 'test'} result={testResult?.body ?? null}
        />
      </Step>
      <Step n={4} status={steps[4]} running={false}>
        {steps[4].state === 'current' && list.length > 0 && <StepAssign models={list} tested={testModel} onDone={onDone} />}
      </Step>
    </ol>
  )
}
