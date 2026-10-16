// 记录经期开始时两处共用的小零件（记录经期开始的面板、月历下的“选中日期”面板）：可留空的结束日期，
// 补记以前的经期要一起填（开始日比今天早 MAX_PERIOD_DAYS 天及以上又没填结束日期时只给一行提示，不拦截）；
// 以及后端错误的原样显示（说明加错误码）。日期是否合理仍由后端判断。
import { ApiError } from '../../api/errors'
import { DateField } from '../../components/DateField'
import { Icon } from '../../components/Icon'
import { MAX_PERIOD_DAYS } from '../../lib/contract'
import { addDays } from '../../lib/dates'

export function EndDateField({ start, end, today, readOnly, error, onChange }: {
  start: string
  end: string | null
  today: string
  readOnly: boolean
  error?: string
  onChange: (value: string | null) => void
}) {
  const pastWithoutEnd = end === null && start <= addDays(today, -MAX_PERIOD_DAYS)
  return (
    <>
      <DateField
        label="结束日期（还没结束可以留空）" value={end} min={start} max={today} readOnly={readOnly} error={error}
        onChange={onChange}
      />
      {pastWithoutEnd && <span className="fld-h">补记以前的经期，请同时填写结束日期</span>}
    </>
  )
}

export function PeriodAlert({ message, error }: { message: string | undefined; error: unknown }) {
  if (!message) return null
  return (
    <div className="err" role="alert">
      <Icon name="alert" size={18} />
      <span>{message}{error instanceof ApiError && <small>错误码 {error.code}</small>}</span>
    </div>
  )
}
