import { useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useDeleteProvider } from '../../api/hooks/llmSettings'
import type { ProviderOut } from '../../api/types'
import { ConfirmSheet } from '../../components/ConfirmSheet'

/**
 * 删除一个模型服务的确认面板：写明该服务的模型、用途分配与密钥会一起删除；确认后失效全部模型服务的缓存（['llm']）。
 * 面板由模型服务页持有（行删掉后面板仍要能正常退场），成功后由 onDeleted 关面板与轻提示。
 */
export function DeleteProviderSheet({ provider, isOpen, onClose, onDeleted }: {
  provider: ProviderOut | null
  isOpen: boolean
  onClose: () => void
  onDeleted: () => void
}) {
  const remove = useDeleteProvider()
  const [error, setError] = useState<ApiError | null>(null)

  const onConfirm = async () => {
    if (!provider) return
    setError(null)
    try {
      await remove.mutateAsync(provider.id)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    onDeleted()
  }

  return (
    <ConfirmSheet
      isOpen={isOpen} onClose={onClose} title="删除这个模型服务"
      quote={provider ? <><b>{provider.name}</b><div className="url">{provider.base_url}</div></> : undefined}
      will={[
        { text: '同时删除这个服务下的全部模型与用途分配，保存的密钥一并删除。', irreversible: true },
        { text: '用到它的用途变成“未设置”，需要时重新添加服务并分配。' },
      ]}
      confirmLabel="删除" confirmVariant="danger" onConfirm={onConfirm} error={error}
    />
  )
}
