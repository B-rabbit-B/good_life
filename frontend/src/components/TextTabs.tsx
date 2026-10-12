import { TabStrip, type TabsProps } from './SegmentedTabs'

/** 二级文字标签：选中项下方一枚 18 × 3 的钴蓝胶囊（.ttabs.sm）。 */
export function TextTabs(props: TabsProps) {
  return <TabStrip {...props} small />
}
