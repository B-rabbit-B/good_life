import { TITLES, type TitleKey } from '../lib/titles'

export type TitleLevel = 'display' | 'title' | 'h' | 'state'

const LEVELS = {
  display: { className: 't-display', tag: 'h1' },
  title: { className: 't-title', tag: 'h2' },
  h: { className: 't-h', tag: 'h3' },
  state: { className: 'st-h', tag: 'h2' },
} as const

/**
 * 宋体标题：全站唯一输出 t-display、t-title、t-h、st-h 类名的地方。
 * 文字只能是 lib/titles.json 里写死的标题，宋体子集按它生成；来自后端或模型的文字一律用黑体。
 */
export function Title({ k, level, as, id }: { k: TitleKey; level: TitleLevel; as?: 'h1' | 'h2' | 'h3'; id?: string }) {
  const { className, tag } = LEVELS[level]
  const Tag = as ?? tag
  return <Tag className={className} id={id}>{TITLES[k]}</Tag>
}
