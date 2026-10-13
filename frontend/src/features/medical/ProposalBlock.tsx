import type { MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { RefTag } from '../../components/RefTag'
import { formatMonthDay, todayISO } from '../../lib/dates'
import '../../styles/components/medical.css'

/**
 * 解除建议（07a）：面板里一块钴蓝浅底的圆角区。写明谁提出（取自条目事件）并加“仅供参考”：
 * 助手提出的写“助手在 某日 提出了一条解除建议”，理由行写“助手给出的理由：”——理由是助手写的，不当作你的原话；
 * 你本人提出的写“你提出了一条解除建议”与“理由：”；后面引用后端的理由原文。建议不改变约束。
 * actions 为真时给“不解除”与“确认解除”（待复核的条目用它自己那一行的动作）。
 */
export function ProposalBlock({ item, proposer, actions, keepPending, onKeep, onResolve }: {
  item: MedicalItemOut
  proposer: 'agent' | 'user' | null
  actions: boolean
  keepPending?: boolean
  onKeep?: () => void
  onResolve?: () => void
}) {
  const day = item.resolution_proposed_at ? formatMonthDay(todayISO(new Date(item.resolution_proposed_at))) : ''
  return (
    <div className="prop">
      <div className="prop-h">
        <b>{proposer === 'agent' ? `助手在 ${day} 提出了一条解除建议` : proposer === 'user' ? '你提出了一条解除建议' : '有一条解除建议'}</b>
        <RefTag />
      </div>
      <p>{proposer === 'agent' ? '助手给出的理由：' : '理由：'}</p>
      {item.resolution_reason && <blockquote>{item.resolution_reason}</blockquote>}
      <p className="t-cap">建议不会改变约束，只有你在这里确认后才会解除。</p>
      {actions && (
        <div className="acts-r">
          <Button variant="quiet" size="sm" isPending={keepPending} onPress={() => onKeep?.()}>不解除</Button>
          <Button variant="danger-outline" size="sm" onPress={() => onResolve?.()}>确认解除</Button>
        </div>
      )}
    </div>
  )
}
