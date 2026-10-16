// “我的”页的“单独同意”一组：经期与医嘱两行，写“已同意（日期）”或“未同意”；已同意的一行可以撤回。
// 撤回在确认面板里完成：必须勾选“我知道清除后不能恢复”，确认后后端清除该模块的全部数据并关闭模块；
// 次按钮“继续使用”只关闭面板（规格的“回到使用状态”）。撤回后那一行的按钮不在了，焦点落到这一组上。
// 两行在敏感区 consents 里（小标题在外面）；模块没开放且从没同意过的一行不显示（例如男性用户的经期），
// 同意过的一行一直显示（关了经期记录开关也要能撤回）。
import { useCallback, useId, useRef, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useConsents, useWithdrawConsent } from '../../api/hooks/consents'
import { useCapabilities } from '../../api/hooks/profile'
import type { ConsentOut } from '../../api/types'
import { Button } from '../../components/Button'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { useToast } from '../../components/Toast'
import { useSheetHost } from '../../components/useSheetHost'
import { todayISO } from '../../lib/dates'
import { CONSENT_KIND_LABELS } from '../../lib/labels'
import '../../styles/components/consent.css'
import '../../styles/components/sec-head.css'
import '../../styles/components/settings.css'

export function ConsentRows() {
  const id = useId()
  const consents = useConsents()
  const caps = useCapabilities()
  const rows = consents.data?.filter((consent) => consent.granted || caps.data?.[consent.kind] === true)
  const withdraw = useWithdrawConsent()
  const toast = useToast()
  const section = useRef<HTMLElement>(null)
  const host = useSheetHost<ConsentOut>(useCallback(() => section.current, []))
  const target = host.sheet
  const label = target ? CONSENT_KIND_LABELS[target.kind] : ''
  const [error, setError] = useState<ApiError | null>(null)

  const onConfirm = async () => {
    if (!target) return
    setError(null)
    try {
      await withdraw.mutateAsync(target.kind)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    host.close(host.nonce)
    toast.show('已撤回')
  }

  return (
    <section ref={section} aria-labelledby={id} tabIndex={-1}>
      <div className="sec-h"><h2 className="sec-l" id={id}>单独同意</h2></div>
      <Sensitive area="consents" className="plate">
        {consents.isError && consents.data === undefined && (
          <ErrorState error={asApiError(consents.error)} onRetry={() => void consents.refetch()} />
        )}
        {rows && (
          <ul className="cs-rows" aria-labelledby={id}>
            {rows.map((consent) => (
              <li key={consent.kind} className="cs-row">
                <span>
                  <b>{consent.title}</b>
                  <span className="t-cap">
                    {consent.granted && consent.granted_at ? `已同意（${todayISO(new Date(consent.granted_at))}）` : '未同意'}
                  </span>
                </span>
                {consent.granted && (
                  <Button variant="danger-outline" size="sm" onPress={() => {
                    setError(null)
                    host.show(consent)
                  }}
                  >
                    撤回
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Sensitive>
      <ConfirmSheet
        key={host.nonce}
        isOpen={host.open} onClose={() => host.close(host.nonce)} title={`撤回${target?.title ?? ''}的单独同意`}
        will={[
          { text: `立即清除你的全部${label}数据，${label}功能随即关闭。`, irreversible: true },
          { text: '对话里已有的副本不会随之删除，需要时可在“我的 → 隐私与数据”里清空全部对话历史。' },
          { text: '开场问候记录里可能含相关内容，撤回时同样不会自动删除，可在“隐私与数据”页清空对话历史时一并清掉。' },
          { text: '以后可以重新同意，从空白开始使用。' },
        ]}
        confirmLabel={`撤回并清除${label}数据`} confirmVariant="danger" ack="我知道清除后不能恢复"
        secondary={{ label: '继续使用', onPress: () => host.close(host.nonce) }}
        onConfirm={onConfirm} error={error}
      />
    </section>
  )
}
