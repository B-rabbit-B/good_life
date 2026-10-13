// 记录经期开始或结束：只问一个日期（默认今天，不晚于今天）。开始是 POST，结束是给最近一次经期 PATCH 结束日期；
// 日期是否合理（重叠、太长、早于开始日）都由后端判断，说明与错误码原样显示。
// 保存中按钮不能再按，取消与 Esc 都不关面板；失败（含断网）之后恢复可操作、可关闭。日期在敏感区里，按钮在外面。
import { useRef, useState } from 'react'
import { ApiError } from '../../api/errors'
import { useCreatePeriod, useUpdatePeriod } from '../../api/hooks/cycle'
import type { PeriodOut } from '../../api/types'
import { Button } from '../../components/Button'
import { DateField } from '../../components/DateField'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { Sheet } from '../../components/Sheet'
import { useToast } from '../../components/Toast'
import { todayISO } from '../../lib/dates'
import { useSingleFlight } from '../../lib/singleFlight'
import { errorsOf, FORM_ERROR } from '../onboarding/fieldErrors'

export type PeriodMode = 'start' | 'end'

const TITLES: Record<PeriodMode, string> = { start: '记录经期开始', end: '记录经期结束' }

function PeriodBody({ mode, period, onClose, onBusyChange }: {
  mode: PeriodMode
  period?: PeriodOut
  onClose: () => void
  onBusyChange: (busy: boolean) => void
}) {
  const today = todayISO()
  const [date, setDate] = useState(today)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const create = useCreatePeriod()
  const update = useUpdatePeriod()
  const flight = useSingleFlight()
  const toast = useToast()
  const done = useRef(false) // 记下之后、面板关上之前不再提交
  const errors = errorsOf(error)
  const fieldError = errors.start_date ?? errors.end_date
  const formError = errors[FORM_ERROR] ?? (fieldError ? undefined : Object.values(errors)[0])

  const save = () => {
    if (done.current) return
    const run = flight(() => {
      setPending(true)
      setError(null)
      onBusyChange(true)
      if (mode === 'end' && period) return update.mutateAsync({ id: period.id, end_date: date })
      return create.mutateAsync({ start_date: date })
    })
    run?.then(() => {
      done.current = true
      onClose()
      toast.show('已记下')
    })
      .catch((caught: unknown) => setError(caught))
      .finally(() => {
        setPending(false)
        onBusyChange(false)
      })
  }

  return (
    <>
      <Sensitive area="content">
        <DateField
          label={mode === 'start' ? '开始日期' : '结束日期'} value={date} max={today} readOnly={pending} error={fieldError}
          onChange={(value) => setDate(value ?? today)}
        />
      </Sensitive>
      {formError && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span>{formError}{error instanceof ApiError && <small>错误码 {error.code}</small>}</span>
        </div>
      )}
      <div className="sheet-foot">
        <Button variant="primary" block isPending={pending} onPress={save}>保存</Button>
        <Button variant="quiet" block isDisabled={pending} onPress={onClose}>取消</Button>
      </div>
    </>
  )
}

/** mode 为 end 时 period 是要结束的那一次（最近一次、还没有结束日期） */
export function PeriodSheet({ mode, period, isOpen, onClose }: {
  mode: PeriodMode
  period?: PeriodOut
  isOpen: boolean
  onClose: () => void
}) {
  const busy = useRef(false)
  return (
    <Sheet
      isOpen={isOpen}
      onClose={() => {
        if (!busy.current) onClose()
      }}
      title={TITLES[mode]}
    >
      <PeriodBody
        mode={mode} period={period} onClose={onClose}
        onBusyChange={(next) => {
          busy.current = next
        }}
      />
    </Sheet>
  )
}
