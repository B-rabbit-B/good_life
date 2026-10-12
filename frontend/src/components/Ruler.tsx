import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { Button as AriaButton, Input, NumberField } from 'react-aria-components'
import '../styles/components/field-input.css'
import '../styles/components/ruler.css'
import { rulerMarks } from './rulerMarks'

export interface RulerProps {
  label: string
  unit: string
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step: number
  /** 大刻度与标签的间隔 */
  major: number
  /** 每单位多少像素 */
  ppu: number
  hint?: string
}

const decimalsOf = (step: number) => (String(step).split('.')[1] ?? '').length

/**
 * 刻度尺选择器：指针固定在中线，拖动刻度改值并吸附到小刻度；方向键按 step、翻页键按大刻度改值；
 * 点数字直接输入（React Aria NumberField，弹出数字键盘）。滑块语义照设计稿手写在刻度尺上
 * （role="slider"，aria-valuetext 带单位），因为 React Aria Slider 的轨道把指针位置映射成绝对值，与“移动刻度”相反。
 * 容器尺寸变化用 ResizeObserver 重算，没有时监听 resize。
 */
export function Ruler({ label, unit, value, onChange, min, max, step, major, ppu, hint }: RulerProps) {
  const labelId = useId()
  const hintId = useId()
  const rulerRef = useRef<HTMLDivElement>(null)
  const numberRef = useRef<HTMLButtonElement>(null)
  const dragRef = useRef<{ pointerId: number; startX: number; startValue: number } | null>(null)
  const closedRef = useRef(false)
  const [width, setWidth] = useState(0)
  const [editing, setEditing] = useState(false)

  const decimals = decimalsOf(step)
  const text = String(Number(value.toFixed(decimals)))
  const normalize = (v: number) => Number((Math.min(max, Math.max(min, Math.round(v / step) * step))).toFixed(decimals))
  const commit = (v: number) => {
    const next = normalize(v)
    if (next !== value) onChange(next)
  }

  useEffect(() => {
    const el = rulerRef.current
    if (!el) return undefined
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => setWidth(el.clientWidth))
      observer.observe(el)
      return () => observer.disconnect()
    }
    const update = () => setWidth(el.clientWidth)
    const frame = requestAnimationFrame(update)
    window.addEventListener('resize', update)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', update)
    }
  }, [])

  // 用键盘（回车或 Esc）结束输入后把焦点还给数字；点别处结束时焦点留在用户点的地方
  useEffect(() => {
    if (!editing && closedRef.current) {
      closedRef.current = false
      numberRef.current?.focus()
    }
  }, [editing])

  const close = (byKeyboard: boolean) => {
    closedRef.current = byKeyboard
    setEditing(false)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = {
      ArrowRight: value + step, ArrowUp: value + step, ArrowLeft: value - step, ArrowDown: value - step,
      PageUp: value + major, PageDown: value - major, Home: min, End: max,
    }
    const next = moves[event.key]
    if (next === undefined) return
    event.preventDefault()
    commit(next)
  }

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    dragRef.current = { pointerId: event.pointerId, startX: event.clientX, startValue: value }
  }
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    // 刻度跟着手指走：向左拖，指针下的数变大
    commit(drag.startValue - (event.clientX - drag.startX) / ppu)
  }
  const endDrag = () => {
    dragRef.current = null
  }

  const { ticks, labels } = rulerMarks(width, value, step, major, ppu)

  return (
    <div className="picker">
      <div className="picker-top">
        <span className="fld-l" id={labelId}>{label}</span>
        {editing ? (
          <NumberField
            className="picker-edit" aria-label={label} defaultValue={value} minValue={min} maxValue={max} step={step}
            onChange={(v) => {
              if (!Number.isNaN(v)) commit(v)
            }}
          >
            {/* 回车在抬起时才收起：按下时 React Aria 已经提交；若在按下时收起，同一次回车会落到数字按钮上又把它打开 */}
            <Input
              inputMode="decimal" autoFocus onBlur={() => close(false)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') close(true)
              }}
              onKeyUp={(event) => {
                if (event.key === 'Enter') close(true)
              }}
            />
            <span>{unit}</span>
          </NumberField>
        ) : (
          <AriaButton
            ref={numberRef} className="picker-val" aria-label={`${label} ${text} ${unit}，点按直接输入`}
            onPress={() => setEditing(true)}
          >
            <span className="n ns">{text}</span>
            <span>{unit}</span>
          </AriaButton>
        )}
      </div>
      <div
        ref={rulerRef} className="ruler" role="slider" tabIndex={0}
        aria-labelledby={labelId} aria-describedby={hint ? hintId : undefined}
        aria-orientation="horizontal" aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}
        aria-valuetext={`${text} ${unit}`}
        onKeyDown={onKeyDown} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
        onPointerUp={endDrag} onPointerCancel={endDrag}
      >
        {ticks.map((tick, i) => <i key={i} className={tick.major ? 'mj' : undefined} style={{ left: tick.x }} />)}
        {labels.map((l) => <span key={l.value} style={{ left: l.x }}>{l.value}</span>)}
        <b className="needle" />
      </div>
      {hint && <span className="fld-h" id={hintId}>{hint}</span>}
    </div>
  )
}
