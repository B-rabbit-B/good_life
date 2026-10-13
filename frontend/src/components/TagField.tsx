import { useId, useLayoutEffect, useRef, useState } from 'react'
import { Button as AriaButton, Label, Tag, TagGroup, TagList } from 'react-aria-components'
import '../styles/components/field-input.css'
import { Icon } from './Icon'

/**
 * 标签的删除键。React Aria 默认用 aria-labelledby 把删除键与整行一起命名（读作“移除清淡 清淡”），
 * 这里把 aria-labelledby 改指向一段只含“移除清淡”的隐藏文字。
 */
function RemoveButton({ tag }: { tag: string }) {
  const nameId = useId()
  const name = `移除${tag}`
  return (
    <AriaButton slot="remove" aria-label={name} aria-labelledby={nameId}>
      <span id={nameId} hidden>{name}</span>
      <Icon name="x" />
    </AriaButton>
  )
}

/** 可移除标签（饮食偏好、忌口）：胶囊，删除键 44；“添加”展开一个胶囊输入框，回车加入（React Aria TagGroup）。error 是后端的说明原文，
 * 写在列表下方并用 aria-describedby 与 aria-invalid 关联到标签列表。 */
export function TagField({ label, tags, onChange, addLabel = '添加', error }: {
  label: string
  tags: string[]
  onChange: (tags: string[]) => void
  addLabel?: string
  error?: string
}) {
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState('')
  const errorId = useId()
  const listRef = useRef<HTMLDivElement>(null)
  // 出错时标在标签列表（grid）上：React Aria 的标签列表挂载后不再更新 aria-describedby，也不转发 aria-invalid，
  // 所以直接写在元素上（这个组件不给标签组说明文字，React Aria 自己不会写 aria-describedby）
  useLayoutEffect(() => {
    const list = listRef.current
    if (!list) return
    if (error) {
      list.setAttribute('aria-invalid', 'true')
      list.setAttribute('aria-describedby', errorId)
    } else {
      list.removeAttribute('aria-invalid')
      list.removeAttribute('aria-describedby')
    }
  }, [error, errorId])
  const finish = (keep: boolean) => {
    const text = draft.trim()
    if (keep && text && !tags.includes(text)) onChange([...tags, text])
    setDraft('')
    setAdding(false)
  }
  return (
    <TagGroup className="fld" onRemove={(keys) => onChange(tags.filter((tag) => !keys.has(tag)))}>
      <Label className="fld-l">{label}</Label>
      <div className="tags">
        <TagList ref={listRef} className="tags">
          {tags.map((tag) => (
            <Tag key={tag} id={tag} textValue={tag} className="tag">
              {tag}
              <RemoveButton tag={tag} />
            </Tag>
          ))}
        </TagList>
        {adding ? (
          <input
            className="tag-in" aria-label={`${addLabel}${label}`} value={draft} autoFocus
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => finish(true)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                finish(true)
              } else if (event.key === 'Escape') {
                finish(false)
              }
            }}
          />
        ) : (
          <AriaButton className="tag add" onPress={() => setAdding(true)}>{addLabel}</AriaButton>
        )}
      </div>
      {error && (
        <div id={errorId} className="err">
          <Icon name="alert" size={18} />
          <span>{error}</span>
        </div>
      )}
    </TagGroup>
  )
}
