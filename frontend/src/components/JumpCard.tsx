import '../styles/components/jump.css'
import { ButtonLink } from './ButtonLink'
import { Icon } from './Icon'
import { Surface } from './Surface'

/** 对话里唯一的跳转件（例如“去医嘱页处理”）：一块白瓷，说明加一个小按钮，只导航，不在对话里完成任何确认或解除。 */
export function JumpCard({ to, label, description }: { to: string; label: string; description?: string }) {
  return (
    <Surface tier="plate" className="jump">
      {description && <p className="t-small">{description}</p>}
      <ButtonLink to={to} variant="quiet" size="sm">
        <Icon name="doc" size={18} />
        {label}
      </ButtonLink>
    </Surface>
  )
}
