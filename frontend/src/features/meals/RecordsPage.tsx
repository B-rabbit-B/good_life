// 记录（设计稿 05）：大标题页头（刷新当天的汇总与记录），按能力清单显示“饮食 / 训练”分段（只有一个时不显示）；
// ?tab=training 时是训练（页头右上多一个“记一次训练”），否则饮食的一天（?date=YYYY-MM-DD，默认今天）。
// 饮食的账本、营养表与三餐在敏感区里；训练顶部的运动限制也在敏感区里。
import { useQueryClient } from '@tanstack/react-query'
import { Button as AriaButton } from 'react-aria-components'
import { useNavigate } from 'react-router'
import { useCapabilities } from '../../api/hooks/profile'
import { qk } from '../../api/keys'
import { useSensitivePage } from '../../app/AppShell'
import { recordSegments } from '../../app/nav'
import { PATHS } from '../../app/paths'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { SegmentedTabs } from '../../components/SegmentedTabs'
import { todayISO } from '../../lib/dates'
import { TrainingView } from '../fitness'
import { DiaryView } from './DiaryView'
import { useQueryParams } from '../../lib/queryParams'

const DATE = /^\d{4}-\d{2}-\d{2}$/
const SEGMENT_LABELS = { diet: '饮食', training: '训练' } as const

export default function RecordsPage() {
  useSensitivePage('records')
  const caps = useCapabilities()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [params, setParams] = useQueryParams()
  const segments = caps.data ? recordSegments(caps.data) : []
  const requested = params.get('tab')
  const tab = segments.find((segment) => segment === requested) ?? segments[0] ?? 'diet'
  const dateParam = params.get('date') ?? ''
  const date = DATE.test(dateParam) ? dateParam : todayISO()

  const refresh = () => {
    if (tab === 'training') {
      void queryClient.invalidateQueries({ queryKey: ['fitness'] })
      void queryClient.invalidateQueries({ queryKey: qk.constraints('exercise_limit') })
      return
    }
    void queryClient.invalidateQueries({ queryKey: qk.summary(date) })
    void queryClient.invalidateQueries({ queryKey: qk.meals(date) })
  }

  return (
    <>
      <PageHeader
        titleKey="records" variant="big" onRefresh={refresh}
        action={tab === 'training'
          ? (
            <AriaButton className="ibtn acc" aria-label="记一次训练" onPress={() => void navigate(PATHS.workoutNew)}>
              <Icon name="plus" />
            </AriaButton>
          )
          : undefined}
      >
        {segments.length > 1 && (
          <SegmentedTabs
            items={segments.map((id) => ({ id, label: SEGMENT_LABELS[id] }))}
            selectedKey={tab}
            onSelectionChange={(key) => setParams({ tab: key })}
            ariaLabel="记录分段"
          />
        )}
      </PageHeader>
      {tab === 'training' ? <TrainingView /> : <DiaryView date={date} />}
    </>
  )
}
