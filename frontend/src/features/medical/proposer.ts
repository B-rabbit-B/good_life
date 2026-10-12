import type { EventOut } from '../../api/types'

/** 最后一条解除建议是谁提出的：助手（agent）或你本人（user）；没有时为 null */
export function proposerOf(events: EventOut[]): 'agent' | 'user' | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i]
    if (event?.action !== 'resolution_proposed') continue
    return event.source === 'agent' || event.source === 'user' ? event.source : null
  }
  return null
}
