import type { TitleKey } from '../lib/titles'
import '../styles/components/button.css'
import '../styles/components/care.css'
import { Icon } from './Icon'
import { Title } from './Title'

/**
 * 就医提示：全站唯一不圆角、不透明、整块朱色的东西；左右出血到屏幕边，在回答最上方，不可折叠、不可关闭。
 * 每个号码一个白底拨号按钮；底部固定说明它不是模型生成的。
 */
export function CareBlock({ titleKey, text, phones }: { titleKey: TitleKey; text: string; phones: ('120' | '12356')[] }) {
  return (
    <div className="care" role="alert">
      <div className="care-h">
        <Icon name="alert" />
        <Title k={titleKey} level="title" as="h2" />
      </div>
      <p>{text}</p>
      <div className="care-calls">
        {phones.map((phone) => (
          <a key={phone} className="btn btn-blk" href={`tel:${phone}`}>
            <Icon name="phone" size={18} />
            拨打 {phone}
          </a>
        ))}
      </div>
      <small>这是一条固定的安全提示，不是模型生成的。</small>
    </div>
  )
}
