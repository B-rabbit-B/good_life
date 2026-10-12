import { COVER_NAMES, useCover } from './cover'
import { IconButton } from './IconButton'

/** 没有底部导航的二级页右上角的遮盖按钮；与导航里的遮盖格共用状态与读屏文字。 */
export function CoverButton() {
  const { covered, toggle } = useCover()
  return (
    <IconButton
      icon="cover"
      label={covered ? COVER_NAMES.on.label : COVER_NAMES.off.label}
      pressed={covered}
      onPress={toggle}
    />
  )
}
