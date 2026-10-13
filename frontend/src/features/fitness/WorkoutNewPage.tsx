// 记一次训练（线框，DESIGN.md 第十三节）：顶部的运动限制（医嘱内容，在敏感区里）；胶囊搜索框（后端的提示原文照写），
// 结果是账目行（动作名、部位、器械）；点一个结果加一个动作：力量动作逐组填重量与次数（可加组、删组），有氧填时长与距离；
// 可以再搜再加；训练日期（默认今天，不晚于今天）与整次时长；操作坞“保存”。成功后回训练记录并轻提示“已记下”，
// 后端返回的冲突说明原样写在轻提示里（遮盖时不写内容）。数字填的不是数字时原样发出，由后端给出说明，写在对应的格子下面。
import { useEffect, useId, useRef, useState } from 'react'
import { Button as AriaButton, Input, Text, TextField as AriaTextField } from 'react-aria-components'
import { useNavigate } from 'react-router'
import { ApiError } from '../../api/errors'
import { useCreateWorkout, useExerciseSearch, type WorkoutInput } from '../../api/hooks/fitness'
import type { ConflictOut, ExerciseSummaryOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { useCover } from '../../components/cover'
import { DateField } from '../../components/DateField'
import { Dock } from '../../components/Dock'
import { Icon } from '../../components/Icon'
import { IconButton } from '../../components/IconButton'
import { PageHeader } from '../../components/PageHeader'
import { TextField } from '../../components/TextField'
import { useToast } from '../../components/Toast'
import { todayISO } from '../../lib/dates'
import { EQUIPMENT_LABELS, MUSCLE_LABELS } from '../../lib/fitnessLabels'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/field-input.css'
import '../../styles/components/training.css'
import { LimitStrip } from './LimitStrip'

const SEARCH_DELAY_MS = 250
const FIELD = /^(strength|cardio)\.(\d+)\.(.+)$/

interface SetDraft { weight: string; reps: string }
interface Entry { key: number; exercise: ExerciseSummaryOut; sets: SetDraft[]; minutes: string; km: string }
type Errors = Record<string, string>
interface Failure { byEntry: Record<number, Errors>; top: Errors; form: string[]; code: string | null }

/** 填的数字：有限的数字发数字，否则原样发出，让后端给出说明 */
const numberOrText = (text: string) => {
  const trimmed = text.trim()
  const value = Number(trimmed)
  return trimmed !== '' && Number.isFinite(value) ? value : trimmed
}
const optional = (text: string) => (text.trim() === '' ? null : numberOrText(text))

/** 输入停下 250 毫秒后才搜索 */
function useDebounced(value: string): string {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [value])
  return settled
}

/** 后端的错误归到动作与格子上（字段路径如 strength.0.sets.1.reps）；归不上的写在表单上 */
function toFailure(error: unknown, strength: Entry[], cardio: Entry[]): Failure {
  const failure: Failure = { byEntry: {}, top: {}, form: [], code: null }
  if (!(error instanceof ApiError)) return { ...failure, form: ['出了点问题，请稍后再试'] }
  failure.code = error.code
  if (error.code !== 'validation_error' || !error.details?.length) return { ...failure, form: [error.message] }
  for (const { field, message } of error.details) {
    const match = FIELD.exec(field)
    const entry = match ? (match[1] === 'strength' ? strength : cardio)[Number(match[2])] : undefined
    if (entry && match?.[3]) (failure.byEntry[entry.key] ??= {})[match[3]] ??= message
    else if (field === 'performed_on' || field === 'duration_minutes') failure.top[field] ??= message
    else failure.form.push(message)
  }
  return failure
}

/** 组里的一个数字格：读屏名称是“第 N 组重量”，框内右侧写单位；后端的说明写在框下 */
function SetInput({ label, value, onChange, suffix, error }: {
  label: string; value: string; onChange: (value: string) => void; suffix: string; error?: string
}) {
  return (
    <AriaTextField className="wn-num" aria-label={label} value={value} onChange={onChange} isInvalid={Boolean(error)} inputMode="decimal">
      <span className={error ? 'fld-i bad' : 'fld-i'}>
        <Input className="n" />
        <span className="t-cap fld-suf" aria-hidden="true">{suffix}</span>
      </span>
      {error && <Text slot="errorMessage" className="err"><span>{error}</span></Text>}
    </AriaTextField>
  )
}

