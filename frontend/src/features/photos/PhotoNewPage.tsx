// 拍照识别（设计稿 04a、04c）：选图（拍照或相册，可选保留照片）与未处理的草稿；识别中显示三步进度，
// 可以取消；成功后换成识别结果页；失败时按错误码给出出路。对话页交来的照片（takePendingPhoto）进入页面就开始识别。
// 离开这一页不会取消识别：后端识别完会保存为草稿，回到这一页时出现在“未处理的草稿”里。
// “取消识别”只是不再等结果：照片已经传完时后端仍会识别并保存草稿，所以取消后过一会儿再刷新一次列表。
// 已确认与已放弃的识别列在“最近的识别”里，从那里进入结果页可以删除（连同保留的照片）。
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ChangeEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError, asApiError } from '../../api/errors'
import { useRecognitions } from '../../api/hooks/photos'
import { qk } from '../../api/keys'
import { getToken } from '../../api/token'
import { uploadRecognition } from '../../api/upload'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { Dock } from '../../components/Dock'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { Title } from '../../components/Title'
import { dayLabel } from '../../lib/dates'
import { peekPendingPhoto, takePendingPhoto } from '../../lib/photoHandoff'
import '../../styles/components/photos.css'
import { compressImage } from './compress'
import { PhotoTips, RecognitionFailure } from './RecognitionFailure'
import { RecognitionProgress, type RecognitionPhase } from './RecognitionProgress'

const PHOTO_TYPES = 'image/jpeg,image/png,image/webp'

// 取消后再刷新列表的时间：后端可能还在识别（看图模型最长约 60 秒）
const CANCEL_REFETCH_MS = [15_000, 60_000]
const STATUS_TEXT = { confirmed: '已确认入库', discarded: '已放弃' } as const

type Run =
  | { kind: 'idle'; cancelled?: boolean }
  | { kind: 'running'; keep: boolean; phase: RecognitionPhase; size: number | null; sent: number; total: number }
  | { kind: 'failed'; file: File; keep: boolean; error: ApiError }

const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

/**
 * 未处理的草稿与最近的识别（已确认、已放弃）：只写识别时间、菜品数与状态（这一页不在遮盖范围里，不写菜名）。
 * “最近的识别”的标题用黑体（宋体子集里没有这几个字）。
 */
function Recognitions() {
  const draftsId = useId()
  const recentId = useId()
  const recognitions = useRecognitions()
  const all = recognitions.data ?? []
  const drafts = all.filter((record) => record.status === 'draft')
  const recent = all.filter((record) => record.status !== 'draft')
  return (
    <>
      {drafts.length > 0 && (
        <section className="plate ph-drafts" aria-labelledby={draftsId}>
          <Title k="photoDrafts" level="h" id={draftsId} />
          {drafts.map((draft) => {
            const waiting = draft.items.filter((item) => item.status === 'needs_confirmation').length
            return (
              <Link key={draft.id} className="ph-draft" to={`/photos/${draft.id}`}>
                <span>{dayLabel(draft.created_at)} 识别</span>
                <span className="v">{draft.items.length} 项{waiting > 0 ? `，${waiting} 项待确认` : ''}</span>
                <Icon name="right" />
              </Link>
            )
          })}
        </section>
      )}
      {recent.length > 0 && (
        <section className="plate ph-drafts" aria-labelledby={recentId}>
          <h2 className="ph-list-h" id={recentId}>最近的识别</h2>
          {recent.map((record) => (
            <Link key={record.id} className="ph-draft" to={`/photos/${record.id}`}>
              <span>{dayLabel(record.created_at)} 识别</span>
              <span className="v">
                {record.status === 'draft' ? '' : STATUS_TEXT[record.status]}{record.image_kept ? '，保留了照片' : ''}
              </span>
              <Icon name="right" />
            </Link>
          ))}
        </section>
      )}
    </>
  )
}

const compressing = (keep: boolean): Run => ({ kind: 'running', keep, phase: 'compressing', size: null, sent: 0, total: 0 })

