import { useId, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useGrants, useRevokeGrant } from '../../api/hooks/grants'
import type { GrantOut } from '../../api/types'
import { Button } from '../../components/Button'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import { Title } from '../../components/Title'
import { formatStamp, todayISO } from '../../lib/dates'
import { ACCESS_LABELS, GRANT_STATUS_LABELS } from '../../lib/settingsLabels'


/**
 * 外部授权（敏感区 grants）：每个授权的名称、权限、状态、到期与最近使用；有效的可以吊销（确认面板里显式按“吊销”）。
 * 轻提示只写“已吊销”，不带授权名称。
 */
export function GrantList() {
  const id = useId()
  const grants = useGrants()
  const revoke = useRevokeGrant()
  const toast = useToast()
  const [target, setTarget] = useState<GrantOut | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const onConfirm = async () => {
    if (!target) return
    setError(null)
    try {
      await revoke.mutateAsync(target.id)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    setOpen(false)
    toast.show('已吊销')
  }

  return (
    <section aria-labelledby={id}>
      <div className="sec-h"><Title k="grants" level="h" id={id} /></div>
      <Sensitive area="grants" className="plate">
        {grants.isError && <p className="pv-empty">{grants.error.message}</p>}
        {grants.data?.length === 0 && <p className="pv-empty">还没有外部授权。</p>}
        {grants.data && grants.data.length > 0 && (
          <ul className="grants" aria-label="外部授权">
            {grants.data.map((grant) => (
              <li key={grant.id} className="grant">
                <b>{grant.name}</b>
                <span className="grant-m">
                  <span>{ACCESS_LABELS[grant.access]}</span>
                  <span>{GRANT_STATUS_LABELS[grant.status]}</span>
                  <span>到期 {todayISO(new Date(grant.expires_at))}</span>
                  <span>{grant.last_used_at ? `最近使用 ${formatStamp(grant.last_used_at)}` : '从未使用'}</span>
                </span>
                {grant.status === 'active' && (
                  <Button variant="danger-outline" size="sm" onPress={() => {
                    setTarget(grant)
                    setError(null)
                    setOpen(true)
                  }}
                  >
                    吊销
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Sensitive>
      <ConfirmSheet
        isOpen={open} onClose={() => setOpen(false)} title="吊销这个授权"
        quote={target ? <Sensitive area="grants"><b>{target.name}</b></Sensitive> : undefined}
        will={[
          { text: '用这个授权的外部客户端立即不能再读写你的数据。' },
          { text: '吊销不能撤销；还要用时，需要重新创建授权。', irreversible: true },
        ]}
        confirmLabel="吊销" confirmVariant="danger" onConfirm={onConfirm} error={error}
      />
    </section>
  )
}
