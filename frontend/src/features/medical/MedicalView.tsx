import { Link } from 'react-router'
import { useMedicalItems } from '../../api/hooks/medical'
import { PATHS } from '../../app/paths'
import { buttonClassName } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { TextTabs } from '../../components/TextTabs'
import '../../styles/components/medical.css'
import { useQueryParams } from '../../lib/queryParams'
import { ActiveTab } from './ActiveTab'
import { HistoryTab } from './HistoryTab'
import { PendingTab } from './PendingTab'

export type MedicalTab = 'pending' | 'active' | 'history'
const TABS: readonly MedicalTab[] = ['pending', 'active', 'history']

/** 当前子标签（?tab=pending|active|history，默认“生效中”）与切换（写回地址栏） */
export function useMedicalTab(): [MedicalTab, (tab: MedicalTab) => void] {
  const [params, setParams] = useQueryParams()
  const requested = params.get('tab')
  const tab = TABS.find((key) => key === requested) ?? 'active'
  return [tab, (next) => setParams({ tab: next })]
}

/**
 * 医嘱的三个子标签（文字标签，选中项下一枚 18 × 3 的钴蓝胶囊）：“待核对 N”（有待核对时是赭色计数）、“生效中 N”、
 * “历史与审计”。放在健康页的页头里，与 ?tab= 同步。
 */
export function MedicalTabs() {
  const [tab, setTab] = useMedicalTab()
  const items = useMedicalItems()
  const list = items.data
  const pending = list?.filter((item) => item.status === 'pending_confirmation').length ?? 0
  const active = list?.filter((item) => item.status === 'active' || item.status === 'pending_review').length
  return (
    <TextTabs
      items={[
        { id: 'pending', label: '待核对', badge: pending > 0 ? pending : undefined },
        { id: 'active', label: active === undefined ? '生效中' : `生效中 ${active}` },
        { id: 'history', label: '历史与审计' },
      ]}
      selectedKey={tab}
      onSelectionChange={(key) => setTab(key as MedicalTab)}
      ariaLabel="医嘱分类"
    />
  )
}

/**
 * 医嘱（07a、07b、07e）：按子标签显示待核对、生效中或历史与审计，内容全部在敏感区里；
 * 下面是背景场上的“录入医嘱”（钴蓝文字按钮垫 72% 白）。确认生效与确认解除只在这里的底部面板里完成。
 */
export function MedicalView() {
  const [tab] = useMedicalTab()
  return (
    <>
      {tab === 'pending' && <PendingTab />}
      {tab === 'active' && <ActiveTab />}
      {tab === 'history' && <HistoryTab />}
      <div className="pad mo-entry">
        <Link to={PATHS.medicalNew} className={buttonClassName({ variant: 'text', onField: true })}>
          <Icon name="plus" size={18} />录入医嘱
        </Link>
      </div>
    </>
  )
}
