// 健康（设计稿 06、07a 至 07e）：大标题页头（刷新经期与医嘱的全部查询）。经期与医嘱都开放时页头里是
// “经期 / 医嘱”分段（医嘱段的徽标是待处理的条数）；只开放医嘱时不显示分段，直接是医嘱的三个子标签；
// 只开放经期时直接是经期内容。/health/cycle 与 /health/medical 决定选中哪一段。
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router'
import { useMedicalReviews } from '../../api/hooks/medical'
import { useCapabilities } from '../../api/hooks/profile'
import { useSensitivePage } from '../../app/AppShell'
import { healthSegments } from '../../app/nav'
import { PATHS } from '../../app/paths'
import { PageHeader } from '../../components/PageHeader'
import { SegmentedTabs } from '../../components/SegmentedTabs'
import { CycleView } from '../cycle/CycleView'
import { MedicalTabs, MedicalView } from '../medical/MedicalView'

export default function HealthPage() {
  const { pathname } = useLocation()
  const segment = pathname.startsWith(PATHS.cycle) ? 'cycle' : 'medical'
  useSensitivePage(segment)
  const caps = useCapabilities()
  const reviews = useMedicalReviews()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const segments = caps.data ? healthSegments(caps.data) : []
  const reviewCount = reviews.data?.length ?? 0

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['medical'] })
    void queryClient.invalidateQueries({ queryKey: ['cycle'] })
  }

  return (
    <>
      <PageHeader titleKey="health" variant="big" onRefresh={refresh}>
        {segments.length > 1 && (
          <SegmentedTabs
            items={[
              { id: 'cycle', label: '经期' },
              { id: 'medical', label: '医嘱', badge: reviewCount > 0 ? reviewCount : undefined },
            ]}
            selectedKey={segment}
            onSelectionChange={(key) => void navigate(key === 'cycle' ? PATHS.cycle : PATHS.medical)}
            ariaLabel="健康分段"
          />
        )}
        {segment === 'medical' && <MedicalTabs />}
      </PageHeader>
      {segment === 'medical' ? <MedicalView /> : <CycleView />}
    </>
  )
}
