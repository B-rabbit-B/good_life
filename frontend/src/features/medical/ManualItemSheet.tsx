import { useAddManualItem } from '../../api/hooks/medicalPage'
import type { OrderOut } from '../../api/types'
import { Sheet } from '../../components/Sheet'
import { useToast } from '../../components/Toast'
import { ItemForm, type ItemFormValues } from './ItemEditSheet'

function ManualBody({ order, onClose }: { order: OrderOut; onClose: () => void }) {
  const add = useAddManualItem(order.id)
  const toast = useToast()
  const submit = async (values: ItemFormValues) => {
    await add.mutateAsync({
      category: values.category, content: values.content, subjects: values.subjects,
      start_date: values.start_date, end_date: values.end_date, review_date: values.review_date,
    })
    toast.show('已补充一条，核对后才会生效')
  }
  return (
    <ItemForm
      initial={{ category: 'diet_avoid', content: '', subjects: [], start_date: order.order_date, end_date: null, review_date: null }}
      onSubmit={submit}
      onClose={onClose}
    />
  )
}

/**
 * 手动补充一条（提取器漏掉的）：挂在这份医嘱下，和提取出的条目一样先进入待核对；生效日期默认是医嘱的开具日期。
 */
export function ManualItemSheet({ order, isOpen, onClose }: { order: OrderOut; isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet isOpen={isOpen} onClose={onClose} titleKey="manualItem">
      <ManualBody order={order} onClose={onClose} />
    </Sheet>
  )
}
