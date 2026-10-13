import { useId } from 'react'
import { Link } from 'react-router'
import type { ApiError } from '../../api/errors'
import { PATHS } from '../../app/paths'
import { Button, buttonClassName } from '../../components/Button'
import { ButtonLink } from '../../components/ButtonLink'
import { Title } from '../../components/Title'
import { WillList } from '../../components/WillList'
import type { TitleKey } from '../../lib/titles'

const TIPS = [
  { text: '光线充足，从斜上方拍，整盘入镜。' },
  { text: '一张照片一餐；多道菜可以拍在同一张里。' },
  { text: '只支持 JPEG、PNG、WebP，不超过 8 MB。' },
]

/** 看图模型没配好、出错或没按要求回答：可以用同一张照片重试，也可以去设置换一个看图模型 */
const isModelFailure = (code: string) => code.startsWith('llm_') || code === 'photo_recognition_failed'

const titleOf = (code: string): TitleKey =>
  code === 'photo_not_food' ? 'photoNotFood' : code === 'photo_unclear' ? 'photoUnclear' : 'photoFailed'

/** 拍照小提示（光线、一餐一张、格式与 8 MB） */
export function PhotoTips() {
  const id = useId()
  return (
    <section className="plate ph-tips" aria-labelledby={id}>
      <Title k="photoTips" level="h" id={id} />
      <WillList items={TIPS} />
    </section>
  )
}

/**
 * 识别失败（设计稿 04c 与状态面板“拍照识别失败”）：标题按错误码（没认出食物、看不清、其余“这次没有识别完成”），
 * 正文原样是后端说明，下一行写错误码与“这次没有产生识别记录”（失败时后端不保存记录）。
 * 出路：重拍、从相册换一张、手动记一餐；看图模型的失败另有“重试识别”（用内存里的同一张照片）与“去设置”；
 * 网络断了也可以直接重试。
 */
export function RecognitionFailure({ error, onRetake, onGallery, onRetry }: {
  error: ApiError
  onRetake: () => void
  onGallery: () => void
  onRetry: () => void
}) {
  const model = isModelFailure(error.code)
  const retry = model || error.code === 'network_error'
  return (
    <>
      <div className="ph-big short">
        <span>{retry ? '你选的照片（还在本页，可以直接重试）' : '你选的照片（已丢弃）'}</span>
      </div>
      <div className="pad ph-fail">
        <div role="alert">
          <Title k={titleOf(error.code)} level="display" as="h2" />
          <p className="t-small ink2 ph-fail-msg">{error.message}</p>
          <p className="t-cap ph-fail-code">错误码 {error.code}。这次没有产生识别记录。</p>
        </div>
        <div className="ph-fail-acts">
          {retry && <Button variant="primary" block icon="refresh" onPress={onRetry}>重试识别</Button>}
          <Button variant={retry ? 'quiet' : 'primary'} block icon="camera" onPress={onRetake}>重拍</Button>
          <Button variant="quiet" block icon="image" onPress={onGallery}>从相册换一张</Button>
          {model && <ButtonLink to={PATHS.models} variant="quiet" block>去设置</ButtonLink>}
          <Link to={PATHS.mealNew} className={buttonClassName({ variant: 'text', onField: true })}>手动记一餐</Link>
        </div>
      </div>
      <PhotoTips />
    </>
  )
}
