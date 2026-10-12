import '../styles/components/slip.css'
import { Icon } from './Icon'
import { Surface } from './Surface'

/** 系统附注：独立于回答气泡的静玻璃便笺，打孔上沿、朱色标题、右上“系统附注”胶囊；材质与位置都和模型的话分开。 */
export function SystemSlip({ title, lines }: { title: string; lines: string[] }) {
  return (
    <Surface tier="still" className="slip" role="note" aria-label="系统附上的医嘱提醒">
      <div className="slip-h">
        <b><Icon name="doc" size={18} />{title}</b>
        <small>系统附注</small>
      </div>
      {lines.map((line) => <p key={line}>{line}</p>)}
    </Surface>
  )
}
