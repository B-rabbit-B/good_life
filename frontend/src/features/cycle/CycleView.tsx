// 经期（设计稿 06）：除两个记录按钮外，全部内容在一块敏感区里。阶段大标题加“仅供参考”、本周期第几天与后端的第一条提示；
// 周期刻度与预测同在一块面板（数据不足或已暂停时换成“数据不足”，正文是后端的说明）；月历；最后是“记录经期开始”
// （最近一次经期还没结束时是“记录经期结束”）与“记录今天”。全页只用海军蓝、灰与钴蓝，文案中性。
// 这个文件连同月历（React Aria Calendar）由健康页按需加载，只在经期这一段出现。
import { networkError } from '../../api/client'
import { ApiError } from '../../api/errors'
import { useCycleStats, usePeriods, usePhase, usePrediction, useTips } from '../../api/hooks/cycle'
import type { CycleStatsOut, PeriodOut, PredictionOut } from '../../api/types'
import { Button } from '../../components/Button'
import { CycleTicks } from '../../components/CycleTicks'
import { RefTag } from '../../components/RefTag'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { InsufficientState } from '../../components/states/InsufficientState'
import { LoadingState } from '../../components/states/LoadingState'
import { Title } from '../../components/Title'
import { formatMonthDay, todayISO } from '../../lib/dates'
import { PHASE_TITLE_KEYS } from '../../lib/cycleLabels'
import '../../styles/components/cycle.css'
import { useSheetHost } from '../medical/useSheetHost'
import { CycleCalendar } from './CycleCalendar'
import { cycleTicksModel, predictedPeriodDays, type CycleTicksModel } from './cyclePanel'
import { DayLogSheet } from './DayLogSheet'
import { PeriodSheet, type PeriodMode } from './PeriodSheet'

type SheetState = { kind: 'period'; mode: PeriodMode; period?: PeriodOut } | { kind: 'day'; date: string }

const ticksLabel = (m: CycleTicksModel) =>
  `周期刻度：共约 ${m.length} 天，第 1 到 ${m.periodDays} 天为经期，今天第 ${m.today} 天，`
  + `下次预计在第 ${m.predicted[0]} 到 ${m.predicted[1]} 天之间开始`

/** “10月28日”的大字：数字用数字字体，“月”“日”小一号 */
function BigDate({ iso }: { iso: string }) {
  const [, m = '', d = ''] = /^(\d+)月(\d+)日$/.exec(formatMonthDay(iso)) ?? []
  return <span className="ns">{m}<small>月</small>{d}<small>日</small></span>
}

function Prediction({ prediction, stats, model }: { prediction: PredictionOut; stats: CycleStatsOut; model: CycleTicksModel | null }) {
  const range = prediction.next_period_range
  return (
    <div className="plate cyc-plate">
      {model && <CycleTicks {...model} label={ticksLabel(model)} />}
      <div className="pred">
        {prediction.next_period_start && <BigDate iso={prediction.next_period_start} />}
        <p>
          预计下次开始。{range && `把握范围 ${formatMonthDay(range.earliest)} 至 ${formatMonthDay(range.latest)}。`}
          <RefTag />
        </p>
        {stats.shortest_cycle !== null && stats.longest_cycle !== null && (
          <p className="pred-x">
            基于最近 {stats.recent_cycle_lengths.length} 个周期，周期长度在 {stats.shortest_cycle} 到 {stats.longest_cycle} 天之间。
          </p>
        )}
        {prediction.notes.map((note) => <p key={note} className="pred-x">{note}</p>)}
        <p className="pred-x">{prediction.disclaimer}</p>
      </div>
    </div>
  )
}

export function CycleView() {
  const today = todayISO()
  const periods = usePeriods()
  const prediction = usePrediction()
  const phase = usePhase()
  const tips = useTips()
  const stats = useCycleStats()
  const host = useSheetHost<SheetState>()
  const queries = [periods, prediction, phase, tips, stats]

  const latest = periods.data?.reduce<PeriodOut | undefined>((a, b) => (!a || b.start_date > a.start_date ? b : a), undefined)
  const periodMode: PeriodMode = latest && latest.end_date === null ? 'end' : 'start'
  const periodLabel = periodMode === 'end' ? '记录经期结束' : '记录经期开始'
  const openPeriod = () => host.show({ kind: 'period', mode: periodMode, period: periodMode === 'end' ? latest : undefined })
  const close = () => host.close(host.nonce)

  let body
  if (periods.data && prediction.data && phase.data && tips.data && stats.data) {
    const p = phase.data
    const tip = tips.data.tips[0]
    const ok = prediction.data.status === 'ok'
    body = (
      <Sensitive area="content">
        <div className="phase">
          <Title k={PHASE_TITLE_KEYS[p.phase]} level="display" as="h2" />
          <RefTag />
          <p>
            {p.cycle_day !== null && `本周期第 ${p.cycle_day} 天。`}
            {tip && <><b className="tip-t">{tip.title}</b><span>{tip.content}</span></>}
          </p>
        </div>
        {ok
          ? <Prediction prediction={prediction.data} stats={stats.data} model={cycleTicksModel(periods.data, prediction.data, p)} />
          : (
            <div className="plate">
              <InsufficientState
                titleKey="cycleInsufficient" notes={prediction.data.notes}
                progressText={`已记录 ${stats.data.cycle_count} 个完整周期`}
                actions={<Button variant="quiet" onPress={openPeriod}>{periodLabel}</Button>}
              />
            </div>
          )}
        <CycleCalendar
          periods={periods.data}
          predictedDays={predictedPeriodDays(prediction.data, stats.data)}
          predictedRange={ok ? prediction.data.next_period_range : null}
          today={today}
          onPick={(date) => host.show({ kind: 'day', date })}
        />
      </Sensitive>
    )
  } else if (queries.some((q) => q.isError && !q.data)) {
    const failed = queries.find((q) => q.isError)?.error
    body = (
      <div className="plate">
        <ErrorState
          error={failed instanceof ApiError ? failed : networkError()}
          onRetry={() => queries.forEach((q) => void q.refetch())}
        />
      </div>
    )
  } else {
    body = <LoadingState variant="page" text="正在读取经期记录" />
  }

  const sheet = host.sheet
  return (
    <>
      {body}
      {periods.data && (
        <div className="pad cyc-acts">
          <Button variant="quiet" onPress={openPeriod}>{periodLabel}</Button>
          <Button variant="primary" onPress={() => host.show({ kind: 'day', date: today })}>记录今天</Button>
        </div>
      )}
      {sheet?.kind === 'period' && (
        <PeriodSheet key={host.nonce} mode={sheet.mode} period={sheet.period} isOpen={host.open} onClose={close} />
      )}
      {sheet?.kind === 'day' && <DayLogSheet key={host.nonce} date={sheet.date} isOpen={host.open} onClose={close} />}
    </>
  )
}

export default CycleView