function EntryHeader({ id, entry, onRemove, errors }: { id: string; entry: Entry; onRemove: () => void; errors: Errors }) {
  const { exercise } = entry
  const shown = new Set(['duration_minutes', 'distance_km'])
  const other = Object.entries(errors).filter(([key]) => !shown.has(key) && !key.startsWith('sets.')).map(([, m]) => m)
  return (
    <>
      <div className="wn-ex-h">
        <div>
          <h2 id={id}>{exercise.name}</h2>
          <span className="t-cap">{exercise.primary_muscles.map((m) => MUSCLE_LABELS[m]).join('、')} · {EQUIPMENT_LABELS[exercise.equipment]}</span>
        </div>
        <Button variant="text" onPress={onRemove}>移除这个动作</Button>
      </div>
      {other.map((message) => <div key={message} className="err"><Icon name="alert" size={18} /><span>{message}</span></div>)}
    </>
  )
}

function EntryPanel({ entry, errors, onChange, onRemove }: {
  entry: Entry; errors: Errors; onChange: (next: Entry) => void; onRemove: () => void
}) {
  const id = useId()
  const setAt = (i: number, patch: Partial<SetDraft>) =>
    onChange({ ...entry, sets: entry.sets.map((s, j) => (j === i ? { ...s, ...patch } : s)) })
  return (
    <section className="plate wn-ex" role="group" aria-labelledby={id}>
      <EntryHeader id={id} entry={entry} onRemove={onRemove} errors={errors} />
      {entry.exercise.kind === 'strength'
        ? (
          <>
            {entry.sets.map((set, i) => (
              // 组只会在末尾增加、按位置删除，用位置当键
              <div key={i} className="wn-set">
                <span className="wn-set-n">第 {i + 1} 组</span>
                <SetInput label={`第 ${i + 1} 组重量`} value={set.weight} suffix="千克" error={errors[`sets.${i}.weight_kg`]} onChange={(weight) => setAt(i, { weight })} />
                <SetInput label={`第 ${i + 1} 组次数`} value={set.reps} suffix="次" error={errors[`sets.${i}.reps`]} onChange={(reps) => setAt(i, { reps })} />
                {entry.sets.length > 1
                  ? <IconButton icon="x" label={`删去第 ${i + 1} 组`} onPress={() => onChange({ ...entry, sets: entry.sets.filter((_, j) => j !== i) })} />
                  : <span />}
              </div>
            ))}
            <Button
              variant="text" icon="plus"
              onPress={() => onChange({ ...entry, sets: [...entry.sets, { ...(entry.sets.at(-1) ?? { weight: '', reps: '' }) }] })}
            >
              加一组
            </Button>
          </>
        )
        : (
          <div className="wn-pair">
            <TextField label="时长" value={entry.minutes} onChange={(minutes) => onChange({ ...entry, minutes })} inputMode="numeric" suffix="分钟" error={errors.duration_minutes} />
            <TextField label="距离（可不填）" value={entry.km} onChange={(km) => onChange({ ...entry, km })} inputMode="decimal" suffix="千米" error={errors.distance_km} />
          </div>
        )}
    </section>
  )
}

function conflictToast(conflicts: ConflictOut[], covered: boolean): string {
  if (conflicts.length === 0) return '已记下'
  if (covered) return '已记下。有一条提示，取消遮盖后可在训练记录里查看。'
  return `已记下。${conflicts.map((c) => c.message).join(' ')}`
}

