import type { HttpHandler } from 'msw'
import { coreHandlers } from './core'

// 各模块的默认处理器放在同目录按模块分的文件里，在这里汇总
export const handlers: HttpHandler[] = [...coreHandlers()]
