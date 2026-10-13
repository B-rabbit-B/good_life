import type { MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { RefTag } from '../../components/RefTag'
import { formatMonthDay, todayISO } from '../../lib/dates'
import '../../styles/components/medical.css'

const WHO = { agent: '助手', user: '你' } as const

/**
 * 解除建议（07a）：面板里一块钴蓝浅底的圆角区。写明谁提出（取自条目事件）并加“仅供参考”，
 * 助手提出的写“依据是你在 某日 的对话里说：”，你本人提出的写“理由：”，后面引用后端的理由原文；
 * 建议不改变约束。actions 为真时给“不解除”与“确认解除”（待复核的条目用它自己那一行的动作）。
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
        <b>{proposer ? `${WHO[proposer]}提出了一条解除建议` : '有一条解除建议'}</b>
        <RefTag />
      </div>
      <p>{proposer === 'agent' ? `依据是你在 ${day} 的对话里说：` : '理由：'}</p>
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