export default function WorkoutNewPage() {
  useSensitivePage('workoutNew')
  const navigate = useNavigate()
  const toast = useToast()
  const { covered } = useCover()
  const today = todayISO()
  const [text, setText] = useState('')
  const q = useDebounced(text.trim())
  const search = useExerciseSearch(q)
  const [entries, setEntries] = useState<Entry[]>([])
  const nextKey = useRef(0)
  const [date, setDate] = useState(today)
  const [duration, setDuration] = useState('')
  const [failure, setFailure] = useState<Failure | null>(null)
  const create = useCreateWorkout()
  // 双击“保存”时 isPending 还没渲染出来：用锁保证只记一次
  const flight = useSingleFlight()
  const saved = useRef(false)

  const pick = (exercise: ExerciseSummaryOut) => {
    nextKey.current += 1
    setEntries((list) => [...list, { key: nextKey.current, exercise, sets: [{ weight: '', reps: '' }], minutes: '', km: '' }])
    setText('')
  }

  const save = () => {
    if (entries.length === 0 || saved.current) return
    const strength = entries.filter((e) => e.exercise.kind === 'strength')
    const cardio = entries.filter((e) => e.exercise.kind === 'cardio')
    const body: WorkoutInput = {
      performed_on: date,
      duration_minutes: optional(duration),
      strength: strength.map((e) => ({
        exercise_id: e.exercise.id, sets: e.sets.map((s) => ({ weight_kg: numberOrText(s.weight), reps: numberOrText(s.reps) })),
      })),
      cardio: cardio.map((e) => ({ exercise_id: e.exercise.id, duration_minutes: numberOrText(e.minutes), distance_km: optional(e.km) })),
    }
    const run = flight(() => {
      setFailure(null)
      return create.mutateAsync(body)
    })
    run?.then((workout) => {
      saved.current = true
      toast.show(conflictToast(workout.conflicts, covered))
      void navigate(`${PATHS.records}?tab=training`)
    }, (caught: unknown) => setFailure(toFailure(caught, strength, cardio)))
  }

  // 选中一个动作后搜索框清空：清空的那一刻就收起上一次的结果（不等防抖），免得再点到旧的结果
  const searching = text.trim() !== ''
  const results = searching ? search.data?.results ?? [] : []
  return (
    <>
      <PageHeader titleKey="workoutNew" variant="sub" back />
      <LimitStrip />
      <div className="plate wn-q">
        <AriaTextField aria-label="搜索动作" type="search" value={text} onChange={setText} maxLength={50}>
          <span className="wn-srch">
            <Icon name="search" size={18} />
            <Input placeholder="搜索动作，比如 深蹲、卧推" />
          </span>
        </AriaTextField>
        {searching && search.data?.message && <p className="wn-msg">{search.data.message}</p>}
        {searching && search.isError && <p className="wn-msg">{search.error.message}</p>}
        {results.length > 0 && (
          <ul className="wn-res" aria-label="搜索结果">
            {results.map((result) => (
              <li key={result.id}>
                <AriaButton className="wn-row" onPress={() => pick(result)}>
                  <span>{result.name}</span>
                  <span className="t-cap">
                    {result.primary_muscles.map((m) => MUSCLE_LABELS[m]).join('、')} · {EQUIPMENT_LABELS[result.equipment]}
                  </span>
                </AriaButton>
              </li>
            ))}
          </ul>
        )}
      </div>
      {entries.map((entry) => (
        <EntryPanel
          key={entry.key} entry={entry} errors={failure?.byEntry[entry.key] ?? {}}
          onChange={(next) => setEntries((list) => list.map((e) => (e.key === next.key ? next : e)))}
          onRemove={() => setEntries((list) => list.filter((e) => e.key !== entry.key))}
        />
      ))}
      <section className="plate wn-when" aria-label="训练时间">
        <div className="wn-pair">
          <DateField label="训练日期" value={date} max={today} error={failure?.top.performed_on} onChange={(value) => setDate(value ?? today)} />
          <TextField label="整次时长（可不填）" value={duration} onChange={setDuration} inputMode="numeric" suffix="分钟" error={failure?.top.duration_minutes} />
        </div>
        {failure && failure.form.length > 0 && (
          <div className="err" role="alert">
            <Icon name="alert" size={18} />
            <span>
              {failure.form.map((message) => <span key={message} className="form-err-line">{message}</span>)}
              {failure.code && <small>错误码 {failure.code}</small>}
            </span>
          </div>
        )}
      </section>
      <Dock>
        <Button variant="primary" block isDisabled={entries.length === 0} isPending={create.isPending} onPress={save}>保存</Button>
      </Dock>
    </>
  )
}
