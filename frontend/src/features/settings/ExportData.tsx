import { useCallback, useId, useRef, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useExportData } from '../../api/hooks/account'
import { Button } from '../../components/Button'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { PasswordField } from '../../components/PasswordField'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import { useSheetHost } from '../../components/useSheetHost'
import { PASSWORD_INCORRECT } from '../../lib/contract'

// 点下链接之后浏览器才开始读这个对象地址：稍后再释放（立即释放时部分浏览器会下载失败）
const REVOKE_DELAY_MS = 1000

/** 用对象地址触发保存；文件名是后端生成的（不含用户输入），用后释放地址，链接不留在页面上 */
function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_DELAY_MS)
}

/**
 * 导出我的数据（敏感区 exportData）：面板里说明压缩包里有什么、密钥只含掩码，重新输入登录密码后下载。
 * 密码只在请求体里（不进地址与浏览器存储），每次提交后变更即离开缓存；成功后清空密码、关面板、轻提示“已开始下载”。
 * 密码不对（password_incorrect）写在密码框下，其他错误写在按钮上方。
 */
export function ExportData() {
  const id = useId()
  const exportData = useExportData()
  const toast = useToast()
  const section = useRef<HTMLElement>(null)
  const host = useSheetHost<true>(useCallback(() => section.current, []))
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const wrongPassword = error?.code === PASSWORD_INCORRECT

  const close = () => {
    setPassword('')
    host.close(host.nonce)
  }

  const onConfirm = async () => {
    setError(null)
    try {
      const { blob, filename } = await exportData.mutateAsync(password)
      saveBlob(blob, filename)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    } finally {
      exportData.reset()
    }
    close()
    toast.show('已开始下载')
  }

  return (
    <section ref={section} aria-labelledby={id} tabIndex={-1}>
      <div className="sec-h"><h2 className="sec-l" id={id}>导出我的数据</h2></div>
      <Sensitive area="exportData" className="plate pv-act">
        <p>把你的全部记录打包成一个压缩包下载，留作备份或带走。</p>
        <Button variant="quiet" size="sm" onPress={() => {
          setError(null)
          setPassword('')
          host.show(true)
        }}
        >
          导出我的数据
        </Button>
      </Sensitive>
      <ConfirmSheet
        key={host.nonce}
        isOpen={host.open} onClose={close} title="导出我的数据"
        will={[
          { text: '下载一个压缩包：档案、经期、医嘱、饮食、训练、对话、拍照识别、模型服务、授权与同意记录各一份数据文件，医嘱原件与保留的照片，以及一份中文说明。' },
          { text: '模型服务的密钥只含掩码，不导出原文；也不含你的密码。' },
        ]}
        confirmLabel="导出并下载" confirmDisabled={password === ''} onConfirm={onConfirm} error={wrongPassword ? null : error}
      >
        <PasswordField
          label="登录密码" value={password} onChange={setPassword} autoComplete="current-password"
          hint="为确认是你本人，请再输入一次登录密码。" error={wrongPassword && error ? <>{error.message}<small>错误码 {error.code}</small></> : undefined}
        />
      </ConfirmSheet>
    </section>
  )
}
