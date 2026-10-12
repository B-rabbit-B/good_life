import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Dialog, Modal, ModalOverlay } from 'react-aria-components'
import type { TitleKey } from '../lib/titles'
import '../styles/components/sheet.css'
import { useSheetGlass } from './glass/GlassModeProvider'
import { shellRoot } from './ShellPortal'
import { Title } from './Title'

// 滑入 320 毫秒；万一 transitionend 没来（例如元素被隐藏），到时也打开磨砂
const ENTER_FALLBACK_MS = 600

type Phase = 'pre' | 'entering' | 'open'

function SheetBody({ titleKey, children, footer }: { titleKey: TitleKey; children: ReactNode; footer?: ReactNode }) {
  const titleId = useId()
  const dialogRef = useRef<HTMLElement>(null)
  const [phase, setPhase] = useState<Phase>('pre')
  // 挂在面板内容上而不是 isOpen 上：React Aria 等遮罩层的退出动画结束才卸载内容，
  // 所以关闭的 200 毫秒里外壳仍不模糊，轻提示也不出现（同屏模糊层不超预算）
  useSheetGlass(true)

  // 第一帧画在起点（实色、在屏幕下面、遮罩透明），下一帧去掉起点让过渡开始；滑入结束后去掉 data-entering，磨砂淡入
  useLayoutEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return undefined
    const frame = requestAnimationFrame(() => setPhase((p) => (p === 'pre' ? 'entering' : p)))
    const onEnd = (event: TransitionEvent) => {
      if (event.target === dialog) setPhase('open')
    }
    dialog.addEventListener('transitionend', onEnd)
    const fallback = setTimeout(() => setPhase('open'), ENTER_FALLBACK_MS)
    return () => {
      cancelAnimationFrame(frame)
      dialog.removeEventListener('transitionend', onEnd)
      clearTimeout(fallback)
    }
  }, [])

  // 打开时焦点进入标题（关闭后由 React Aria 还给触发处）
  useEffect(() => {
    const title = document.getElementById(titleId)
    if (!title) return
    title.setAttribute('tabindex', '-1')
    title.focus()
  }, [titleId])

  return (
    <>
      <div className="scrim" data-pre={phase === 'pre' ? '' : undefined} />
      <Modal className="sheet-wrap">
        <Dialog
          ref={dialogRef}
          className="sheet"
          aria-labelledby={titleId}
          data-tier="sheet"
          data-pre={phase === 'pre' ? '' : undefined}
          data-entering={phase === 'open' ? undefined : ''}
        >
          <Title k={titleKey} level="title" as="h2" id={titleId} />
          {children}
          {footer && <div className="sheet-foot">{footer}</div>}
        </Dialog>
      </Modal>
    </>
  )
}

/**
 * 底部面板：React Aria ModalOverlay、Modal、Dialog（焦点锁定、背景滚动锁定、Esc 关闭）。
 * 遮罩 --scrim 只压暗不模糊；没有拖动把手，只能用 Esc 或按钮关闭。滑入时是实色（data-entering），
 * 停稳后磨砂只过渡底色淡入；从打开到退出动画结束，根节点带 data-sheet-open，遮罩下的外壳关模糊、轻提示隐藏。
 */
export function Sheet({ isOpen, onClose, titleKey, children, footer }: {
  isOpen: boolean
  onClose: () => void
  titleKey: TitleKey
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      isDismissable={false}
      className="sheet-layer"
      UNSTABLE_portalContainer={shellRoot()}
    >
      <SheetBody titleKey={titleKey} footer={footer}>{children}</SheetBody>
    </ModalOverlay>
  )
}
