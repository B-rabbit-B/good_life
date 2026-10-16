// 月历下的“选中日期”面板（在经期页的敏感区里），三种样子：
// 选了开始日、还没选结束日：“经期从 X 开始。再点一个日期作为结束日……”，按钮“还没结束，只记开始”（只带开始日保存）与“取消”；
// 结束日也选好：“X 至 Y，共 N 天”，按钮“保存”与“重新选择”（都清掉选择）；
// 点的是已记录经期里的一天：“这一天在 X 至 Y 的经期内”，按钮“删除这次经期”（确认面板由经期页持有）与“收起”。
// 前两种和第三种都有“只记录这一天的流量、心情、备注”（打开每日记录面板）。
// 保存中面板锁（各按钮停用），单次锁防连按；失败后选择保留，说明与错误码原样显示；轻提示只写“已记下”，不带日期。
import { useState } from 'react'
import { useCreatePeriod } from '../../api/hooks/cycle'
import type { PeriodOut } from '../../api/types'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { addDays, formatFullDate, formatMonthDay } from '../../lib/dates'
import { errorsOf, FORM_ERROR } from '../../lib/formErrors'
import { useSingleFlight } from '../../lib/singleFlight'
import { PeriodAlert } from './PeriodFields'

export type Selection =
  | { kind: 'range'; start: string; end: string | null }
  | { kind: 'inside'; date: string }

function dayCount(start: string, end: string): number {
  let n = 1
  for (let date = start; date < end; date = addDays(date, 1)) n += 1
  return n
}

export function SelectedDay({ selection, period, onReset, onLog, onDelete }: {
  selection: Selection
  /** selection 是 inside 时：包含那一天的经期 */
  period?: PeriodOut
  /** 取消、重新选择、收起与保存成功之后：清掉选择 */
  onReset: () => void
  onLog: (date: string) => void
  onDelete: (period: PeriodOut) => void
}) {
  const create = useCreatePeriod()
  const flight = useSingleFlight()
  const toast = useToast()
  const [pending, setPending] = useState(false)
  // 错误记下是在哪个结束日上失败的：改了结束日就不再显示
  const [failure, setFailure] = useState<{ at: string; error: unknown } | null>(null)
  const at = selection.kind === 'range' ? selection.end ?? '' : ''
  const error = failure?.at === at ? failure.error : null
  const errors = errorsOf(error)
  const message = errors[FORM_ERROR] ?? Object.values(errors)[0]

  const save = (start: string, end: string | null) => {
    flight(() => {
      setPending(true)
      setFailure(null)
      return create.mutateAsync(end ? { start_date: start, end_date: end } : { start_date: start })
    })
      ?.then(() => {
        onReset()
        toast.show('已记下')
      })
      .catch((caught: unknown) => setFailure({ at, error: caught }))
      .finally(() => setPending(false))
  }

  const logButton = (date: string) => (
    <div className="sel-log">
      <Button variant="text" isDisabled={pending} onPress={() => onLog(date)}>只记录这一天的流量、心情、备注</Button>
    </div>
  )

  if (selection.kind === 'inside') {
    return (
      <section className="plate sel-day" aria-label="选中日期">
        {period && (
          <p className="sel-x">
            这一天在 {formatFullDate(period.start_date)} 至 {period.end_date ? formatFullDate(period.end_date) : '今（还没结束）'} 的经期内
          </p>
        )}
        <div className="sel-acts">
          <Button variant="danger-outline" block onPress={() => period && onDelete(period)}>删除这次经期</Button>
          <Button variant="quiet" block onPress={onReset}>收起</Button>
        </div>
        {logButton(selection.date)}
      </section>
    )
  }

  const { start, end } = selection
  return (
    <section className="plate sel-day" aria-label="选中日期">
      <p className="sel-x">
        {end
          ? `${formatMonthDay(start)} 至 ${formatMonthDay(end)}，共 ${dayCount(start, end)} 天`
          : `经期从 ${formatMonthDay(start)} 开始。再点一个日期作为结束日，只能点这天之后的日子。`}
      </p>
      <PeriodAlert message={message} error={error} />
      {end ? (
        <div className="sel-acts two">
          <Button variant="primary" block isPending={pending} onPress={() => save(start, end)}>保存</Button>
          <Button variant="quiet" block isDisabled={pending} onPress={onReset}>重新选择</Button>
        </div>
      ) : (
        <div className="sel-acts">
          <Button variant="quiet" block isPending={pending} onPress={() => save(start, null)}>还没结束，只记开始</Button>
          <Button variant="quiet" block isDisabled={pending} onPress={onReset}>取消</Button>
        </div>
      )}
      {!end && logButton(start)}
    </section>
  )
}
