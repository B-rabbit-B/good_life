import { StatusMark } from '../../components/StatusMark'
import { fmtBytes } from '../../lib/format'

export type RecognitionPhase = 'compressing' | 'uploading' | 'recognising'

/**
 * 识别进度（设计稿 04a）：上传、认菜和份量、按营养库计算三步。上传进度来自 XMLHttpRequest；
 * 照片传完、响应到达之前第二步转动（后端一次请求里同步识别并计算，第三步没有单独的进度）。
 * 当前一步是转动的钴蓝弧线，完成的一步是钴蓝圆点加勾；步骤的状态由文字说明，图形对读屏隐藏。
 * 读屏只在换步时播报一次（单独的 role="status"）；上传百分比是进度条语义，不随每个进度事件播报。
 */
const STEP_TEXT: Record<RecognitionPhase, string> = {
  compressing: '正在压缩照片',
  uploading: '正在上传照片',
  recognising: '上传完成，正在认菜和份量',
}

export function RecognitionProgress({ phase, size, sent, total }: {
  phase: RecognitionPhase
  /** 压缩后的字节数（还在压缩时为 null） */
  size: number | null
  sent: number
  total: number
}) {
  const percent = total > 0 ? Math.min(100, Math.round((sent / total) * 100)) : 0
  const sizeText = size === null ? '' : `压缩后 ${fmtBytes(size)}`
  let upload
  if (phase === 'compressing') upload = <span>正在压缩照片</span>
  else if (phase === 'uploading') {
    upload = (
      <span>
        正在上传
        <small>
          {sizeText}，
          <span role="progressbar" aria-label="上传进度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
            已传 {percent}%
          </span>
        </small>
      </span>
    )
  }
  else upload = <span>上传完成<small>{sizeText}</small></span>
  const recognising = phase === 'recognising'
  return (
    <>
      <p className="sr-only" role="status">{STEP_TEXT[phase]}</p>
      <ol className="prog-list" aria-label="识别进度">
        <li>
          <StatusMark state={recognising ? 'ok' : 'running'} />
          {upload}
        </li>
        <li>
          <StatusMark state={recognising ? 'running' : 'todo'} />
          {recognising
            ? <span>正在认菜和份量</span>
            : <span className="mute">正在认菜和份量<span className="sr-only">，等待中</span></span>}
        </li>
        <li>
          <StatusMark state="todo" />
          <span className="mute">按营养库计算热量与营养<span className="sr-only">，等待中</span></span>
        </li>
      </ol>
    </>
  )
}
