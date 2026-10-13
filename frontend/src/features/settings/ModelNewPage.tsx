// 添加模型服务（设计稿 10a 的四步、10b 的失败）：页头带返回，四步写在一块面板里；保存用途后回到模型服务页并轻提示“已保存”。
import { useNavigate } from 'react-router'
import { PATHS } from '../../app/paths'
import { PageHeader } from '../../components/PageHeader'
import { useToast } from '../../components/Toast'
import '../../styles/components/settings.css'
import { ProviderFlow } from './ProviderFlow'

export default function ModelNewPage() {
  const navigate = useNavigate()
  const toast = useToast()
  return (
    <>
      <PageHeader titleKey="modelNew" variant="sub" back={PATHS.models} />
      <div className="plate flow-plate">
        <ProviderFlow
          onDone={() => {
            toast.show('已保存')
            void navigate(PATHS.models)
          }}
        />
      </div>
    </>
  )
}
