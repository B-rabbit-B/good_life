// 识别结果（设计稿 04b）：缩略图与状态；建议核对的提示条；识别项面板（菜名、热量、份量与克数、把握程度、营养库、
// 评价结论；候选、修改、删除）与合计四格；整餐评价（只有草稿有）；吃的时间；放弃这次识别；操作坞里确认入库。
// 菜名、数字与评价在敏感区里。已确认或已放弃的记录只读显示状态。界面不做判断：待确认、建议核对、评价都来自后端。
import { useQueryClient } from '@tanstack/react-query'
import { useId, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { asApiError } from '../../api/errors'
import {
  useConfirmRecognition, useDeleteRecognition, useDiscardRecognition, useObjectUrl, useRecognition,
  useRecognitionImage, useUpdateRecognitionItems,
} from '../../api/hooks/photos'
import { qk } from '../../api/keys'
import type { PhotoItemOut, RecognitionOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { Button } from '../../components/Button'
import { ButtonLink } from '../../components/ButtonLink'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { DateField } from '../../components/DateField'
import { Dock } from '../../components/Dock'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { SelectField } from '../../components/SelectField'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { Title } from '../../components/Title'
import { useToast } from '../../components/Toast'
import { PHOTO_GRAMS_OUT_OF_RANGE, PHOTO_ITEMS_NEED_CONFIRMATION } from '../../lib/contract'
import { dayLabel, defaultMealType, formatMonthDay, todayISO } from '../../lib/dates'
import { fmtFixed, fmtNum } from '../../lib/format'
import { MEAL_LABELS, type MealType } from '../../lib/labels'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/photos.css'
import { ItemEditSheet } from './ItemEditSheet'
import { ItemRow } from './ItemRow'
import { toItemsUpdate, type ItemChange } from './itemsUpdate'
import { MealEvaluation } from './MealEvaluation'

const MEAL_OPTIONS = (Object.keys(MEAL_LABELS) as MealType[]).map((value) => ({ value, label: MEAL_LABELS[value] }))
const STATUS_TEXT: Record<RecognitionOut['status'], string> = { draft: '草稿', confirmed: '已确认入库', discarded: '已放弃' }
// 确认入库被这两种错误挡回时，把焦点移到第一个需要处理的项
const BACK_TO_ITEMS = new Set([PHOTO_ITEMS_NEED_CONFIRMATION, PHOTO_GRAMS_OUT_OF_RANGE])

// 另一个修正还没回来时跳过这一次（不提示错误）
const SKIPPED = new Error('上一个修正还没完成')
// 删除的标题：保留了照片时说明照片一起删
const deleteTitle = (imageKept: boolean) => (imageKept ? '删除这条识别（连同照片）' : '删除这条识别')

/** 第一个需要处理的项：待确认的，其次克数不在常见范围的，再次任何建议核对的，最后第一项 */
function firstToHandle(items: PhotoItemOut[]): PhotoItemOut | undefined {
  return items.find((item) => item.status === 'needs_confirmation')
    ?? items.find((item) => item.review_reasons.includes('grams_out_of_range'))
    ?? items.find((item) => item.review_reasons.length > 0)
    ?? items[0]
}

function KeptImage({ blob }: { blob: Blob }) {
  const ref = useObjectUrl(blob)
  return <img ref={ref} alt="这次识别保留的照片" />
}

/** 缩略图：保留了照片才去取（image_kept），否则写“图片 未保留”；取不到时写“读取失败” */
function Thumbnail({ record }: { record: RecognitionOut }) {
  const { blob, failed } = useRecognitionImage(record.id, record.image_kept)
  let state = '未保留'
  if (record.image_kept) state = failed ? '读取失败' : '读取中'
  return (
    <Sensitive area="dishes" className="ph-img">
      {blob ? <KeptImage blob={blob} /> : <span>图片<br />{state}</span>}
    </Sensitive>
  )
}

function Totals({ record }: { record: RecognitionOut }) {
  const { totals } = record
  const cell = (value: number | null | undefined, format: (n: number) => string, label: string) => (
    <div><span className="ns">{value == null ? '—' : format(value)}</span>{label}</div>
  )
  return (
    <div className="totals">
      {cell(totals.energy_kcal, (n) => fmtNum(n, 1), '千卡')}
      {cell(totals.protein_g, (n) => fmtFixed(n, 1), '蛋白质 克')}
      {cell(totals.fat_g, (n) => fmtFixed(n, 1), '脂肪 克')}
      {cell(totals.sodium_mg, (n) => fmtNum(n, 1), '钠 毫克')}
    </div>
  )
}

function ResultBody({ record }: { record: RecognitionOut }) {
  const draft = record.status === 'draft'
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const update = useUpdateRecognitionItems(record.id)
  const confirm = useConfirmRecognition(record.id)
  const discard = useDiscardRecognition(record.id)
  const remove = useDeleteRecognition(record.id)
  // 双击或连按时 isPending 还没渲染出来，第二次按下照样会发请求：确认与修正各用一把锁
  const confirmFlight = useSingleFlight()
  const itemFlight = useSingleFlight()
  // 请求回来到页面按新记录重画之间还隔着一拍：已经改过的那一版记录不再接受修正，确认成功后也不再确认
  const revised = useRef<RecognitionOut | null>(null)
  const confirmed = useRef(false)
  const [removeOpen, setRemoveOpen] = useState(false)
  const [editing, setEditing] = useState<PhotoItemOut | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [date, setDate] = useState(record.eaten_on ?? todayISO())
  const [meal, setMeal] = useState<MealType>(record.meal_type ?? defaultMealType(new Date()))
  const listRef = useRef<HTMLDivElement>(null)
  const whenId = useId()

  const conclusions = new Map((record.evaluation?.items ?? []).map((item) => [item.item_id, item.conclusion]))
  const waiting = record.items.filter((item) => item.status === 'needs_confirmation').length
  const flagged = record.items.filter((item) => item.review_reasons.length > 0).length

  const change = (next: ItemChange) => {
    if (revised.current === record) return Promise.reject(SKIPPED)
    const run = itemFlight(async () => {
      const saved = await update.mutateAsync(toItemsUpdate(record.items, next))
      revised.current = record
      return saved
    })
    return run ?? Promise.reject(SKIPPED)
  }
  const quietly = (next: ItemChange) =>
    change(next).catch((error: unknown) => {
      if (error !== SKIPPED) toast.show(asApiError(error).message)
      throw error
    })

  const focusItem = (item: PhotoItemOut | undefined) => {
    const rows = Array.from(listRef.current?.querySelectorAll<HTMLElement>('[data-item-id]') ?? [])
    rows.find((row) => row.dataset.itemId === item?.id)?.focus()
  }

  const onConfirm = () => {
    if (confirmed.current) return
    const run = confirmFlight(() => confirm.mutateAsync({ eaten_on: date, meal_type: meal }))
    run?.then(
      (saved) => {
        confirmed.current = true
        void navigate(`/records?tab=diet&date=${saved.eaten_on ?? date}`)
      },
      (error: unknown) => {
        const apiError = asApiError(error)
        toast.show(apiError.message)
        void queryClient.invalidateQueries({ queryKey: qk.recognition(record.id) })
        if (BACK_TO_ITEMS.has(apiError.code)) focusItem(firstToHandle(record.items))
      },
    )
  }

  const onRemove = async () => {
    await remove.mutateAsync()
    setRemoveOpen(false)
    toast.show('已删除这条识别')
    await navigate('/photos/new', { replace: true })
    // 离开结果页之后再移除这一条与它的图片的缓存（还在页面上时移除会让它重新请求）
    queryClient.removeQueries({ queryKey: qk.recognition(record.id) })
  }

  return (
    <>
      <div className="ph-top">
        <Thumbnail record={record} />
        <div>
          <div className="ph-state">{STATUS_TEXT[record.status]}</div>
          <div className="t-cap">
            {dayLabel(record.created_at)} 识别<br />
            看图模型 {record.model_id}
            {record.status === 'confirmed' && record.eaten_on && record.meal_type && (
              <><br />记入 {formatMonthDay(record.eaten_on)} {MEAL_LABELS[record.meal_type]}</>
            )}
          </div>
        </div>
      </div>
      {draft && flagged > 0 && (
        <p className="nr"><Icon name="alert" size={18} /><span>{`有 ${flagged} 项建议核对`}</span></p>
      )}
      <Sensitive area="dishes" className="plate">
        <div ref={listRef}>
          {record.items.map((item) => (
            <ItemRow
              key={item.id} item={item} conclusion={conclusions.get(item.id)} editable={draft} busy={update.isPending}
              onEdit={(target) => {
                setEditing(target)
                setEditOpen(true)
              }}
              onDelete={(target) => void quietly({ kind: 'delete', id: target.id }).catch(() => undefined)}
              onPick={(target, foodId) => quietly({ kind: 'edit', id: target.id, food_id: foodId })}
            />
          ))}
        </div>
        <Totals record={record} />
        <p className="t-cap ph-disc">{record.disclaimer}</p>
      </Sensitive>
      {record.evaluation && <MealEvaluation evaluation={record.evaluation} />}
      {draft && (
        <>
          <section className="plate when-p" aria-labelledby={whenId}>
            <Title k="mealWhen" level="h" id={whenId} />
            <div className="when">
              <DateField label="日期" value={date} max={todayISO()} onChange={(value) => setDate(value ?? todayISO())} />
              <SelectField label="餐次" value={meal} options={MEAL_OPTIONS} onChange={(value) => setMeal(value as MealType)} />
            </div>
          </section>
          <div className="ph-discard">
            <Button variant="text" ink onPress={() => setDiscardOpen(true)}>放弃这次识别</Button>
          </div>
          <Dock>
            <Button variant="primary" block isDisabled={waiting > 0} isPending={confirm.isPending} onPress={onConfirm}>
              {waiting > 0 ? `确认入库（还有 ${waiting} 项待确认）` : '确认入库'}
            </Button>
          </Dock>
          <ItemEditSheet
            item={editing} isOpen={editOpen} onClose={() => setEditOpen(false)}
            onSave={(next) => change(next)}
          />
          <ConfirmSheet
            isOpen={discardOpen} onClose={() => setDiscardOpen(false)} titleKey="discardRecognition"
            will={[{ text: '这次识别的菜品不会写入饮食记录' }, { text: '放弃后不能再修改或确认入库，需要时重新拍照识别' }]}
            confirmLabel="放弃" confirmVariant="danger" error={discard.error ? asApiError(discard.error) : null}
            onConfirm={async () => {
              await discard.mutateAsync()
              setDiscardOpen(false)
              toast.show('已放弃这次识别')
              await navigate('/photos/new', { replace: true })
            }}
          />
        </>
      )}
      {record.status === 'confirmed' && record.eaten_on && (
        <div className="pad ph-done">
          <ButtonLink to={`/records?tab=diet&date=${record.eaten_on}`} variant="quiet" block>查看这天的饮食记录</ButtonLink>
        </div>
      )}
      <div className="ph-discard">
        <Button variant="text" ink onPress={() => setRemoveOpen(true)}>{deleteTitle(record.image_kept)}</Button>
      </div>
      <ConfirmSheet
        isOpen={removeOpen} onClose={() => setRemoveOpen(false)} title={deleteTitle(record.image_kept)}
        will={[
          { text: record.image_kept ? '这条识别记录与保留的照片一起删除' : '这条识别记录被删除（这次没有保留照片）' },
          { text: '已经写入饮食记录的条目不受影响，需要时到饮食记录里修改' },
          { text: '删除后不能恢复', irreversible: true },
        ]}
        confirmLabel="删除" confirmVariant="danger" error={remove.error ? asApiError(remove.error) : null}
        onConfirm={onRemove}
      />
    </>
  )
}

export default function PhotoResultPage() {
  useSensitivePage('photoResult')
  const { recId = '' } = useParams()
  const record = useRecognition(recId)
  let body
  if (record.data) body = <ResultBody key={record.data.id} record={record.data} />
  else if (record.isError) {
    body = <ErrorState error={asApiError(record.error)} onRetry={() => void record.refetch()} />
  } else body = <LoadingState variant="page" text="正在读取识别结果" />
  return (
    <>
      <PageHeader titleKey="photoResult" variant="sub" back />
      {body}
    </>
  )
}
