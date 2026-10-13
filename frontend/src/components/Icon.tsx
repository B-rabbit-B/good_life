import type { ReactNode } from 'react'

// 路径照抄设计稿 index.html 第 888 至 915 行：24 格、1.5 线宽、圆头圆角
const PATHS = {
  camera: <><path d="M3.5 8.5h3.2L8.3 6h7.4l1.6 2.5h3.2V19h-17z" /><circle cx="12" cy="13.2" r="3.4" /></>,
  image: <><rect x="3.5" y="5" width="17" height="14" rx="2.5" /><path d="M3.5 16l4.8-4.6 4 3.8 2.6-2.4 5.6 5.2" /><circle cx="15.6" cy="9.4" r="1.4" /></>,
  send: <path d="M12 19V5.5M6.5 11 12 5.5l5.5 5.5" />,
  back: <path d="M14.5 5.5 8 12l6.5 6.5" />,
  down: <path d="M6.5 9.5 12 15l5.5-5.5" />,
  right: <path d="M9.5 6.5 15 12l-5.5 5.5" />,
  cover: <><path d="M4 4l16 16" /><path d="M10.4 6.2A9.6 9.6 0 0 1 12 6c4.8 0 8 4.2 9 6-.5.9-1.5 2.3-3 3.6M6.5 7.7C4.7 8.9 3.5 10.8 3 12c1 1.8 4.2 6 9 6 1.5 0 2.9-.4 4.1-1" /><path d="M9.9 10a3 3 0 0 0 4.1 4.1" /></>,
  eye: <><path d="M3 12c1-1.8 4.2-6 9-6s8 4.2 9 6c-1 1.8-4.2 6-9 6s-8-4.2-9-6z" /><circle cx="12" cy="12" r="3" /></>,
  pin: <><path d="M12 20.5s-6.3-5.8-6.3-10.6a6.3 6.3 0 0 1 12.6 0c0 4.8-6.3 10.6-6.3 10.6z" /><circle cx="12" cy="9.9" r="2.2" /></>,
  nav: <path d="M4.5 11.2 19.5 4.5l-6.7 15-1.9-5.9z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="M5 12.5l4.3 4.3L19 7.3" />,
  x: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,
  alert: <><path d="M12 4.2 20.8 19.5H3.2z" /><path d="M12 10v4.4M12 16.9v.3" /></>,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.3M12 7.9v.3" /></>,
  phone: <path d="M6.2 4h2.9l1.4 3.9-2 1.3a10.4 10.4 0 0 0 6.3 6.3l1.3-2 3.9 1.4v2.9a1.7 1.7 0 0 1-1.9 1.7A15.6 15.6 0 0 1 4.5 5.9 1.7 1.7 0 0 1 6.2 4z" />,
  search: <><circle cx="11" cy="11" r="6" /><path d="M15.5 15.5 20 20" /></>,
  refresh: <><path d="M19 12a7 7 0 1 1-2.1-5" /><path d="M19 4.5V8h-3.5" /></>,
  lock: <><rect x="5" y="10.5" width="14" height="9.5" rx="2.5" /><path d="M8.2 10.5V8a3.8 3.8 0 0 1 7.6 0v2.5" /></>,
  edit: <><path d="M5 19h3.6L18.8 8.8l-3.6-3.6L5 15.4z" /><path d="M13.6 6.8l3.6 3.6" /></>,
  trash: <path d="M4.5 7h15M9.5 7V4.8h5V7M6.5 7l.9 12.5h9.2L17.5 7" />,
  cal: <><rect x="4" y="5.5" width="16" height="14.5" rx="2.5" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  doc: <><path d="M6.5 3.5h7.5l4 4v13h-11.5z" /><path d="M14 3.5V7.5h4M9.5 12h5M9.5 15.5h5" /></>,
  bowl: <><path d="M3.5 11.5h17a8.5 8.5 0 0 1-17 0z" /><path d="M8 20h8M9 8.5c0-1.5 1-1.5 1-3M13 8.5c0-1.5 1-1.5 1-3" /></>,
} satisfies Record<string, ReactNode>

export type IconName = keyof typeof PATHS
export const ICON_NAMES = Object.keys(PATHS) as IconName[]

const SIZE_CLASS = { 18: ' ic-s', 20: ' ic-m', 24: '' } as const

/** 线性图标，内联 SVG，对读屏隐藏；放在玻璃上时线宽 1.7（onGlass，或在 .chrome 与吸顶页头里自动加粗）。 */
export function Icon({ name, size = 24, onGlass = false }: { name: IconName; size?: 18 | 20 | 24; onGlass?: boolean }) {
  return (
    <svg
      className={`ic${SIZE_CLASS[size]}${onGlass ? ' ic-g' : ''}`}
      viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
