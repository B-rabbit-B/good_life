import { useCallback, useId, useRef, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useClearConversations } from '../../api/hooks/account'
import { Button } from '../../components/Button'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import { useSheetHost } from '../../components/useSheetHost'

/**
 * 清空对话历史（敏感区 clearChat）：确认面板写明同时清掉开场问候、其他数据不受影响，必须勾选“不能恢复”。
 * 成功后对话与开场的缓存随即丢掉（api/hooks/account 的 useClearConversations），轻提示“已清空”。
 */
export function ClearConversations() {
  const id = useId()
  const clear = useClearConversations()
  const toast = useToast()
  const section = useRef<HTMLElement>(null)
  const host = useSheetHost<true>(useCallback(() => section.current, []))
  const [error, setError] = useState<ApiError | null>(null)

  const onConfirm = async () => {
    setError(null)
    try {
      await clear.mutateAsync()
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    host.close(host.nonce)
    toast.show('已清空')
  }

  return (
    <section ref={section} aria-labelledby={id} tabIndex={-1}>
      <div className="sec-h"><h2 className="sec-l" id={id}>清空对话历史</h2></div>
      <Sensitive area="clearChat" className="plate pv-act">
        <p>删除与智能体的全部对话，连同每天的开场问候。</p>
        <Button variant="danger-outline" size="sm" onPress={() => {
          setError(null)
          host.show(true)
        }}
        >
          清空对话历史
        </Button>
      </Sensitive>
      <ConfirmSheet
        key={host.nonce}
        isOpen={host.open} onClose={() => host.close(host.nonce)} title="清空对话历史"
        will={[
          { text: '删除全部对话与其中的工具结果，同时清掉开场问候的记录。', irreversible: true },
          { text: '档案、饮食、训练、经期、医嘱、偏好记忆与其他设置不受影响。' },
        ]}
        ack="我知道清空后不能恢复"
        confirmLabel="清空" confirmVariant="danger" onConfirm={onConfirm} error={error}
      />
    </section>
  )
}
