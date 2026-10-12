import { useId } from 'react'
import '../styles/components/field-input.css'
import { Icon } from './Icon'

/**
 * 日期：原生 input type=date 铺满 .sel 圆角框（透明），点哪里都调起系统日期选择器；框里显示 YYYY-MM-DD 或占位文字。
 * 清空时回调 null。
 */
export function DateField({ label, value, onChange, min, max, placeholder }: {
  label: string
  value: string | null
  onChange: (value: string | null) => void
  min?: string
  max?: string
  placeholder?: string
}) {
  const id = useId()
  return (
    <div className="fld">
      <label className="fld-l" htmlFor={id}>{label}</label>
      <span className="sel">
        <span className={value ? 'n' : 'mute'} aria-hidden="true">{value ?? placeholder ?? ''}</span>
        <Icon name="cal" size={18} />
        <input
          id={id} type="date" value={value ?? ''} min={min} max={max}
          onChange={(event) => onChange(event.target.value || null)}
          onClick={(event) => {
            try {
              event.currentTarget.showPicker()
            } catch {
              // 不支持 showPicker 的浏览器点击输入框本身就会打开
            }
          }}
        />
      </span>
    </div>
  )
}
