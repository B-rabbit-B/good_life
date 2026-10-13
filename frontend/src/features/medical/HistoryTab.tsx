import { ApiError } from '../../api/errors'
import { useItemEvents, useMedicalItems } from '../../api/hooks/medical'
import { useMedicalEvents } from '../../api/hooks/medicalPage'
import type { EventOut, MedicalItemOut } from '../../api/types'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { Title } from '../../components/Title'
import { todayISO } from '../../lib/dates'
import { CATEGORY_LABELS } from '../../lib/labels'
import { EVENT_SOURCE_LABELS, eventActionLabel } from '../../lib/medicalLabels'
import '../../styles/components/medical-item.css'
import '../../styles/components/medical.css'
import { auditLine } from './auditLine'

const AUDIT_LIMIT = 50
const CLOSED_STATUS = { resolved: '已解除', voided: '已作废' } as const

const isClosing = (item: MedicalItemOut) => (event: Pick<EventOut, 'to_status' | 'from_status'>) =>
  event.to_status === item.status && event.from_status !== item.status

/** 关闭事件的一行：原因原文在前，再写由谁、做了什么（“重复录入，由你本人作废”） */
function closingText(event: Pick<EventOut, 'action' | 'source' | 'detail'>): string {
  const reason = event.detail?.reason
  const who = `由${EVENT_SOURCE_LABELS[event.source]}${eventActionLabel(event.action, event.source)}`
  return typeof reason === 'string' && reason !== '' ? `${reason}，${who}` : who
}

/**
 * 已结束的一条：颜色退一级、竖线变浅，状态写“已解除 日期”或“已作废 日期”（closed_at 的本地日期），
 * 下面一行写最后一个关闭事件的来源与原因：先在审计列表里找，找不到（太早）再取这一条的事件。
 */
function ClosedItem({ item, recent, eventsReady }: {
  item: MedicalItemOut & { status: 'resolved' | 'voided' }
  recent: EventOut | undefined
  eventsReady: boolean
}) {
  const own = useItemEvents(item.id, eventsReady && recent === undefined)
  const event = recent ?? own.data?.filter(isClosing(item)).at(-1)
  return (
    <div className="closed">
      <div className="mo-h">
        <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
        <span className="mo-st">{CLOSED_STATUS[item.status]} {item.closed_at ? todayISO(new Date(item.closed_at)) : ''}</span>
      </div>
      <div className="mo-c">{item.content}</div>
      {event && <span className="t-cap">{closingText(event)}</span>}
    </div>
  )
}

const isClosed = (item: MedicalItemOut): item is MedicalItemOut & { status: 'resolved' | 'voided' } =>
  item.status === 'resolved' || item.status === 'voided'

/**
 * 历史与审计（07e）：已结束的条目（已解除与已作废，只读）与跨条目的审计记录（GET /api/medical/events，新的在前）。
 * 每条审计写时间、动作、条目内容原文、状态变化与来源；系统事件的时间就是检查的时间，不写成零点。
 */
export function HistoryTab() {
  const items = useMedicalItems()
  const events = useMedicalEvents(AUDIT_LIMIT)
  const failed = (items.isError && !items.data) || (events.isError && !events.data)
  if (failed) {
    const caught = items.error ?? events.error
    const error = caught instanceof ApiError ? caught : new ApiError(0, 'unknown_error', String(caught))
    return <div className="plate"><ErrorState error={error} onRetry={() => void Promise.all([items.refetch(), events.refetch()])} /></div>
  }
  if (items.data === undefined) return <LoadingState variant="list" text="正在读取历史与审计" />

  const closed = items.data.filter(isClosed)
    .sort((a, b) => (b.closed_at ?? '').localeCompare(a.closed_at ?? ''))
  const audit = events.data ?? []
  return (
    <Sensitive area="content">
      <div className="sec-h">
        <Title k="ended" level="h" />
        <span className="t-cap">{closed.length} 条</span>
      </div>
      <div className="plate">
        {closed.length === 0 && <p className="mo-empty">还没有已解除或已作废的条目。</p>}
        {closed.map((item) => (
          <ClosedItem
            key={item.id} item={item} eventsReady={events.data !== undefined}
            recent={audit.find((event) => event.item_id === item.id && isClosing(item)(event))}
          />
        ))}
      </div>
      <div className="sec-h">
        <Title k="audit" level="h" />
        <span className="t-cap">最近 {audit.length} 条</span>
      </div>
      <div className="plate">
        {events.data === undefined && <p className="mo-empty">正在读取审计记录</p>}
        {events.data !== undefined && audit.length === 0 && <p className="mo-empty">还没有审计记录。</p>}
        {audit.length > 0 && (
          <ol className="audit">
            {audit.map((event) => {
              const line = auditLine(event)
              const [day, time] = line.time.split(' ')
              return (
                <li key={event.id}>
                  <time dateTime={event.occurred_at}>{day}<br />{time}</time>
                  <span>
                    <b>{line.action}</b> {line.content}
                    <span className="tr">{line.transition}，来源：{line.source}</span>
                  </span>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </Sensitive>
  )
}
