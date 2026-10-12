import { lazy, Suspense, useId, useState } from 'react'
import { useCancelProposal } from '../../api/hooks/medical'
import type { MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { ButtonLink } from '../../components/ButtonLink'
import { Icon } from '../../components/Icon'
import { RefTag } from '../../components/RefTag'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import { formatMonthDay, todayISO } from '../../lib/dates'
import { CATEGORY_LABELS } from '../../lib/labels'
import '../../styles/components/medical-item.css'
import { shortDue } from '../medical/dueReason'
import { useItemContext } from '../medical/useItemContext'

// 继续遵守面板只在点了“继续遵守”后才加载
const ContinueSheet = lazy(() => import('../medical/ContinueSheet'))

/** 页头里待处理条的展开按钮（开场卡片收起后焦点落在这里） */
export const STRIP_TOGGLE_ID = 'pending-strip-toggle'
const MEDICAL_PAGE = '/health/medical?tab=active'

const isDue = (item: MedicalItemOut) => item.status === 'pending_review'

function proposedBy(item: MedicalItemOut, proposer: 'agent' | 'user' | null): string {
  const day = item.resolution_proposed_at ? formatMonthDay(todayISO(new Date(item.resolution_proposed_at))) : ''
  if (proposer === 'agent') return `助手根据你 ${day} 的话提出，仍在生效`
  if (proposer === 'user') return `你在 ${day} 提出，仍在生效`
  return `${day} 提出，仍在生效`
}

function StripItem({ item }: { item: MedicalItemOut }) {
  const context = useItemContext(item)
  const cancel = useCancelProposal()
  const toast = useToast()
  const [sheet, setSheet] = useState<'closed' | 'open' | 'loaded'>('closed')
  const due = isDue(item)
  const status = due ? (context.dueReason ? `待复核，${shortDue(context.dueReason)}` : '待复核') : '有解除建议'

  return (
    <div className="rvx-i">
      <div className="mo-h">
        <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
        <span className={due ? 'mo-st due' : 'mo-st pend'}>{status}</span>
      </div>
      <div className="mo-c">{item.content}</div>
      {!due && <p className="t-cap prop-by">{proposedBy(item, context.proposer)}<RefTag /></p>}
      <div className="acts-r">
        {due
          ? <Button variant="quiet" size="sm" onPress={() => setSheet('open')}>继续遵守</Button>
          : (
            <Button
              variant="quiet" size="sm" isPending={cancel.isPending}
              onPress={() => cancel.mutate(item.id, {
                onSuccess: () => toast.show('已撤销解除建议'),
                onError: (error) => toast.show(error.message),
              })}
            >
              不解除
            </Button>
          )}
        <ButtonLink to={MEDICAL_PAGE} variant="quiet" size="sm">去医嘱页处理</ButtonLink>
      </div>
      {sheet !== 'closed' && (
        <Suspense fallback={null}>
          <ContinueSheet
            item={item} dueReason={context.dueReason} isOpen={sheet === 'open'} area="reviewBar"
            onClose={() => setSheet('loaded')}
          />
        </Suspense>
      )}
    </div>
  )
}

/**
 * 待处理条（03a、03e）：页头玻璃里的一条白瓷条，在敏感区里。收起时一条写“类别 待复核”或“类别 有解除建议”，
 * 多条写“医嘱待处理 N 条”，不放医嘱原文；展开后每条写类别、状态、内容原文与动作：
 * 待复核是“继续遵守”与“去医嘱页处理”，带解除建议的是“不解除”与“去医嘱页处理”（并注明谁提出、仍在生效、仅供参考）。
 * 正在作为开场卡片显示的那一条由调用方去掉。
 */
export function PendingStrip({ items }: { items: MedicalItemOut[] }) {
  const [open, setOpen] = useState(false)
  const listId = useId()
  const first = items[0]
  if (!first) return null
  const single = items.length === 1
  const cat = single ? CATEGORY_LABELS[first.category] : '医嘱待处理'
  const st = single ? (isDue(first) ? '待复核' : '有解除建议') : `${items.length} 条`
  return (
    <Sensitive area="reviewBar" className="rv1-wrap">
      <button
        id={STRIP_TOGGLE_ID} type="button" className={single && !isDue(first) ? 'rv1 is-prop' : 'rv1'}
        aria-expanded={open} aria-controls={open ? listId : undefined} aria-label={`${cat} ${st}`}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="cat">{cat}</span>
        <span className="st">{st}</span>
        <span className="sp" />
        <Icon name="down" size={18} />
      </button>
      {open && <div className="rvx" id={listId}>{items.map((item) => <StripItem key={item.id} item={item} />)}</div>}
    </Sensitive>
  )
}
