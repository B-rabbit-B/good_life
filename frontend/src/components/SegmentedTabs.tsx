import type { Key } from 'react-aria-components'
import { Tab, TabList, Tabs } from 'react-aria-components'
import '../styles/components/tabs.css'

export interface TabItem {
  id: string
  label: string
  badge?: number
}

export interface TabsProps {
  items: TabItem[]
  selectedKey: string
  onSelectionChange: (key: string) => void
  ariaLabel: string
}

export function TabStrip({ items, selectedKey, onSelectionChange, ariaLabel, small }: TabsProps & { small: boolean }) {
  return (
    <Tabs selectedKey={selectedKey} onSelectionChange={(key: Key) => onSelectionChange(String(key))}>
      <TabList className={small ? 'ttabs sm' : 'ttabs'} aria-label={ariaLabel}>
        {items.map((item) => (
          <Tab key={item.id} id={item.id} className="ttab">
            {item.label}
            {item.badge !== undefined && <span className="cnt">{item.badge}</span>}
          </Tab>
        ))}
      </TabList>
    </Tabs>
  )
}

/** 一级分段标签：轨道 6% 海军蓝，选中项是抬起的瓷白滑块（React Aria Tabs）。内容区由页面按 selectedKey 渲染。 */
export function SegmentedTabs(props: TabsProps) {
  return <TabStrip {...props} small={false} />
}
