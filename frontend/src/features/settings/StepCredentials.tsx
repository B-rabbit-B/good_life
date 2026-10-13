import type { ReactNode, RefObject } from 'react'
import type { ProviderOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { PasswordField } from '../../components/PasswordField'
import { SelectField } from '../../components/SelectField'
import { TextField } from '../../components/TextField'
import type { StepStatus } from './flowReducer'
import { KeyMask } from './KeyMask'

/** 说明原文紧贴着写错误码（设计稿 10b） */
export function ErrorText({ message, code }: { message?: string; code?: string }): ReactNode {
  return <>{message}{code && <small>错误码 {code}</small>}</>
}

const KEY_HINT = '保存后只显示掩码，原文无法再查看。'

export interface CredentialsForm {
  type: string
  name: string
  baseUrl: string
  apiKey: string
}

/**
 * 第 1 步“填写地址与密钥”：类型（预设或自定义）、名称、服务地址、密钥。保存成功后只显示地址与后端给的密钥掩码；
 * 出错时只给出错的字段 2 像素朱色内描边，说明原文与错误码紧贴在下面。已创建的服务不能改类型。
 */
export function StepCredentials({ status, saved, form, types, onChange, onSubmit, pending, urlBox }: {
  status: StepStatus
  saved: ProviderOut | null
  form: CredentialsForm
  types: { value: string; label: string }[]
  onChange: (form: CredentialsForm) => void
  onSubmit: () => void
  pending: boolean
  /** 包着服务地址输入框的元素：“修改地址”回到这里时把焦点放进去 */
  urlBox: RefObject<HTMLDivElement | null>
}) {
  if (status.state === 'ok' && saved) {
    return (
      <div className="fs-b fs-sum">
        <span className="url">{saved.base_url}</span>
        <KeyMask hint={saved.key_hint} />
      </div>
    )
  }
  const bad = status.state === 'bad'
  const errorFor = (field: StepStatus['field']) =>
    bad && status.field === field ? <ErrorText message={status.message} code={status.code} /> : undefined
  const set = (patch: Partial<CredentialsForm>) => onChange({ ...form, ...patch })
  const keyError = errorFor('api_key')
  const ready = form.name.trim() !== '' && form.baseUrl.trim() !== '' && (saved !== null || form.apiKey.trim() !== '')
  return (
    <div className="fs-form">
      <SelectField label="类型" value={form.type} options={types} onChange={(type) => set({ type })} isDisabled={saved !== null} />
      <TextField label="名称" value={form.name} onChange={(name) => set({ name })} maxLength={50} autoComplete="off" error={errorFor('name')} />
      <div ref={urlBox}>
        <TextField
          label="服务地址" value={form.baseUrl} onChange={(baseUrl) => set({ baseUrl })} type="url" inputMode="url"
          maxLength={300} autoComplete="off" error={errorFor('base_url')}
        />
      </div>
      <PasswordField
        label="密钥" value={form.apiKey} onChange={(apiKey) => set({ apiKey })} autoComplete="new-password" showLabel="显示密钥"
        hint={keyError ? undefined : KEY_HINT} error={keyError}
      />
      {/* 密钥出错时说明紧贴在框下，提示写在说明后面（设计稿 10b） */}
      {keyError && <p className="fld-h">{KEY_HINT}</p>}
      {bad && !status.field && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span><ErrorText message={status.message} code={status.code} /></span>
        </div>
      )}
      <div className="fs-go">
        <Button variant="primary" block isPending={pending} isDisabled={!ready} onPress={onSubmit}>
          {bad ? '重新保存并获取模型' : '保存并获取模型'}
        </Button>
      </div>
    </div>
  )
}
