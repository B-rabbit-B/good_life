// 免责声明（只读，线框）：正文按行显示、版本号写在页头右侧，下面写这个版本的确认时间。
import type { ApiError } from '../../api/errors'
import { useDisclaimer, useDisclaimerStatus } from '../../api/hooks/disclaimer'
import { PATHS } from '../../app/paths'
import { PageHeader } from '../../components/PageHeader'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { formatTime, todayISO } from '../../lib/dates'
import '../../styles/components/settings.css'

export default function DisclaimerViewPage() {
  const disclaimer = useDisclaimer()
  const status = useDisclaimerStatus()
  const at = status.data?.accepted_at
  return (
    <>
      <PageHeader
        titleKey="disclaimer" variant="sub" back={PATHS.me}
        caption={disclaimer.data ? `版本 ${disclaimer.data.version}` : undefined}
      />
      {disclaimer.isError && <ErrorState error={disclaimer.error as ApiError} onRetry={() => void disclaimer.refetch()} />}
      {!disclaimer.data && !disclaimer.isError && <LoadingState variant="page" text="正在读取免责声明" />}
      {disclaimer.data && (
        <div className="plate dv">
          {disclaimer.data.text.split('\n').filter((line) => line.trim() !== '').map((line, i) => <p key={i}>{line}</p>)}
        </div>
      )}
      {at && <p className="t-cap dv-at">已于 {todayISO(new Date(at))} {formatTime(at)} 确认这个版本。</p>}
    </>
  )
}
