import { useState } from 'react'
import type { ApiError } from '../../api/errors'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { TextField } from '../../components/TextField'
import { LISTING_UNSUPPORTED, stepForError, type StepStatus } from './flowReducer'
import { ErrorText } from './StepCredentials'

/**
 * 第 2 步“获取模型”：完成时写“其中 X 个能看图，Y 个能调用工具。”（或手动添加的编号）；
 * 失败时写说明原文与错误码，地址问题给“修改地址”，其他给“重试”；后端说列不出模型时还可以手动添加模型编号。
 */
export function StepFetch({ status, running, summary, onEditUrl, onRetry, onAdd, adding, addError }: {
  status: StepStatus
  running: boolean
  summary: string | null
  onEditUrl: () => void
  onRetry: () => void
  onAdd: (modelId: string) => void
  adding: boolean
  /** 手动添加失败（例如已有这个编号）：原样写在添加框下面 */
  addError: ApiError | null
}) {
  const [modelId, setModelId] = useState('')
  if (status.state === 'ok') return summary ? <div className="fs-b">{summary}</div> : null
  if (running) return <div className="fs-b" role="status">正在获取模型</div>
  if (status.state !== 'bad') return null
  const action = stepForError(status.code ?? '', 'fetch').action
  return (
    <div className="fs-b">
      <div className="err" role="alert">
        <Icon name="alert" size={18} />
        <span><ErrorText message={status.message} code={status.code} /></span>
      </div>
      <div className="fs-acts">
        {action === 'editUrl'
          ? <Button variant="quiet" size="sm" onPress={onEditUrl}>修改地址</Button>
          : <Button variant="quiet" size="sm" icon="refresh" onPress={onRetry}>重试</Button>}
      </div>
      {status.code === LISTING_UNSUPPORTED && (
        <div className="fs-add">
          <TextField label="模型编号" value={modelId} onChange={setModelId} maxLength={200} autoComplete="off" />
          <Button variant="quiet" isPending={adding} isDisabled={modelId.trim() === ''} onPress={() => onAdd(modelId.trim())}>
            添加
          </Button>
        </div>
      )}
      {addError && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span><ErrorText message={addError.message} code={addError.code} /></span>
        </div>
      )}
    </div>
  )
}
