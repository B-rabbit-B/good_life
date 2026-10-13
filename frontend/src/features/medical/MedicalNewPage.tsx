// 录入医嘱（设计稿 07f）：照原文粘贴（1 至 5000 字）、开具日期（默认今天、不晚于今天）与可选的证据（拍照或相册，
// 可移除，显示大小与“加密保存”）。“提取条目”先建医嘱（后端提取出待核对的条目），再逐个上传证据，全部完成后去待核对。
// 任何一步失败都原样显示后端的说明与错误码；已经建好的医嘱不会重复提交，重试只上传还没传完的证据。
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError } from '../../api/errors'
import { useCreateOrder, useUploadEvidence } from '../../api/hooks/medicalPage'
import { useObjectUrl } from '../../api/hooks/photos'
import type { OrderOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { DateField } from '../../components/DateField'
import { Dock } from '../../components/Dock'
import { Icon } from '../../components/Icon'
import { IconButton } from '../../components/IconButton'
import { PageHeader } from '../../components/PageHeader'
import { Sensitive } from '../../components/Sensitive'
import { TextField } from '../../components/TextField'
import { todayISO } from '../../lib/dates'
import { fmtBytes } from '../../lib/format'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/medical.css'
import { errorsOf, FORM_ERROR } from '../onboarding/fieldErrors'

// app/medical/schemas.py 的 OrderCreate.text 与 app/medical/orders.py 的证据上限、类型：界面只先提示，以后端结果为准
const MAX_TEXT = 5000
const MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
const EVIDENCE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
const PENDING_TAB = `${PATHS.medical}?tab=pending`

interface Picked {
  key: number
  file: File
}

type Failure = { error: ApiError; file?: string }

const toApiError = (caught: unknown) =>
  caught instanceof ApiError ? caught : new ApiError(0, 'unknown_error', String(caught))

function Thumb({ file }: { file: File }) {
  const ref = useObjectUrl(file)
  return <img ref={ref} alt="" />
}

function warningOf(file: File): string | null {
  if (file.size > MAX_EVIDENCE_BYTES) return '文件超过 10 MB，可能无法上传'
  if (file.type && !EVIDENCE_TYPES.includes(file.type)) return '只支持 JPG、PNG、WEBP 图片或 PDF，这个文件可能无法上传'
  return null
}

export default function MedicalNewPage() {
  useSensitivePage('medicalNew')
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [date, setDate] = useState<string | null>(() => todayISO())
  const [files, setFiles] = useState<Picked[]>([])
  const [order, setOrder] = useState<OrderOut | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [pending, setPending] = useState(false)
  const createOrder = useCreateOrder()
  const upload = useUploadEvidence()
  const flight = useSingleFlight()
  const created = useRef<OrderOut | null>(null) // 已建好的医嘱：重试时不再提交
  const uploaded = useRef(new Set<number>()) // 已上传的证据
  const nextKey = useRef(0)
  const camera = useRef<HTMLInputElement>(null)
  const album = useRef<HTMLInputElement>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  const today = todayISO()
  const fieldErrors = failure && !failure.file && failure.error.code === 'validation_error' ? errorsOf(failure.error) : {}
  const formMessage = failure && (failure.file || failure.error.code !== 'validation_error' || fieldErrors[FORM_ERROR])
    ? `${failure.file ? `${failure.file}：` : ''}${fieldErrors[FORM_ERROR] ?? failure.error.message}`
    : null

  // 出错的说明可能落在操作坞下面：滚到视野里
  useEffect(() => {
    const el = errorRef.current
    if (failure && el && typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'center' })
  }, [failure])

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(event.target.files ?? []).map((file) => {
      nextKey.current += 1
      return { key: nextKey.current, file }
    })
    event.target.value = ''
    setFiles((list) => [...list, ...picked])
  }

  const submit = () => {
    const run = flight(async () => {
      setPending(true)
      setFailure(null)
      let current = created.current
      if (!current) {
        try {
          current = await createOrder.mutateAsync({ text, order_date: date })
        } catch (caught) {
          setFailure({ error: toApiError(caught) })
          return
        }
        created.current = current
        setOrder(current)
      }
      for (const picked of files) {
        if (uploaded.current.has(picked.key)) continue
        try {
          await upload.mutateAsync({ orderId: current.id, file: picked.file })
        } catch (caught) {
          setFailure({ error: toApiError(caught), file: picked.file.name })
          return
        }
        uploaded.current.add(picked.key)
      }
      await navigate(PENDING_TAB)
    })
    void run?.finally(() => setPending(false))
  }

  return (
    <>
      <PageHeader titleKey="medicalNew" variant="sub" back={PATHS.medical} />
      <p className="t-small ink2 pad mn-lead">照你拿到的原文粘贴或拍照，不用改写。提取出的条目需要你逐条核对后才会生效。</p>
      <Sensitive area="content" className="plate mn">
        {/* 医嘱建好之后原文与日期只读：重试只上传证据，改了也不会再提交 */}
        <TextField
          label="医嘱原文" value={text} onChange={setText} multiline rows={5} maxLength={MAX_TEXT}
          hint={`${text.length} / ${MAX_TEXT}`} error={fieldErrors.text} isReadOnly={order !== null}
        />
        <DateField
          label="开具日期" value={date} onChange={setDate} max={today} error={fieldErrors.order_date} readOnly={order !== null}
        />
        <p className="fld-l mn-ev-l">证据（可选）</p>
        {files.length > 0 && (
          <ul className="mn-files" aria-label="证据">
            {files.map(({ key, file }) => {
              const warning = warningOf(file)
              return (
                <li key={key} className="srcbox">
                  <div className="src-img" aria-hidden="true">
                    {file.type.startsWith('image/') ? <Thumb file={file} /> : file.type === 'application/pdf' ? 'PDF' : '文件'}
                  </div>
                  <div>
                    <div className="src-t">{file.name}</div>
                    <div className="t-cap">{fmtBytes(file.size)}，加密保存</div>
                    {warning && <span className="mn-warn">{warning}</span>}
                  </div>
                  <IconButton
                    icon="x" label={`移除${file.name}`} isDisabled={pending}
                    onPress={() => setFiles((list) => list.filter((p) => p.key !== key))}
                  />
                </li>
              )
            })}
          </ul>
        )}
        <div className="mn-pick">
          <Button variant="text" icon="camera" onPress={() => camera.current?.click()}>拍照</Button>
          <Button variant="text" icon="image" onPress={() => album.current?.click()}>从相册选</Button>
        </div>
        {order && (
          <p className="t-small mn-status" role="status">
            医嘱已提交，提取出 {order.items.length} 条。重试只上传还没传完的证据，不会重复提交医嘱。
          </p>
        )}
        {formMessage && failure && (
          <div className="err" role="alert" ref={errorRef}>
            <Icon name="alert" size={18} />
            <span>{formMessage}<small>错误码 {failure.error.code}</small></span>
          </div>
        )}
        {order && failure && (
          <div className="mn-after">
            <Button variant="text" onPress={() => void navigate(PENDING_TAB)}>先去核对，不传剩下的证据</Button>
          </div>
        )}
      </Sensitive>
      <p className="t-cap pad mn-lead">提取后可以逐条修改，也可以在待核对里手动补充一条。</p>
      <input
        ref={camera} className="file-in" type="file" accept="image/*" capture="environment" tabIndex={-1} hidden onChange={onPick}
      />
      <input
        ref={album} className="file-in" type="file" accept={EVIDENCE_TYPES.join(',')} multiple tabIndex={-1} hidden onChange={onPick}
      />
      <Dock>
        <Button variant="primary" block isPending={pending} isDisabled={!order && text.trim() === ''} onPress={submit}>
          {order ? '重试上传证据' : '提取条目'}
        </Button>
      </Dock>
    </>
  )
}
