import { Icon } from './Icon'
import '../styles/components/field-input.css'

/** 表单级错误：后端说明原文，朱色写在面板里（不上玻璃），role="alert" 播报。没有错误时什么都不画。 */
export function FormError({ messages }: { messages: string[] }) {
  if (messages.length === 0) return null
  return (
    <div className="err form-err" role="alert">
      <Icon name="alert" size={18} />
      <span>{messages.map((message) => <span key={message} className="form-err-line">{message}</span>)}</span>
    </div>
  )
}
