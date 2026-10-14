// 隐私与数据（线框）：遮盖说明、“减少透明”（跟随系统 / 开 / 关）、已保存的大致区域（可清除）、外部授权（可吊销）、调用记录，
// 以及数据可控的三块：导出我的数据、清空对话历史、删除账号与全部数据（黑体 sec-l 小标题）。
// 区域、授权与调用记录都在敏感区里；数据可控三块不含内容，但本页是登记过的敏感页，它们也各自包在敏感区里。
import { useCapabilities } from '../../api/hooks/profile'
import { useSensitivePage } from '../../app/AppShell'
import { PATHS } from '../../app/paths'
import { PageHeader } from '../../components/PageHeader'
import '../../styles/components/field-input.css'
import '../../styles/components/sec-head.css'
import '../../styles/components/settings.css'
import { AuditList } from './AuditList'
import { ClearConversations } from './ClearConversations'
import { DeleteAccount } from './DeleteAccount'
import { ExportData } from './ExportData'
import { GlassPreference } from './GlassPreference'
import { GrantList } from './GrantList'
import { SavedArea } from './SavedArea'

export default function PrivacyPage() {
  useSensitivePage('privacy')
  const caps = useCapabilities()
  return (
    <>
      <PageHeader titleKey="privacy" variant="sub" back={PATHS.me} />
      <p className="pv-note">打开后医嘱、经期、档案等内容用斜纹盖住；应用切到后台再回来时自动遮盖。</p>
      <div className="plate pv-glass">
        <GlassPreference />
      </div>
      <SavedArea enabled={caps.data?.nutrition === true} />
      <GrantList />
      <AuditList />
      <ExportData />
      <ClearConversations />
      <DeleteAccount />
    </>
  )
}
