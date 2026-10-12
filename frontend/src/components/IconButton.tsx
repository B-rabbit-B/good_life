import { Button as AriaButton } from 'react-aria-components'
import '../styles/components/button.css'
import { Icon, type IconName } from './Icon'

/** 图标按钮：44 点按区（.ibtn）；返回键加 .back，是 44 点按区里一颗 36 的瓷扣。 */
export function IconButton({ icon, label, onPress, back = false, pressed }: {
  icon: IconName
  label: string
  onPress?: () => void
  back?: boolean
  pressed?: boolean
}) {
  return (
    <AriaButton
      className={back ? 'ibtn back' : 'ibtn'}
      aria-label={label}
      aria-pressed={pressed}
      onPress={onPress}
    >
      <Icon name={icon} />
    </AriaButton>
  )
}
