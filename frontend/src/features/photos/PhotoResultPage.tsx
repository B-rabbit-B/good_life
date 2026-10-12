// 识别结果（设计稿 04b）：缩略图与状态；建议核对的提示条；识别项面板（菜名、热量、份量与克数、把握程度、营养库、
// 评价结论；候选、修改、删除）与合计四格；整餐评价（只有草稿有）；吃的时间；放弃这次识别；操作坞里确认入库。
// 菜名、数字与评价在敏感区里。已确认或已放弃的记录只读显示状态。界面不做判断：待确认、建议核对、评价都来自后端。
import { useQueryClient } from '@tanstack/react-query'
import { useId, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { networkError } from '../../api/client'
import { ApiError } from '../../api/errors'
import {
  useConfirmRecognition, useDiscardRecognition, useObjectUrl, useRecognition, useRecognitionImage,
  useUpdateRecognitionItems,
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
import { dayLabel, defaultMealType, formatMonthDay, todayISO } from '../../lib/dates'
import { fmtFixed, fmtNum } from '../../lib/format'
import { MEAL_LABELS, type MealType } from '../../lib/labels'
import '../../styles/components/photos.css'
import { ItemEditSheet } from './ItemEditSheet'
import { ItemRow } from './ItemRow'
import { toItemsUpdate, type ItemChange } from './itemsUpdate'
import { MealEvaluation } from './MealEvaluation'

const MEAL_OPTIONS = (Object.keys(MEAL_LABELS) as MealType[]).map((value) => ({ value, label: MEAL_LABELS[value] }))
const STATUS_TEXT: Record<RecognitionOut['status'], string> = { draft: '草稿', confirmed: '已确认入库', discarded: '已放弃' }
// 确认入库被这两种错误挡回时，把焦点移到第一个需要处理的项
const BACK_TO_ITEMS = new Set(['photo_items_need_confirmation', 'photo_grams_out_of_range'])

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError())

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

/** 缩略图：保留了照片才去取（image_kept），否则写“图片 未保留” */
function Thumbnail({ record }: { record: RecognitionOut }) {
  const blob = useRecognitionImage(record.id, record.image_kept)
  return (
    <Sensitive area="dishes" className="ph-img">
      {blob ? <KeptImage blob={blob} /> : <span>图片<br />{record.image_kept ? '读取中' : '未保留'}</span>}
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

  const change = (next: ItemChange) => update.mutateAsync(toItemsUpdate(record.items, next))
  const quietly = (next: ItemChange) =>
    change(next).catch((error: unknown) => {
      toast.show(asApiError(error).message)
      throw error
    })

  const focusItem = (item: PhotoItemOut | undefined) => {
    const rows = Array.from(listRef.current?.querySelectorAll<HTMLElement>('[data-item-id]') ?? [])
    rows.find((row) => row.dataset.itemId === item?.id)?.focus()
  }

  const onConfirm = () => {
    confirm.mutate({ eaten_on: date, meal_type: meal }, {
      onSuccess: (saved) => void navigate(`/records?tab=diet&date=${saved.eaten_on ?? date}`),
      onError: (error) => {
        const apiError = asApiError(error)
        toast.show(apiError.message)
        void queryClient.invalidateQueries({ queryKey: qk.recognition(record.id) })
        if (BACK_TO_ITEMS.has(apiError.code)) focusItem(firstToHandle(record.items))
      },
    })
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
