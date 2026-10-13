import { useId, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useClearArea, useRestaurantSettings } from '../../api/hooks/restaurants'
import { Button } from '../../components/Button'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import { Title } from '../../components/Title'
import { todayISO } from '../../lib/dates'


/**
 * 已保存的大致区域（敏感区 savedArea）：区域名与保存日期，“清除”经确认面板后删除。
 * 饮食模块不开放时（附近餐厅不可用）整段不显示。轻提示只写“已清除”，不带区域名。
 */
export function SavedArea({ enabled }: { enabled: boolean }) {
  const id = useId()
  const settings = useRestaurantSettings(enabled)
  const clear = useClearArea()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  if (!enabled) return null
  const area = settings.data?.area ?? null

  const onConfirm = async () => {
    setError(null)
    try {
      await clear.mutateAsync()
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    setOpen(false)
    toast.show('已清除')
  }

  return (
    <section aria-labelledby={id}>
      <div className="sec-h"><Title k="savedArea" level="h" id={id} /></div>
      <Sensitive area="savedArea" className="plate">
        {settings.isError && <p className="pv-empty">{settings.error.message}</p>}
        {settings.data && !area && <p className="pv-empty">没有保存大致区域。</p>}
        {area && (
          <div className="area-row">
            <span>
              <b>{area.name}</b>
              {area.saved_at && <span className="t-cap">保存于 {todayISO(new Date(area.saved_at))}</span>}
            </span>
            <Button variant="quiet" size="sm" onPress={() => {
              setError(null)
              setOpen(true)
            }}
            >
              清除
            </Button>
          </div>
        )}
      </Sensitive>
      <ConfirmSheet
        isOpen={open} onClose={() => setOpen(false)} title="清除大致区域"
        quote={area ? <Sensitive area="savedArea"><b>{area.name}</b></Sensitive> : undefined}
        will={[
          { text: '附近餐厅不再提供“用已保存的区域”，下次要定位或输入地点。' },
          { text: '只删除这个大致区域，饮食记录与其他设置不变。' },
        ]}
        confirmLabel="清除" confirmVariant="danger" onConfirm={onConfirm} error={error}
      />
    </section>
  )
}
