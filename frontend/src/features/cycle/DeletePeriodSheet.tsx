// 删除一次经期记录的确认面板：后端只删这条经期（每日记录是另一张表，不连带删除），预测与统计随之重算。
// 面板里不写日期（遮盖时轻提示与面板文字都不带出内容）。确认中锁面板与 Esc（ConfirmSheet）；失败后恢复，原样显示后端的说明与错误码。
import { useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useDeletePeriod } from '../../api/hooks/cycle'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { useToast } from '../../components/Toast'

export function DeletePeriodSheet({ periodId, isOpen, onClose }: { periodId: string; isOpen: boolean; onClose: () => void }) {
  const remove = useDeletePeriod()
  const toast = useToast()
  const [error, setError] = useState<ApiError | null>(null)

  const onConfirm = async () => {
    setError(null)
    try {
      await remove.mutateAsync(periodId)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    onClose()
    toast.show('已删除')
  }

  return (
    <ConfirmSheet
      isOpen={isOpen} onClose={onClose} title="删除这次经期记录"
      will={[
        { text: '这次经期记录会被删除，这段时间的预测与统计会重新计算。', irreversible: true },
        { text: '这次经期当天的每日记录不会被删除。' },
      ]}
      confirmLabel="删除这次经期" confirmVariant="danger" onConfirm={onConfirm} error={error}
    />
  )
}
