import { useState } from 'react'
import type { NeedOut } from '../../api/types'
import { Icon } from '../../components/Icon'
import { MAX_NEEDS } from '../../lib/contract'

const FIRST = 4

/**
 * 需求胶囊（多选）：先显示前四个，最后一个胶囊“全部 N 项”展开其余；选满 MAX_NEEDS 个后其余不可选。
 * 选中是钴蓝浅底加勾（aria-pressed）。胶囊 36 高，点按区用伪元素补到 44。
 */
export function NeedChips({ needs, selected, onChange }: {
  needs: NeedOut[]
  selected: string[]
  onChange: (keys: string[]) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const full = selected.length >= MAX_NEEDS
  const shown = expanded ? needs : needs.slice(0, FIRST)
  const toggle = (key: string) => {
    if (selected.includes(key)) onChange(selected.filter((k) => k !== key))
    else if (!full) onChange([...selected, key])
  }
  return (
    <>
      <div className="need" role="group" aria-label="需求">
        {shown.map((need) => {
          const on = selected.includes(need.key)
          return (
            <button
              key={need.key} type="button" aria-pressed={on} disabled={!on && full} data-hit44=""
              title={need.description} onClick={() => toggle(need.key)}
            >
              <span className="box" aria-hidden="true">{on && <Icon name="check" size={18} />}</span>
              {need.name}
            </button>
          )
        })}
        {!expanded && needs.length > FIRST && (
          <button type="button" className="all on-field" aria-expanded={false} data-hit44="" onClick={() => setExpanded(true)}>
            全部 {needs.length} 项
          </button>
        )}
      </div>
      {full && <p className="need-max">最多选 {MAX_NEEDS} 项</p>}
    </>
  )
}
