// 健康（设计稿 06、07a 至 07e）：大标题页头（刷新经期与医嘱的全部查询）。经期与医嘱都开放时页头里是
// “经期 / 医嘱”分段（医嘱段的徽标是待处理的条数）；只开放医嘱时不显示分段，直接是医嘱的三个子标签；
// 只开放经期时直接是经期内容。/health/cycle 与 /health/medical 决定选中哪一段。
// 经期内容（连同 React Aria 的月历）按需加载：只看医嘱时不下载月历。
// 经期与医嘱各要单独同意：未同意时分段照常显示，内容换成同意面板，医嘱的子标签与待处理徽标也不出现（不请求）。
import { useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useModuleReady } from '../../api/hooks/consents'
import { useMedicalReviews } from '../../api/hooks/medical'
import { useCapabilities } from '../../api/hooks/profile'
import { useSensitivePage } from '../../app/AppShell'
import { healthSegments } from '../../app/nav'
import { PATHS } from '../../app/paths'
import { PageHeader } from '../../components/PageHeader'
import { SegmentedTabs } from '../../components/SegmentedTabs'
import { LoadingState } from '../../components/states/LoadingState'
import { ConsentGate } from '../consent'
import { loadCycleView } from '../cycle'
import { MedicalTabs, MedicalView } from '../medical'

const CycleView = lazy(loadCycleView)

export default function HealthPage() {
  const { pathname } = useLocation()
  const segment = pathname.startsWith(PATHS.cycle) ? 'cycle' : 'medical'
  useSensitivePage(segment)
  const caps = useCapabilities()
  const reviews = useMedicalReviews()
  const medicalReady = useModuleReady('medical')
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
        {segment === 'medical' && medicalReady && <MedicalTabs />}
      </PageHeader>
      {segment === 'medical'
        ? <ConsentGate kind="medical"><MedicalView /></ConsentGate>
        : (
          <ConsentGate kind="cycle">
            <Suspense fallback={<LoadingState variant="page" text="正在读取经期记录" />}>
              <CycleView />
            </Suspense>
          </ConsentGate>
        )}
    </>
  )
}
