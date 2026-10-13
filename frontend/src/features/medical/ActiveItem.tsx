import type { MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { PENDING_REVIEW_NOTE } from '../../lib/contract'
import { CATEGORY_LABELS } from '../../lib/labels'
import '../../styles/components/medical-item.css'
import '../../styles/components/medical.css'
import { shortDue } from './dueReason'
import { itemActionsFor, type ItemActionKind } from './itemActions'
import { ProposalBlock } from './ProposalBlock'
import { useItemContext } from './useItemContext'

/**
 * 生效中的一条（07a）：类别、状态（待复核写赭色“待复核，到期原因”，否则“生效中”）、内容（黑体 500，左侧圆头竖线，
 * 只换行不截断）、日期行；待复核写后端的 PENDING_REVIEW_NOTE；带解除建议的放解除建议区。
 * 动作按 itemActionsFor：待复核是“继续遵守”“确认解除”，带建议的在建议区里是“不解除”“确认解除”，其余是“修改”“确认解除”。
 * onAction 把到期原因一并交出（继续遵守面板要用它标出触发的一项）。
 */
export function ActiveItem({ item, keepPending, onAction }: {
  item: MedicalItemOut
  keepPending: boolean
  onAction: (kind: ItemActionKind, dueReason: string | null) => void
}) {
  const { dueReason, proposer } = useItemContext(item)
  const due = item.status === 'pending_review'
  const actions = itemActionsFor(item)
  const inProposal = actions.some((action) => action.kind === 'cancel-proposal')
  const status = due ? (dueReason ? `待复核，${shortDue(dueReason)}` : '待复核') : '生效中'
  return (
    <div className="mo">
      <div className="mo-h">
        <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
        <span className={due ? 'mo-st due' : 'mo-st act'}>{status}</span>
      </div>
      <div className="mo-c">{item.content}</div>
      <div className="mo-d">
        <span>生效 <span className="n">{item.start_date}</span></span>
        {item.review_date && <span>复查 <span className="n">{item.review_date}</span></span>}
        {item.end_date && <span>预计结束 <span className="n">{item.end_date}</span></span>}
      </div>
      {due && <p className="t-cap mo-note">{PENDING_REVIEW_NOTE}</p>}
      {item.resolution_proposed_at !== null && (
        <ProposalBlock
          item={item} proposer={proposer} actions={inProposal} keepPending={keepPending}
          onKeep={() => onAction('cancel-proposal', dueReason)} onResolve={() => onAction('resolve', dueReason)}
        />
      )}
      {!inProposal && actions.length > 0 && (
        <div className="acts-r">
          {actions.map(({ kind, label }) => (
            <Button
              key={kind} size="sm" variant={kind === 'resolve' ? 'danger-outline' : 'quiet'} icon={kind === 'edit' ? 'edit' : undefined}
              onPress={() => onAction(kind, dueReason)}
            >
              {label}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
