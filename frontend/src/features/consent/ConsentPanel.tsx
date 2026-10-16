// 单独同意面板：经期或医嘱第一次使用前显示，不与免责声明打包。标题是黑体，正文原样取自后端（按换行分段）；
// 必须单独勾选“我已阅读并同意”，“同意并开始使用”才可用；“暂不使用”只回到上一页，不进入模块。
// 同意的是面板上显示的那个版本；后端说版本已更新（409 consent_outdated）时显示它的说明与错误码、重新读取正文并要求重新勾选。
import { useId, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { ApiError, asApiError } from '../../api/errors'
import { useConsents, useGrantConsent } from '../../api/hooks/consents'
import type { ConsentKind } from '../../api/types'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { Icon } from '../../components/Icon'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { CONSENT_OUTDATED } from '../../lib/contract'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/consent.css'
import '../../styles/components/field-input.css'

/** 有上一页时退回上一页；直接打开（例如从地址栏进来）时没有上一页，去对话页 */
function useGoBack(): () => void {
  const navigate = useNavigate()
  const { key } = useLocation()
  return () => {
    const idx = (window.history.state as { idx?: unknown } | null)?.idx
    const canGoBack = typeof idx === 'number' ? idx > 0 : key !== 'default'
    if (canGoBack) void navigate(-1)
    else void navigate(PATHS.chat, { replace: true })
  }
}

export function ConsentPanel({ kind }: { kind: ConsentKind }) {
  const id = useId()
  const consents = useConsents()
  const grant = useGrantConsent()
  const goBack = useGoBack()
  const [read, setRead] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  // 双击时 isPending 还没来得及渲染：用单次锁守住，同一时间只提交一次
  const flight = useSingleFlight()
  const consent = consents.data?.find((c) => c.kind === kind)

  if (!consent) {
    return consents.isError
      ? <ErrorState error={asApiError(consents.error)} onRetry={() => void consents.refetch()} />
      : <LoadingState variant="page" text="正在读取单独同意的说明" />
  }

  const agree = () => {
    const run = flight(async () => {
      setError(null)
      try {
        await grant.mutateAsync({ kind, version: consent.current_version })
      } catch (caught) {
        const apiError = asApiError(caught)
        setError(apiError)
        if (apiError.code === CONSENT_OUTDATED) {
          setRead(false)
          void consents.refetch()
        }
      }
    })
    void run
  }

  return (
    <section className="plate consent" aria-labelledby={id}>
      <h2 id={id} className="cs-h">单独同意：{consent.title}</h2>
      <div className="cs-text">
        {consent.text.split('\n').filter((line) => line.trim() !== '').map((line, i) => <p key={i}>{line}</p>)}
      </div>
      <Checkbox isSelected={read} onChange={setRead}>我已阅读并同意</Checkbox>
      {error && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span>{error.message}<small>错误码 {error.code}</small></span>
        </div>
      )}
      <div className="cs-acts">
        {/* 重新读取正文期间不能同意：否则会再次提交旧版本 */}
        <Button
          variant="primary" block isDisabled={!read || consents.isFetching} isPending={grant.isPending} onPress={agree}
        >
          同意并开始使用
        </Button>
        <Button variant="quiet" block isDisabled={grant.isPending} onPress={goBack}>暂不使用</Button>
      </div>
    </section>
  )
}
