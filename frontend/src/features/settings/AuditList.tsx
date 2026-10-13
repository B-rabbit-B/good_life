import { useId, useState } from 'react'
import { useAudits } from '../../api/hooks/grants'
import type { AuditOut } from '../../api/types'
import { Sensitive } from '../../components/Sensitive'
import { Title } from '../../components/Title'
import { formatStamp } from '../../lib/dates'
import type { AuditOutcome } from '../../lib/labels'
import { AUDIT_OUTCOME_LABELS, clientLabel } from '../../lib/settingsLabels'

function AuditRows({ rows }: { rows: AuditOut[] }) {
  return (
    <ul className="audits" aria-label="调用记录">
      {rows.map((row) => (
        <li key={row.id} className="audit-row">
          <time dateTime={row.created_at}>{formatStamp(row.created_at)}</time>
          <span>
            <b>{clientLabel(row.client_name)}</b> {row.capability}
            <br />
            <span className={row.outcome === 'ok' ? undefined : 'bad'}>
              {AUDIT_OUTCOME_LABELS[row.outcome as AuditOutcome] ?? row.outcome}
            </span>
            {row.error_code && <>，{row.error_code}</>}
            ，{row.duration_ms} 毫秒
          </span>
        </li>
      ))}
    </ul>
  )
}

/**
 * 调用记录（敏感区 audit）：筛选胶囊“全部”加最近 200 条里出现过的客户端名（应用内助手写中文名）；
 * 选中一个客户端后只取它的最近 50 条。每行时间、客户端、能力名、结果、错误码与耗时。
 */
export function AuditList() {
  const id = useId()
  const [client, setClient] = useState<string | undefined>(undefined)
  const all = useAudits()
  const filtered = useAudits(client)
  const clients = [...new Set((all.data ?? []).map((row) => row.client_name))]
  const shown = client ? filtered : all
  const chip = (value: string | undefined, label: string) => (
    <button key={value ?? ''} type="button" aria-pressed={client === value} data-hit44="" onClick={() => setClient(value)}>
      {label}
    </button>
  )
  return (
    <section aria-labelledby={id}>
      <div className="sec-h"><Title k="auditCalls" level="h" id={id} /></div>
      <Sensitive area="audit" className="pv-audit">
        <div className="chips" role="group" aria-label="按客户端筛选">
          {chip(undefined, '全部')}
          {clients.map((name) => chip(name, clientLabel(name)))}
        </div>
        <div className="plate">
          {shown.isError && <p className="pv-empty">{shown.error.message}</p>}
          {shown.data?.length === 0 && <p className="pv-empty">还没有调用记录。</p>}
          {!shown.data && !shown.isError && <p className="pv-empty" role="status">正在读取调用记录</p>}
          {shown.data && shown.data.length > 0 && <AuditRows rows={shown.data} />}
        </div>
      </Sensitive>
    </section>
  )
}
