// 运动限制条（设计稿 08 顶部）：今天生效的“运动限制”类医嘱，每条一行“运动限制生效中：内容，到 某日”，赭色浅底圆角。
// 它是医嘱内容，整块在敏感区里；医嘱模块没开放时不请求、不显示。读取失败时一行说明加错误码（同样在敏感区里）。
import { asApiError } from '../../api/errors'
import { useConstraints } from '../../api/hooks/medicalPage'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { formatMonthDay } from '../../lib/dates'
import '../../styles/components/training.css'

export function LimitStrip() {
  const constraints = useConstraints('exercise_limit')
  const limits = constraints.data?.constraints ?? []
  if (constraints.isError && constraints.data === undefined) {
    const error = asApiError(constraints.error)
    return (
      <Sensitive area="constraints" className="lims">
        <p className="lim">
          <Icon name="alert" size={18} />
          <span>没能读取今天的运动限制：{error.message}<small>错误码 {error.code}</small></span>
        </p>
      </Sensitive>
    )
  }
  if (limits.length === 0) return null
  return (
    <Sensitive area="constraints" className="lims">
      {limits.map((limit) => (
        <p key={limit.item_id} className="lim">
          <Icon name="alert" size={18} />
          <span>运动限制生效中：{limit.content}{limit.end_date ? `，到 ${formatMonthDay(limit.end_date)}` : ''}</span>
        </p>
      ))}
    </Sensitive>
  )
}
