import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { useNavigate } from 'react-router'
import type { TitleKey } from '../lib/titles'
import '../styles/components/header.css'
import { CoverButton } from './CoverButton'
import { useCover } from './cover'
import { Icon } from './Icon'
import { IconButton } from './IconButton'
import { Title } from './Title'

const VARIANT_CLASS = { big: 'hdr hdr-big', sub: 'hdr hdr-sub', chat: 'hdr' } as const

function scrollParent(el: HTMLElement): HTMLElement | null {
  for (let node = el.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node)
    if (overflowY === 'auto' || overflowY === 'scroll') return node
  }
  return null
}

/** 列表顶部的 1 像素哨兵离开视野时为真。IntersectionObserver 不可用时监听滚动并按帧合批。 */
function useStuck(sentinel: RefObject<HTMLDivElement | null>): boolean {
  const [stuck, setStuck] = useState(false)
  useEffect(() => {
    const el = sentinel.current
    if (!el) return undefined
    if (typeof IntersectionObserver !== 'undefined') {
      const observer = new IntersectionObserver((entries) => {
        const entry = entries[entries.length - 1]
        if (entry) setStuck(!entry.isIntersecting)
      })
      observer.observe(el)
      return () => observer.disconnect()
    }
    const parent = scrollParent(el)
    let frame = 0
    const measure = () => {
      frame = 0
      const top = parent ? parent.getBoundingClientRect().top : 0
      setStuck(el.getBoundingClientRect().bottom <= top)
    }
    const onScroll = () => {
      if (frame === 0) frame = requestAnimationFrame(measure)
    }
    document.addEventListener('scroll', onScroll, { capture: true, passive: true })
    frame = requestAnimationFrame(measure)
    return () => {
      document.removeEventListener('scroll', onScroll, true)
      if (frame !== 0) cancelAnimationFrame(frame)
    }
  }, [sentinel])
  return stuck
}

/**
 * 页头：滚动容器顶部的 position: sticky 页头（上沿加安全区）。静止时透明；列表一滚动，玻璃层（画在 ::before 上）
 * 只用透明度淡入。big 是一级页大标题，sub 是带返回键的二级页，chat 是对话页。
 * onRefresh 时右侧放刷新按钮（代替下拉刷新）；cover 时右上角放遮盖按钮（没有底部导航的二级页）。
 */
export function PageHeader({ titleKey, variant, back, caption, cover = false, onRefresh, children }: {
  titleKey: TitleKey
  variant: 'big' | 'sub' | 'chat'
  back?: true | string
  caption?: string
  cover?: boolean
  onRefresh?: () => void
  children?: ReactNode
}) {
  const navigate = useNavigate()
  const sentinel = useRef<HTMLDivElement>(null)
  const stuck = useStuck(sentinel)
  const { covered } = useCover()
  const goBack = () => {
    if (back === true) void navigate(-1)
    else if (back) void navigate(back)
  }
  return (
    <>
      <div ref={sentinel} className="top-sentinel" aria-hidden="true" />
      <header className={stuck ? 'top stuck' : 'top'}>
        <div className={VARIANT_CLASS[variant]}>
          <div className="hdr-l">
            {back && <IconButton icon="back" label="返回" back onPress={goBack} />}
            <Title k={titleKey} level={variant === 'big' ? 'display' : 'title'} as="h1" />
          </div>
          {(caption || onRefresh || cover) && (
            <div className="hdr-r">
              {caption && <span className="t-cap hdr-cap">{caption}</span>}
              {onRefresh && <IconButton icon="refresh" label="刷新" onPress={onRefresh} />}
              {cover && <CoverButton />}
            </div>
          )}
        </div>
        {covered && (
          <p className="cover-note">
            <Icon name="cover" size={18} />
            {cover ? '已遮盖，再点右上角恢复显示。' : '已遮盖，再点“遮盖”恢复显示。'}
          </p>
        )}
        {children}
      </header>
    </>
  )
}
