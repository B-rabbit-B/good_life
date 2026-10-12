import { Button as AriaButton, Disclosure, DisclosurePanel } from 'react-aria-components'
import '../styles/components/fold.css'
import { Icon } from './Icon'

/** 依据折叠：默认折叠，标题“依据”旁一枚胶囊写条数；高度用 grid-template-rows 过渡（React Aria Disclosure）。 */
export function EvidenceFold({ lines }: { lines: string[] }) {
  return (
    <Disclosure className="fold-wrap">
      <AriaButton slot="trigger" className="fold">
        <span>依据</span>
        <em>{lines.length}</em>
        <span className="sp" />
        <Icon name="down" size={18} />
      </AriaButton>
      <DisclosurePanel className="fold-b">
        <div>
          <ul className="ev">
            {lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      </DisclosurePanel>
    </Disclosure>
  )
}
