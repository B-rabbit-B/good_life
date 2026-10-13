import type { ReactNode } from 'react'
import type { ApiError } from '../../api/errors'
import type { TitleKey } from '../../lib/titles'
import '../../styles/components/states.css'
import { Button } from '../Button'
import { Title } from '../Title'

/** 失败：标题（默认“没能读取”）、后端说明原文、错误码；有 onRetry 时主按钮“重试”。 */
export function ErrorState({ titleKey = 'loadFailed', error, onRetry, actions, note }: {
  titleKey?: TitleKey
  error: ApiError
  onRetry?: () => void
  actions?: ReactNode
  note?: string
}) {
  return (
    <div className="state" role="alert">
      <Title k={titleKey} level="state" />
      <p className="st-p">{error.message}</p>
      <p className="st-code">错误码 {error.code}</p>
      {(onRetry || actions) && (
        <div className="st-acts">
          {onRetry && <Button variant="primary" icon="refresh" onPress={onRetry}>重试</Button>}
          {actions}
        </div>
      )}
      {note && <p className="t-cap st-note">{note}</p>}
    </div>
  )
}
