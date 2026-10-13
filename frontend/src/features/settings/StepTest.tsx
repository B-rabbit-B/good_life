import type { ModelOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { SelectField } from '../../components/SelectField'
import type { StepStatus } from './flowReducer'
import { ErrorText } from './StepCredentials'

/** 默认测试第一个不是“非对话模型”的模型（capabilities.chat 不为 false） */
export function defaultTestModel(models: ModelOut[]): string {
  return (models.find((m) => m.capabilities.chat !== false) ?? models[0])?.model_id ?? ''
}

/**
 * 第 3 步“测试连通”：选一个模型发一次最小对话。完成时写后端的说明原文（用时写在标题右侧）；
 * 失败时写说明原文与错误码，给“重新测试”。
 */
export function StepTest({ status, models, model, onModel, onTest, running, result }: {
  status: StepStatus
  models: ModelOut[]
  model: string
  onModel: (modelId: string) => void
  onTest: () => void
  running: boolean
  result: string | null
}) {
  if (status.state === 'ok') return result ? <div className="fs-b">{result}</div> : null
  if (status.state === 'todo') return null
  const bad = status.state === 'bad'
  return (
    <div className="fs-b">
      {bad && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span><ErrorText message={status.message} code={status.code} /></span>
        </div>
      )}
      <SelectField
        label="测试用的模型" value={model} onChange={onModel} isDisabled={running}
        options={models.map((m) => ({ value: m.model_id, label: m.model_id }))}
      />
      <div className="fs-acts">
        <Button
          variant={bad ? 'quiet' : 'primary'} size={bad ? 'sm' : 'md'} block={!bad} icon={bad ? 'refresh' : undefined}
          isPending={running} isDisabled={model === ''} onPress={onTest}
        >
          {bad ? '重新测试' : '测试连通'}
        </Button>
      </div>
    </div>
  )
}
