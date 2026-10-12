import { useLayoutEffect, useRef } from 'react'
import type { Capabilities } from '../../api/types'
import { CareBlock } from '../../components/CareBlock'
import { EvidenceFold } from '../../components/EvidenceFold'
import { JumpCard } from '../../components/JumpCard'
import { RefTag } from '../../components/RefTag'
import { Sensitive } from '../../components/Sensitive'
import { SystemSlip } from '../../components/SystemSlip'
import { ThoughtLine } from '../../components/ThoughtLine'
import { FLAG_CLUE, FLAG_FALLBACK } from '../../lib/contract'
import { RISK_PHONES, RISK_TITLE_KEYS } from '../../lib/labels'
import '../../styles/components/chat.css'
import { evidenceLines, jumpCardsFor, riskCategory, splitAssistantText, visibleWhileStreaming } from './agentText'

export const THINKING_TEXT = '正在查询你的记录并组织回答'

export interface AssistantMessageData {
  id: string
  text: string
  evidence: string
  flags: string[]
}

/**
 * 一条助手回答。风险话题只画“系统”加就医提示（后端的固定回复原文），不接任何别的内容；本次流式的这一条是 alert，
 * 历史里的是 note（不在每次打开页面时重复播报）。
 * 其余是白瓷气泡：回答、依据折叠（有依据时）、“仅供参考”与免责句；输出检查附加的医嘱提醒画成气泡外的系统附注；
 * 固定的安全回答在气泡下注明不是模型生成的；有医嘱解除线索时只给一个“去医嘱页处理”的跳转；
 * toolsUsed（只有本次流式回答才有）给对应的“去看看”跳转。live 时依据、附注与“仅供参考”淡入上移 4 像素。
 */
export function AssistantMessage({ message, caps, live = false, streamed = live, toolsUsed = [] }: {
  message: AssistantMessageData
  caps: Capabilities
  live?: boolean
  /** 本次打开页面后流式得到的（存好之后也是）：就医提示保持 alert，不在存好时改成 note */
  streamed?: boolean
  toolsUsed?: string[]
}) {
  const risk = riskCategory(message.flags)
  if (risk) {
    return (
      <div className="msg-sys">
        <div className="who">系统</div>
        <CareBlock titleKey={RISK_TITLE_KEYS[risk]} text={message.text} phones={RISK_PHONES[risk]} role={streamed ? 'alert' : 'note'} />
      </div>
    )
  }
  const { answer, notice, disclaimer } = splitAssistantText(message.text)
  const lines = evidenceLines(message.evidence)
  const after = live ? ' fresh' : ''
  const jumps = [
    ...(message.flags.includes(FLAG_CLUE) && caps.medical ? [{ to: '/health/medical?tab=active', label: '去医嘱页处理' }] : []),
    ...jumpCardsFor(toolsUsed, caps),
  ]
  return (
    <>
      <div className="msg-a">
        <div className="who">助手</div>
        <p className="ans">{answer}</p>
        <div className={`after${after}`}>
          {lines.length > 0 && <EvidenceFold lines={lines} />}
          <div className="tip"><RefTag />{disclaimer && <span>{disclaimer}</span>}</div>
        </div>
      </div>
      {message.flags.includes(FLAG_FALLBACK) && <p className="fixed-note">这是一条固定的安全回答，不是模型生成的。</p>}
      {notice && (
        <Sensitive area="notes" className={`note-wrap${after}`}>
          <SystemSlip title="医嘱提醒" lines={notice.lines} />
        </Sensitive>
      )}
      {jumps.map((jump) => <JumpCard key={jump.to} to={jump.to} label={jump.label} />)}
    </>
  )
}

/**
 * 流入中的文字：按帧把新到的可见部分作为新的文本节点追加在光标前（不重排已显示的文字）；
 * 医嘱提醒与免责句的开头先不显示，流完后它们各自出现在气泡外与气泡底部。
 */
function StreamText({ text }: { text: string }) {
  const target = useRef<HTMLSpanElement>(null)
  const shown = useRef(0)
  useLayoutEffect(() => {
    const el = target.current
    if (!el) return
    const visible = visibleWhileStreaming(text)
    if (visible.length > shown.current) {
      el.appendChild(document.createTextNode(visible.slice(shown.current)))
      shown.current = visible.length
    }
  }, [text])
  return <p className="ans"><span ref={target} /><span className="caret" aria-hidden="true" /></p>
}

/** 还在等或正在流入的回答：没有文字时（或减弱动效时）是一行“正在查询……”，有文字时逐段追加 */
export function PendingAnswer({ text }: { text: string }) {
  return (
    <div className="msg-a">
      <div className="who">助手</div>
      {text ? <StreamText text={text} /> : <ThoughtLine text={THINKING_TEXT} />}
    </div>
  )
}
