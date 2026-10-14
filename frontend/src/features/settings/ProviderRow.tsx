import { useState } from 'react'
import { type ApiError, asApiError } from '../../api/errors'
import { useTestProvider } from '../../api/hooks/llmSettings'
import type { ConnectionReportOut, ProviderOut } from '../../api/types'
import { Button } from '../../components/Button'
import { VerdictMark } from '../../components/VerdictMark'
import { useSingleFlight } from '../../lib/singleFlight'
import { KeyMask } from './KeyMask'

/**
 * 一个模型服务：名称、地址（完整显示，可换行）、密钥掩码；“测试连通”用分配给它的模型（有的话）测一次，
 * 结果写“已连通”或“未连通”加后端的说明原文（失败时带错误码）。“删除”打开模型服务页持有的确认面板（DeleteProviderSheet）。
 */
export function ProviderRow({ provider, modelId, onDelete }: {
  provider: ProviderOut
  modelId: string | undefined
  onDelete: (provider: ProviderOut) => void
}) {
  const test = useTestProvider(provider.id)
  const flight = useSingleFlight()
  const [result, setResult] = useState<{ report: ConnectionReportOut } | { error: ApiError } | null>(null)
  const run = () => flight(async () => {
    setResult(null)
    try {
      setResult({ report: await test.mutateAsync(modelId) })
    } catch (caught) {
      setResult({ error: asApiError(caught) })
    }
  })
  return (
    <li className="prov">
      <div className="prov-n">
        <b>{provider.name}</b>
        <div className="url">{provider.base_url}</div>
      </div>
      <span className="prov-test">
        <Button variant="text" isPending={test.isPending} onPress={() => void run()}>测试连通</Button>
      </span>
      <KeyMask hint={provider.key_hint} />
      <span className="prov-del">
        <Button variant="text" onPress={() => onDelete(provider)}>删除</Button>
      </span>
      {result && 'report' in result && (
        <div className="prov-r" role="status">
          <VerdictMark conclusion={result.report.ok ? 'suitable' : 'not_recommended'} label={result.report.ok ? '已连通' : '未连通'} />
          <span>{result.report.message}</span>
          {!result.report.ok && <small>错误码 {result.report.chat?.code ?? result.report.listing.code ?? result.report.conclusion}</small>}
        </div>
      )}
      {result && 'error' in result && (
        <div className="prov-r" role="alert">
          <VerdictMark conclusion="not_recommended" label="未连通" />
          <span>{result.error.message}</span>
          <small>错误码 {result.error.code}</small>
        </div>
      )}
    </li>
  )
}
