import { useCallback, useId, useRef, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useDeleteAccount } from '../../app/useDeleteAccount'
import { Button } from '../../components/Button'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { PasswordField } from '../../components/PasswordField'
import { Sensitive } from '../../components/Sensitive'
import { useSheetHost } from '../../components/useSheetHost'
import { PASSWORD_INCORRECT } from '../../lib/contract'

/**
 * 删除账号与全部数据（敏感区 deleteAccount）：确认面板里重新输入登录密码，并勾选“我知道……不能恢复”，两样都有了才能删除。
 * 请求进行中面板锁住（ConfirmSheet：按钮停用、Esc 不关）；成功后清令牌、清缓存、回登录页并显示“已删除”（app/useDeleteAccount）。
 * 密码不对（password_incorrect）写在密码框下，其他错误写在按钮上方；关面板时密码一并清掉。
 */
export function DeleteAccount() {
  const id = useId()
  const remove = useDeleteAccount()
  const section = useRef<HTMLElement>(null)
  const host = useSheetHost<true>(useCallback(() => section.current, []))
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const wrongPassword = error?.code === PASSWORD_INCORRECT

  const onConfirm = async () => {
    setError(null)
    try {
      await remove.mutateAsync(password)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    } finally {
      remove.reset()
    }
  }

  return (
    <section ref={section} aria-labelledby={id} tabIndex={-1}>
      <div className="sec-h"><h2 className="sec-l" id={id}>删除账号与全部数据</h2></div>
      <Sensitive area="deleteAccount" className="plate pv-act">
        <p>立即删除账号与全部记录，不能恢复；需要留底请先导出。</p>
        <Button variant="danger-outline" size="sm" onPress={() => {
          setError(null)
          setPassword('')
          host.show(true)
        }}
        >
          删除账号
        </Button>
      </Sensitive>
      <ConfirmSheet
        key={host.nonce}
        isOpen={host.open} title="删除账号与全部数据"
        onClose={() => {
          setPassword('')
          host.close(host.nonce)
        }}
        will={[
          { text: '立即删除账号与全部数据：档案、经期、医嘱与原件、饮食、训练、对话、照片、模型服务与密钥、外部授权。', irreversible: true },
          { text: '这台设备随即退出登录，外部客户端的授权同时失效。' },
        ]}
        ack="我知道删除后所有数据立即清除、不能恢复"
        confirmLabel="删除账号" confirmVariant="danger" confirmDisabled={password === ''}
        onConfirm={onConfirm} error={wrongPassword ? null : error}
      >
        <PasswordField
          label="登录密码" value={password} onChange={setPassword} autoComplete="current-password"
          hint="为确认是你本人，请再输入一次登录密码。"
          error={wrongPassword && error ? <>{error.message}<small>错误码 {error.code}</small></> : undefined}
        />
      </ConfirmSheet>
    </section>
  )
}
