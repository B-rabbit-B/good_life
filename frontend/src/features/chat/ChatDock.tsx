import { useLayoutEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import type { Capabilities } from '../../api/types'
import { navItems } from '../../app/nav'
import { BottomNav } from '../../components/BottomNav'
import { Icon } from '../../components/Icon'
import { ShellPortal } from '../../components/ShellPortal'
import { Surface } from '../../components/Surface'
import { MESSAGE_MAX_CHARS } from '../../lib/contract'
import { setPendingPhoto } from '../../lib/photoHandoff'
import '../../styles/components/chat.css'
import { useVisualViewportInset } from './useVisualViewportInset'

/** 输入框的编号：开场卡片收起而页头没有待处理条时，焦点回到这里 */
export const COMPOSER_ID = 'chat-composer'
/** 底座实际高度的 CSS 变量（AppShell 用它算对话页滚动容器的底部留白） */
export const DOCK_HEIGHT_VAR = '--dock-h'
const PHOTO_TYPES = 'image/jpeg,image/png,image/webp'

function quickActions(caps: Capabilities): { to: string; label: string }[] {
  return [
    ...(caps.nutrition ? [{ to: '/restaurants', label: '附近吃什么' }, { to: '/records/meals/new', label: '记一餐' }] : []),
    ...(caps.medical ? [{ to: '/health/medical', label: '看医嘱' }] : []),
  ]
}

/**
 * 对话底座：一块活玻璃，渲染进 #shell-root。上面是快捷操作胶囊（最后一条助手消息是就医提示时整行隐藏），
 * 中间是拍照、相册、多行输入框（Enter 发送、Shift+Enter 换行，输入法组字时不发送）与发送键，下面嵌着底部导航。
 * 选了照片就交给拍照识别页（/photos/new）。ready 为假（会话列表还没取到）时不能发送，免得新建一个会话把历史挡掉。
 * 底座的实际高度写进根节点的 --dock-h，滚动容器的底部留白跟着它（多行输入时底座变高，最后一条仍能滚出来）。
 */
export function ChatDock({ caps, onSend, busy, ready, hideQuickActions }: {
  caps: Capabilities
  onSend: (text: string) => void
  busy: boolean
  ready: boolean
  hideQuickActions: boolean
}) {
  const navigate = useNavigate()
  const [draft, setDraft] = useState('')
  const input = useRef<HTMLTextAreaElement>(null)
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  useVisualViewportInset()

  useLayoutEffect(() => {
    const slab = input.current?.closest<HTMLElement>('.slab')
    if (!slab) return undefined
    const root = document.documentElement
    const measure = () => root.style.setProperty(DOCK_HEIGHT_VAR, `${Math.round(slab.getBoundingClientRect().height)}px`)
    measure()
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null
    observer?.observe(slab)
    return () => {
      observer?.disconnect()
      root.style.removeProperty(DOCK_HEIGHT_VAR)
    }
  }, [])

  // 多行时输入框往上长（最多约 4 行，再多在框里滚动）
  useLayoutEffect(() => {
    const el = input.current
    if (!el) return
    el.style.height = ''
    // 空的时候按一行算：放不下的占位文字只截短，不把框撑高
    if (draft !== '' && el.scrollHeight > el.clientHeight) el.style.height = `${el.scrollHeight}px`
  }, [draft])

  const text = draft.trim()
  const canSend = text !== '' && !busy && ready
  const submit = () => {
    if (!canSend) return
    onSend(text)
    setDraft('')
    // 发送键随即变成不可用，焦点留在输入框里，不丢
    input.current?.focus()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    submit()
  }
  const onPhoto = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setPendingPhoto(file)
    void navigate('/photos/new')
  }

  const quick = hideQuickActions ? [] : quickActions(caps)
  return (
    <ShellPortal>
      <Surface tier="chrome" className="slab">
        {quick.length > 0 && (
          <div className="qa" role="group" aria-label="快捷操作">
            {quick.map((action) => <Link key={action.to} to={action.to} data-hit44="">{action.label}</Link>)}
          </div>
        )}
        <div className="cmp">
          {caps.nutrition && (
            <>
              <button type="button" className="ibtn" aria-label="拍照" onClick={() => camera.current?.click()}>
                <Icon name="camera" />
              </button>
              <input ref={camera} type="file" accept={PHOTO_TYPES} capture="environment" tabIndex={-1} onChange={onPhoto} />
              <button type="button" className="ibtn" aria-label="从相册选图" onClick={() => gallery.current?.click()}>
                <Icon name="image" />
              </button>
              <input ref={gallery} type="file" accept={PHOTO_TYPES} tabIndex={-1} onChange={onPhoto} />
            </>
          )}
          <textarea
            ref={input} id={COMPOSER_ID} className="cmp-in" rows={1} maxLength={MESSAGE_MAX_CHARS}
            aria-label="给助手发消息" placeholder="说点什么，或拍一张饭菜" enterKeyHint="send"
            value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onKeyDown}
          />
          <button type="button" className="send" aria-label="发送" disabled={!canSend} onClick={submit}>
            <Icon name="send" />
          </button>
        </div>
        <BottomNav items={navItems(caps)} embedded />
      </Surface>
    </ShellPortal>
  )
}
