import { useId, type ReactNode } from 'react'
import type { TitleKey } from '../../lib/titles'
import '../../styles/components/states.css'
import { Title } from '../Title'

/** 需要授权或前置条件（定位、未配置模型、登录过期）：说明为什么要、不给会怎样，再给动作。 */
export function AuthNeededState({ titleKey, body, actions }: { titleKey: TitleKey; body: string; actions: ReactNode }) {
  const id = useId()
  return (
    <section className="state" aria-labelledby={id}>
      <Title k={titleKey} level="state" id={id} />
      <p className="st-p">{body}</p>
      <div className="st-acts">{actions}</div>
    </section>
  )
}
