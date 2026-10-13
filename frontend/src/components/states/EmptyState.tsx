import { useId, type ReactNode } from 'react'
import type { TitleKey } from '../../lib/titles'
import '../../styles/components/states.css'
import { Title } from '../Title'

/** 无数据：写清发生了什么、下一步做什么。 */
export function EmptyState({ titleKey, body, actions }: { titleKey: TitleKey; body: string; actions?: ReactNode }) {
  const id = useId()
  return (
    <section className="state" aria-labelledby={id}>
      <Title k={titleKey} level="state" id={id} />
      <p className="st-p">{body}</p>
      {actions && <div className="st-acts">{actions}</div>}
    </section>
  )
}
