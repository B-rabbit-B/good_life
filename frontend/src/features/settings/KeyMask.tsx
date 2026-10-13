import { Icon } from '../../components/Icon'

/** 密钥掩码：锁图标加后端给的 key_hint（前端从不保存、也不显示密钥原文）。 */
export function KeyMask({ hint }: { hint: string }) {
  return (
    <span className="mask" role="img" aria-label={`密钥 ${hint}`}>
      <Icon name="lock" size={18} />
      <span aria-hidden="true">{hint}</span>
    </span>
  )
}
