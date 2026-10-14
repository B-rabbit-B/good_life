// 模型服务（设计稿 10a 上半）：服务列表（名称、完整地址、密钥掩码、测试连通、删除）、当前用途、“添加模型服务”、
// “其他设置”三行链接（隐私与数据、已保存的大致区域（区域名在敏感区里）、免责声明）。
import { Link } from 'react-router'
import { asApiError } from '../../api/errors'
import { useAssignments, useProviders } from '../../api/hooks/llmSettings'
import { useCapabilities } from '../../api/hooks/profile'
import { useRestaurantSettings } from '../../api/hooks/restaurants'
import type { AssignmentOut, ProviderOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { PATHS } from '../../app/paths'
import { ButtonLink } from '../../components/ButtonLink'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { Title } from '../../components/Title'
import { useToast } from '../../components/Toast'
import { useSheetHost } from '../../components/useSheetHost'
import type { Purpose } from '../../lib/labels'
import { PURPOSE_LABELS } from '../../lib/settingsLabels'
import '../../styles/components/me.css'
import '../../styles/components/sec-head.css'
import '../../styles/components/settings.css'
import { DeleteProviderSheet } from './DeleteProviderSheet'
import { ProviderRow } from './ProviderRow'

const PURPOSES: Purpose[] = ['chat', 'vision']

/** 测试连通用的模型：先用分配给这个服务的对话模型，再用看图模型；都没有时只测列模型 */
function assignedModel(provider: ProviderOut, assignments: AssignmentOut[]): string | undefined {
  for (const purpose of PURPOSES) {
    const item = assignments.find((a) => a.purpose === purpose && a.model.provider_id === provider.id)
    if (item) return item.model.model_id
  }
  return undefined
}

function Uses({ assignments }: { assignments: AssignmentOut[] }) {
  return (
    <ul className="plate uses" aria-label="当前用途">
      {PURPOSES.map((purpose) => {
        const item = assignments.find((a) => a.purpose === purpose)
        return (
          <li key={purpose}>
            <span>{PURPOSE_LABELS[purpose]}</span>
            <span>{item ? `${item.model.model_id}（${item.provider_name}）` : '未设置'}</span>
          </li>
        )
      })}
    </ul>
  )
}

function OtherSettings() {
  const caps = useCapabilities()
  const settings = useRestaurantSettings(caps.data?.nutrition === true)
  const area = settings.data?.area?.name
  return (
    <>
      <div className="sec-h"><Title k="otherSettings" level="h" /></div>
      <div className="plate set-links">
        <Link className="lnk" to={PATHS.privacy}>隐私与数据<Icon name="right" /></Link>
        <Link className="lnk" to={PATHS.privacy}>
          已保存的大致区域
          <Sensitive as="span" area="savedArea" className="v">{area ?? (settings.data ? '未保存' : '')}</Sensitive>
          <Icon name="right" />
        </Link>
        <Link className="lnk" to={PATHS.disclaimerView}>免责声明<Icon name="right" /></Link>
      </div>
    </>
  )
}

// 删除服务后那一行（连同触发的按钮）不在了：焦点落到“添加模型服务”上
const addProviderLink = () => document.querySelector<HTMLElement>('.add-prov a')

export default function ModelsPage() {
  useSensitivePage('models')
  const providers = useProviders()
  const assignments = useAssignments()
  const toast = useToast()
  const host = useSheetHost<ProviderOut>(addProviderLink)
  const failed = providers.error ?? assignments.error
  const error = failed === null ? null : asApiError(failed)
  return (
    <>
      <PageHeader titleKey="models" variant="sub" back={PATHS.me} />
      {error && (
        <ErrorState error={error} onRetry={() => void Promise.all([providers.refetch(), assignments.refetch()])} />
      )}
      {!error && (!providers.data || !assignments.data) && <LoadingState variant="list" text="正在读取模型服务" />}
      {providers.data && assignments.data && (
        <>
          {providers.data.length > 0
            ? (
              <ul className="plate provs" aria-label="模型服务">
                {providers.data.map((p) => (
                  <ProviderRow key={p.id} provider={p} modelId={assignedModel(p, assignments.data)} onDelete={host.show} />
                ))}
              </ul>
            )
            : <p className="pv-note">还没有模型服务。添加一个，填地址与密钥即可。</p>}
          <div className="pad add-prov">
            <ButtonLink to={PATHS.modelNew} variant="quiet" block>
              <Icon name="plus" size={18} />
              添加模型服务
            </ButtonLink>
          </div>
          <div className="sec-h"><h2 className="sec-l">当前用途</h2></div>
          <Uses assignments={assignments.data} />
        </>
      )}
      <OtherSettings />
      <DeleteProviderSheet
        key={host.nonce} provider={host.sheet} isOpen={host.open} onClose={() => host.close(host.nonce)}
        onDeleted={() => {
          host.close(host.nonce)
          toast.show('已删除')
        }}
      />
    </>
  )
}
