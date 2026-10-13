// 免责声明确认（设计稿 01b）：正文原样取自后端，按换行切成条目，版本号写在页头；没有返回键（守卫要求先确认）。
// 勾选“我已阅读并理解以上内容”后才能确认；确认的是页面上显示的那个版本。后端说版本已更新（409 disclaimer_outdated）时
// 显示它的说明、重新读取正文，并要求重新勾选。
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { ApiError, asApiError } from '../../api/errors'
import { useAcceptDisclaimer, useDisclaimer } from '../../api/hooks/disclaimer'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { Dock } from '../../components/Dock'
import { PageHeader } from '../../components/PageHeader'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import '../../styles/components/onboarding.css'
import { errorsOf } from '../../lib/formErrors'
import { FormError } from '../../components/FormError'

const OUTDATED = 'disclaimer_outdated'

export default function DisclaimerPage() {
  const disclaimer = useDisclaimer()
  const accept = useAcceptDisclaimer()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from
  const [read, setRead] = useState(false)
  const [errors, setErrors] = useState<string[]>([])

  if (!disclaimer.data) {
    return (
      <>
        <PageHeader titleKey="disclaimer" variant="big" />
        {disclaimer.isError
          ? <ErrorState error={asApiError(disclaimer.error)} onRetry={() => void disclaimer.refetch()} />
          : <LoadingState variant="page" text="正在读取免责声明" />}
      </>
    )
  }

  const { version, text } = disclaimer.data
  const lines = text.split('\n').map((line) => line.trim()).filter(Boolean)

  const confirm = () => {
    setErrors([])
    accept.mutate(version, {
      onSuccess: () => void navigate(from ?? PATHS.root, { replace: true }),
      onError: (error) => {
        setErrors(Object.values(errorsOf(error)))
        if (error instanceof ApiError && error.code === OUTDATED) {
          setRead(false)
          void disclaimer.refetch()
        }
      },
    })
  }

  return (
    <>
      <PageHeader titleKey="disclaimer" variant="big" caption={`版本 ${version}`} />
      <p className="intro">开始使用前，请读完下面 {lines.length} 条。</p>
      <div className="plate">
        {errors.length > 0 && <div className="disc-err"><FormError messages={errors} /></div>}
        <ol className="disc">
          {lines.map((line, i) => <li key={i}>{line}</li>)}
        </ol>
      </div>
      <Dock tall>
        <div className="disc-chk">
          <Checkbox isSelected={read} onChange={setRead}>我已阅读并理解以上内容</Checkbox>
        </div>
        {/* 重新读取正文期间不能确认：否则会再次提交旧版本 */}
        <Button variant="primary" block isDisabled={!read || disclaimer.isFetching} isPending={accept.isPending} onPress={confirm}>
          确认并继续
        </Button>
        <span className="t-cap disc-note">之后可以在“我的”里随时查看</span>
      </Dock>
    </>
  )
}
