// 单独同意的守门：未同意时显示同意面板，已同意时显示模块内容。模块是否开放由路由守卫与能力清单决定，这里只看同意。
import type { ReactNode } from 'react'
import { asApiError } from '../../api/errors'
import { useConsents } from '../../api/hooks/consents'
import type { ConsentKind } from '../../api/types'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { ConsentPanel } from './ConsentPanel'

export function ConsentGate({ kind, children }: { kind: ConsentKind; children: ReactNode }) {
  const consents = useConsents()
  const consent = consents.data?.find((c) => c.kind === kind)
  if (!consent) {
    return consents.isError
      ? <ErrorState error={asApiError(consents.error)} onRetry={() => void consents.refetch()} />
      : <LoadingState variant="page" text="正在读取单独同意" />
  }
  return consent.granted ? children : <ConsentPanel kind={kind} />
}