export default function PhotoNewPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  // 对话页交来的照片：渲染时只看一眼（渲染可能被丢弃），挂载后在副作用里取走；页面直接从“识别中”开始
  const [handed] = useState(peekPendingPhoto)
  const [keep, setKeep] = useState(false)
  const [run, setRun] = useState<Run>(() => (handed ? compressing(false) : { kind: 'idle' }))
  const controller = useRef<AbortController | null>(null)
  const mounted = useRef(false)
  const handedStarted = useRef(false)
  const refetchTimers = useRef<ReturnType<typeof setTimeout>[]>([])
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)

  useEffect(() => {
    mounted.current = true
    const timers = refetchTimers.current
    return () => {
      mounted.current = false
      for (const timer of timers) clearTimeout(timer)
    }
  }, [])

  /** 压缩、上传并等识别结果；只要 abort 还是当前这一次，就更新进度、成功后换成结果页、失败时显示出路 */
  const recognise = useCallback(async (file: File, keepImage: boolean, abort: AbortController) => {
    const current = () => controller.current === abort
    const token = getToken()
    const blob = await compressImage(file)
    if (!current()) return
    setRun({ kind: 'running', keep: keepImage, phase: 'uploading', size: blob.size, sent: 0, total: blob.size })
    try {
      const record = await uploadRecognition(blob, keepImage, (sent, total) => {
        if (!current()) return
        setRun((r) => (r.kind === 'running' ? { ...r, sent, total, phase: sent >= total ? 'recognising' : 'uploading' } : r))
      }, abort.signal)
      // 退出登录或换了账号之后才回来的结果不写进缓存（缓存已经清给下一个人了）；离开了这一页也不写，只刷新列表
      if (getToken() !== token) return
      void queryClient.invalidateQueries({ queryKey: qk.recognitions, exact: true })
      if (!mounted.current) return
      queryClient.setQueryData(qk.recognition(record.id), record)
      if (current()) void navigate(`/photos/${record.id}`, { replace: true })
    } catch (error) {
      if (isAbort(error) || !current()) return
      setRun({ kind: 'failed', file, keep: keepImage, error: asApiError(error) })
    }
  }, [navigate, queryClient])

  const start = (file: File, keepImage: boolean) => {
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setRun(compressing(keepImage))
    void recognise(file, keepImage, abort)
  }

  // 交来的照片在挂载后取走并开始识别（严格模式下副作用跑两遍，用 ref 保证只取一次、只开始一次）
  useLayoutEffect(() => {
    if (!handed || handedStarted.current) return
    handedStarted.current = true
    takePendingPhoto()
    const abort = new AbortController()
    controller.current = abort
    void recognise(handed, false, abort)
  }, [handed, recognise])

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) void start(file, run.kind === 'failed' ? run.keep : keep)
  }

  const cancel = () => {
    controller.current?.abort()
    controller.current = null
    setRun({ kind: 'idle', cancelled: true })
    const refetch = () => void queryClient.invalidateQueries({ queryKey: qk.recognitions, exact: true })
    refetch()
    for (const delay of CANCEL_REFETCH_MS) refetchTimers.current.push(setTimeout(refetch, delay))
  }

  let body
  if (run.kind === 'running') {
    body = (
      <>
        <div className="ph-big">
          <span>{run.keep ? '你选的照片（加密保留）' : '你选的照片（不保留，识别后丢弃）'}</span>
        </div>
        <div className="plate">
          <RecognitionProgress phase={run.phase} size={run.size} sent={run.sent} total={run.total} />
        </div>
        <p className="t-cap pad ph-leave">可以离开这一页，识别完成后可在拍照页的“未处理的草稿”里继续。</p>
        <Dock>
          <Button variant="quiet" block onPress={cancel}>取消识别</Button>
        </Dock>
      </>
    )
  } else if (run.kind === 'failed') {
    body = (
      <RecognitionFailure
        error={run.error}
        onRetake={() => camera.current?.click()}
        onGallery={() => gallery.current?.click()}
        onRetry={() => void start(run.file, run.keep)}
      />
    )
  } else {
    body = (
      <>
        <div className="pad ph-pick">
          <Button variant="primary" block icon="camera" onPress={() => camera.current?.click()}>拍照</Button>
          <Button variant="quiet" block icon="image" onPress={() => gallery.current?.click()}>从相册选</Button>
          <Checkbox isSelected={keep} onChange={setKeep}>保留照片（加密保存，可随时删除）</Checkbox>
          {run.cancelled && (
            <p className="t-cap ph-cancelled" role="status">
              已取消识别。如果照片已经传完，识别仍会在后台完成，草稿可能过一会儿出现在“未处理的草稿”里。
            </p>
          )}
        </div>
        <Recognitions />
        <PhotoTips />
      </>
    )
  }

  return (
    <>
      <PageHeader titleKey="photo" variant="sub" back />
      {body}
      <input ref={camera} className="file-in" type="file" accept={PHOTO_TYPES} capture="environment" tabIndex={-1} onChange={onPick} />
      <input ref={gallery} className="file-in" type="file" accept={PHOTO_TYPES} tabIndex={-1} onChange={onPick} />
    </>
  )
}
