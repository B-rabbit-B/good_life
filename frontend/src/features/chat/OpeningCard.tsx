import { lazy, Suspense, useId, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAnswerOpening, useDeclineOpening } from '../../api/hooks/agent'
import { useCapabilities } from '../../api/hooks/profile'
import type { MedicalItemOut, OpeningOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Sensitive } from '../../components/Sensitive'
import { Surface } from '../../components/Surface'
import { useToast } from '../../components/Toast'
import '../../styles/components/chat.css'
import { useItemContext } from '../../api/itemContext/useItemContext'
import { openingActionsFor, type OpeningAction } from './openingActions'

// 继续遵守面板只在点了“继续遵守”后才加载，不进对话页的首屏脚本
const ContinueSheet = lazy(() => import('../medical').then((medical) => ({ default: medical.ContinueSheet })))

const NO_CAPS = { cycle: false, medical: false, nutrition: false, fitness: false }

/**
 * 开场卡片：静玻璃，左侧钴蓝圆头竖线，“今天想问你”加后端的问句原文（18 号黑体 500）。
 * 跳转与继续遵守成功都把开场标为已回答，“稍后”“不用了”标为已拒绝；之后卡片收起（缓存里的开场清空），
 * review_due 的条目回到页头的待处理条里。
 */
export function OpeningCard({ opening, target, onCollapsed }: {
  opening: OpeningOut
  /** 待处理列表的第一条（review_due 开场问的就是它） */
  target?: MedicalItemOut
  onCollapsed: () => void
}) {
  const caps = useCapabilities().data ?? NO_CAPS
  const navigate = useNavigate()
  const toast = useToast()
  const answer = useAnswerOpening()
  const decline = useDeclineOpening()
  const context = useItemContext(opening.kind === 'review_due' ? target : undefined)
  const [sheet, setSheet] = useState<'closed' | 'open' | 'loaded'>('closed')
  const questionId = useId()

  const press = (action: OpeningAction) => {
    if (action.kind === 'continue') {
      setSheet('open')
    } else if (action.kind === 'navigate' && action.to) {
      answer.mutate(opening.id)
      void navigate(action.to)
    } else {
      decline.mutate(opening.id, { onSuccess: onCollapsed, onError: (error) => toast.show(error.message) })
    }
  }

  return (
    <Sensitive area="opening" className="open-wrap">
      <Surface tier="still" className="open" role="group" aria-labelledby={questionId}>
        <span className="t-cap">今天想问你</span>
        <p id={questionId}>{opening.question}</p>
        <div className="acts">
          {openingActionsFor(opening, target, caps).map((action) => (
            <Button
              key={action.label}
              variant={action.kind === 'decline' ? 'text' : 'quiet'} size="sm" ink={action.kind === 'decline'}
              isPending={action.kind === 'decline' && decline.isPending}
              onPress={() => press(action)}
            >
              {action.label}
            </Button>
          ))}
        </div>
      </Surface>
      {sheet !== 'closed' && target && (
        <Suspense fallback={null}>
          <ContinueSheet
            item={target} dueReason={context.dueReason} isOpen={sheet === 'open'} area="opening"
            onClose={() => setSheet('loaded')}
            onDone={() => answer.mutate(opening.id, { onSuccess: onCollapsed })}
          />
        </Suspense>
      )}
    </Sensitive>
  )
}
