import '../styles/components/will.css'

export interface WillItem {
  text: string
  irreversible?: boolean
}

/** “确认后会发生”清单：逐条写清后果，不可撤销的一项朱色。 */
export function WillList({ items }: { items: WillItem[] }) {
  return (
    <ul className="will">
      {items.map((item) => <li key={item.text} className={item.irreversible ? 'irrev' : undefined}>{item.text}</li>)}
    </ul>
  )
}
