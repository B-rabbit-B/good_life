import { Button } from '../../components/Button'
import { AuthNeededState } from '../../components/states/AuthNeededState'

const BODY = '只用来查找附近的餐厅，精确位置不会保存。不允许也没关系，可以输入地名或地标，以后不再询问。'

/** 第一次查附近餐厅（后端说 should_ask_location）时问一次定位：允许或改为输入地点，两个整宽按钮上下排。 */
export function LocationAsk({ onAllow, onPlace, pending }: {
  onAllow: () => void
  onPlace: () => void
  /** 正在记下选择：两个按钮都不可再点，按下的那个显示进行中 */
  pending: 'granted' | 'denied' | null
}) {
  return (
    <AuthNeededState
      titleKey="locationAsk" body={BODY}
      actions={(
        <>
          <Button variant="primary" block icon="pin" isPending={pending === 'granted'} isDisabled={pending === 'denied'} onPress={onAllow}>
            允许定位
          </Button>
          <Button variant="quiet" block isPending={pending === 'denied'} isDisabled={pending === 'granted'} onPress={onPlace}>
            输入地点
          </Button>
        </>
      )}
    />
  )
}
