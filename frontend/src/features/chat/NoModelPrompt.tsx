import { ButtonLink } from '../../components/ButtonLink'
import { AuthNeededState } from '../../components/states/AuthNeededState'
import { Surface } from '../../components/Surface'
import '../../styles/components/chat.css'

/** 还没有可用的对话模型：说明要做什么、大约多久，并给“去添加模型服务” */
export function NoModelPrompt() {
  return (
    <Surface tier="plate" className="nomodel">
      <AuthNeededState
        titleKey="noModel"
        body="对话和拍照识别都需要先添加一个模型服务，填地址与密钥，大约两分钟。"
        actions={<ButtonLink to="/settings/models/new" variant="primary">去添加模型服务</ButtonLink>}
      />
    </Surface>
  )
}
