import { useState } from 'react'
import { Button as AriaButton, Label, Tag, TagGroup, TagList } from 'react-aria-components'
import '../styles/components/field-input.css'
import { Icon } from './Icon'

/** 可移除标签（饮食偏好、忌口）：胶囊，删除键 44；“添加”展开一个胶囊输入框，回车加入（React Aria TagGroup）。 */
export function TagField({ label, tags, onChange, addLabel = '添加' }: {
  label: string
  tags: string[]
  onChange: (tags: string[]) => void
  addLabel?: string
}) {
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState('')
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
        <TagList className="tags">
          {tags.map((tag) => (
            <Tag key={tag} id={tag} textValue={tag} className="tag">
              {tag}
              <AriaButton slot="remove" aria-label={`移除${tag}`}><Icon name="x" /></AriaButton>
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
    </TagGroup>
  )
}
