// 记录某一天（默认今天，不晚于今天）：流量五档、心情五档、备注（最多 500 字）；PUT 那一天的记录。
// 后端是整条替换：这一天已有记录时先填进表单，这里不编辑的疼痛与症状原样带上，免得被清掉。
// 保存中按钮不能再按，取消与 Esc 都不关面板；失败（含断网）之后恢复可操作、可关闭；说明与错误码原样显示。
// 日期与填写的内容在敏感区里（与医嘱面板一样，按钮在外面）。
import { useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { asApiError } from '../../api/errors'
import { useDayLogs, usePutDayLog } from '../../api/hooks/cycle'
import type { DayLogOut } from '../../api/types'
import { Button } from '../../components/Button'
import { DateField } from '../../components/DateField'
import { Icon } from '../../components/Icon'
import { RadioSegment } from '../../components/RadioSegment'
import { Sensitive } from '../../components/Sensitive'
import { Sheet } from '../../components/Sheet'
import { TextField } from '../../components/TextField'
import { useToast } from '../../components/Toast'
import { MAX_NOTE } from '../../lib/contract'
import { formatMonthDay, todayISO } from '../../lib/dates'
import { FLOW_LABELS, MOOD_LABELS } from '../../lib/cycleLabels'
import type { Flow, Mood } from '../../lib/labels'
import { useSingleFlight } from '../../lib/singleFlight'
import { errorsOf, FORM_ERROR } from '../../lib/formErrors'

// app/cycle/schemas.py 的 DayLogIn.note：最多 500 个字
const FLOW_OPTIONS = (Object.keys(FLOW_LABELS) as Flow[]).map((value) => ({ value, label: FLOW_LABELS[value] }))
const MOOD_OPTIONS = (Object.keys(MOOD_LABELS) as Mood[]).map((value) => ({ value, label: MOOD_LABELS[value] }))

function Alert({ message, code }: { message: string; code?: string }) {
  return (
    <div className="err" role="alert">
      <Icon name="alert" size={18} />
      <span>{message}{code && <small>错误码 {code}</small>}</span>
    </div>
  )
}

function DayLogForm({ date, existing, onClose, onBusyChange }: {
  date: string
  existing: DayLogOut | null
  onClose: () => void
  onBusyChange: (busy: boolean) => void
}) {
  const [flow, setFlow] = useState<string>(existing?.flow ?? '')
  const [mood, setMood] = useState<string>(existing?.mood ?? '')
  const [note, setNote] = useState(existing?.note ?? '')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const put = usePutDayLog()
  const flight = useSingleFlight()
  const toast = useToast()
  const done = useRef(false)
  const errors = errorsOf(error)
  const formError = errors[FORM_ERROR] ?? Object.entries(errors).find(([key]) => key !== 'note')?.[1]

  const save = () => {
    if (done.current) return
    const run = flight(() => {
      setPending(true)
      setError(null)
      onBusyChange(true)
      return put.mutateAsync({
        date,
        body: {
          flow: flow === '' ? null : flow as Flow,
          mood: mood === '' ? null : mood as Mood,
          note: note.trim() === '' ? null : note,
          pain: existing?.pain ?? null,
          symptoms: existing?.symptoms ?? [],
        },
      })
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
        <RadioSegment label="流量" options={FLOW_OPTIONS} value={flow} onChange={setFlow} />
        <RadioSegment label="心情" options={MOOD_OPTIONS} value={mood} onChange={setMood} />
        <TextField label="备注" value={note} onChange={setNote} multiline rows={2} maxLength={MAX_NOTE} error={errors.note} isReadOnly={pending} />
      </Sensitive>
      {formError && <Alert message={formError} code={error instanceof ApiError ? error.code : undefined} />}
      <div className="sheet-foot">
        <Button variant="primary" block isPending={pending} onPress={save}>保存</Button>
        <Button variant="quiet" block isDisabled={pending} onPress={onClose}>取消</Button>
      </div>
    </>
  )
}

function DayLogBody({ initialDate, onClose, onBusyChange }: {
  initialDate: string
  onClose: () => void
  onBusyChange: (busy: boolean) => void
}) {
  const today = todayISO()
  const [date, setDate] = useState(initialDate)
  const [busy, setBusy] = useState(false)
  const logs = useDayLogs(date, date)
  const failed = asApiError(logs.error)
  return (
    <>
      <Sensitive area="content">
        <DateField label="日期" value={date} max={today} readOnly={busy} onChange={(value) => setDate(value ?? today)} />
      </Sensitive>
      {logs.data
        ? (
          <DayLogForm
            key={date} date={date} existing={logs.data.find((log) => log.log_date === date) ?? null} onClose={onClose}
            onBusyChange={(next) => {
              setBusy(next)
              onBusyChange(next)
            }}
          />
        )
        : (
          <>
            {logs.isError
              ? <Alert message={failed.message} code={failed.code} />
              : <p className="t-cap" role="status">正在读取这一天的记录</p>}
            <div className="sheet-foot">
              {logs.isError && <Button variant="primary" block icon="refresh" onPress={() => void logs.refetch()}>重试</Button>}
              <Button variant="quiet" block onPress={onClose}>取消</Button>
            </div>
          </>
        )}
    </>
  )
}

/** date 不给时是今天；面板标题是“记录今天”，其他日子写“记录 10月11日” */
export function DayLogSheet({ date, isOpen, onClose }: { date?: string; isOpen: boolean; onClose: () => void }) {
  const busy = useRef(false)
  const today = todayISO()
  const day = date ?? today
  return (
    <Sheet
      isOpen={isOpen}
      onClose={() => {
        if (!busy.current) onClose()
      }}
      title={day === today ? '记录今天' : `记录 ${formatMonthDay(day)}`}
    >
      <DayLogBody
        initialDate={day} onClose={onClose}
        onBusyChange={(next) => {
          busy.current = next
        }}
      />
    </Sheet>
  )
}
