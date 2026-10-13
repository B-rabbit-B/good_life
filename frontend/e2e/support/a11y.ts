// 自写的版式与无障碍断言（不用 axe-core：它是 MPL-2.0）。
import { expect, type Page } from '@playwright/test'
import {
  compareSensitiveAreas, SENSITIVE_AREA_ATTR, SENSITIVE_PAGE_ATTR, UNNAMED_AREA, type SensitiveArea,
} from '../../src/app/sensitiveAreas'

const INTERACTIVE = [
  'a', 'button', 'input', 'select', 'textarea',
  ...['button', 'tab', 'radio', 'checkbox', 'switch', 'slider', 'link'].map((role) => `[role="${role}"]`),
].join(', ')
const MIN_TARGET = 44
const HIT44_VISUAL_MIN = 36
const HIT44_EXTEND = 4
const COVER_NAME = '遮盖敏感内容'
const UNCOVER_NAME = '已遮盖，点按恢复显示'

/**
 * 可见的可交互元素宽高都不小于 44；带 data-hit44 的允许视觉高 36，但 ::before 要上下各外扩至少 4 像素。
 * 只给读屏用的隐藏原生控件（React Aria 的单选、勾选、开关）改量包着它的 label，标签同样不小于 44。
 */
export async function expectTouchTargets(page: Page): Promise<void> {
  const problems = await page.evaluate(
    ({ selector, min, hitVisualMin, extend }) => {
      const px = (value: string) => (value.endsWith('px') ? Number.parseFloat(value) : Number.NaN)
      const describe = (el: Element) => {
        const label = el.getAttribute('aria-label') ?? el.textContent?.trim().slice(0, 20) ?? ''
        return `<${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}> ${label}`
      }
      // React Aria 把原生单选框、勾选框与开关放在一个 1 × 1、overflow:hidden 的隐藏外层里（控件本身仍是原生大小）
      const insideVisuallyHidden = (el: Element) => {
        for (let node = el.parentElement, depth = 0; node && depth < 3; node = node.parentElement, depth += 1) {
          const r = node.getBoundingClientRect()
          if (r.width <= 1 && r.height <= 1 && getComputedStyle(node).overflow === 'hidden') return true
        }
        return false
      }
      const out: string[] = []
      const measuredLabels = new Set<Element>()
      for (const el of Array.from(document.querySelectorAll(selector))) {
        if (el instanceof HTMLInputElement && el.type === 'hidden') continue
        const style = getComputedStyle(el)
        const rect = el.getBoundingClientRect()
        if (style.display === 'none' || style.visibility === 'hidden') continue
        // 只给读屏用的隐藏控件（1 像素以内，或在 1 × 1 的隐藏外层里）本身不算触控目标：
        // 手指点的是包着它的可见标签（.opt、.chk、.tg-row），所以改为量这个标签
        if (rect.width <= 1 || rect.height <= 1 || insideVisuallyHidden(el)) {
          // 只给读屏光标用、不进 Tab 顺序的隐藏按钮（React Aria 月历末尾的“下一页”）不是触控目标
          if (el instanceof HTMLButtonElement && el.getAttribute('aria-label') && el.tabIndex === -1) continue
          const label = el.closest('label')
          if (!label) {
            out.push(`${describe(el)}：隐藏的控件没有可点的可见标签`)
            continue
          }
          if (measuredLabels.has(label)) continue
          measuredLabels.add(label)
          const box = label.getBoundingClientRect()
          if (box.width < min || box.height < min) {
            out.push(`${describe(el)} 的标签 <label${label.className ? `.${label.className.split(' ').join('.')}` : ''}>：`
              + `${box.width.toFixed(1)}×${box.height.toFixed(1)}`)
          }
          continue
        }
        if (!el.hasAttribute('data-hit44')) {
          if (rect.width < min || rect.height < min) {
            out.push(`${describe(el)}：${rect.width.toFixed(1)}×${rect.height.toFixed(1)}`)
          }
          continue
        }
        const before = getComputedStyle(el, '::before')
        const top = px(before.top)
        const bottom = px(before.bottom)
        const left = Number.isNaN(px(before.left)) ? 0 : Math.min(0, px(before.left))
        const right = Number.isNaN(px(before.right)) ? 0 : Math.min(0, px(before.right))
        const width = rect.width - left - right
        const ok = before.content !== 'none' && rect.height >= hitVisualMin && top <= -extend && bottom <= -extend
          && width >= min
        if (!ok) {
          out.push(`${describe(el)}（data-hit44）：视觉 ${rect.width.toFixed(1)}×${rect.height.toFixed(1)}，`
            + `::before top ${before.top} bottom ${before.bottom} content ${before.content}`)
        }
      }
      return out
    },
    { selector: INTERACTIVE, min: MIN_TARGET, hitVisualMin: HIT44_VISUAL_MIN, extend: HIT44_EXTEND },
  )
  expect(problems, '触控目标小于 44').toEqual([])
}

/** 全部可见文字节点的计算字号不小于 min 像素。 */
export async function expectMinFontSize(page: Page, min: number): Promise<void> {
  const problems = await page.evaluate((minSize) => {
    const out: string[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim() ?? ''
      const parent = node.parentElement
      if (!text || !parent) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const visible = Array.from(range.getClientRects()).some((r) => r.width > 0 && r.height > 0)
      const style = getComputedStyle(parent)
      if (!visible || style.visibility === 'hidden') continue
      const size = Number.parseFloat(style.fontSize)
      if (size < minSize) out.push(`${size}px：${text.slice(0, 20)}`)
    }
    return out
  }, min)
  expect(problems, `字号小于 ${min} 像素`).toEqual([])
}

/** 页面没有横向滚动。 */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(scrollWidth, '页面出现横向滚动').toBeLessThanOrEqual(clientWidth)
}

async function sensitiveState(page: Page) {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-sensitive]')).map((el) => {
      const after = getComputedStyle(el, '::after')
      return {
        ariaHidden: el.getAttribute('aria-hidden'),
        inert: el.hasAttribute('inert'),
        content: after.content,
        backgroundColor: after.backgroundColor,
        backgroundImage: after.backgroundImage,
        filter: after.filter,
        backdropFilter: after.backdropFilter || 'none',
        webkitBackdropFilter: (after as CSSStyleDeclaration & { webkitBackdropFilter?: string }).webkitBackdropFilter
          || 'none',
      }
    }),
  )
}

const opaque = (color: string) => {
  const match = color.match(/rgba?\(([^)]+)\)/)
  if (!match?.[1]) return false
  const parts = match[1].split(/[\s,/]+/).filter(Boolean)
  return parts.length < 4 || Number.parseFloat(parts[3] ?? '1') === 1
}

/**
 * 点遮盖后每个 [data-sensitive] 都有 aria-hidden="true" 与 inert，::after 是不透明斜纹且没有任何滤镜；
 * 连按 Tab 焦点不会进入敏感区；再点恢复。
 * Tab 这一步只在 Chromium 里断言：WebKit 默认 Tab 会跳过链接与按钮，连按 Tab 本来就进不去，断言没有意义；
 * 在 WebKit 里由上面的 inert 与 aria-hidden 属性检查代替。
 */
export async function expectCoverWorks(page: Page): Promise<void> {
  expect(await page.locator('[data-sensitive]').count(), '页面上没有敏感区').toBeGreaterThan(0)
  await page.getByRole('button', { name: COVER_NAME, exact: true }).first().click()
  await expect.poll(async () => (await sensitiveState(page)).every((s) => s.ariaHidden === 'true' && s.inert)).toBe(true)

  for (const state of await sensitiveState(page)) {
    expect(state.content, '遮盖层 ::after 没有内容').not.toBe('none')
    expect(opaque(state.backgroundColor), `遮盖层底色不是不透明的：${state.backgroundColor}`).toBe(true)
    expect(state.backgroundImage, '遮盖层不是斜纹').toContain('linear-gradient')
    expect([state.filter, state.backdropFilter, state.webkitBackdropFilter]).toEqual(['none', 'none', 'none'])
  }

  if (page.context().browser()?.browserType().name() === 'chromium') {
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
    for (let i = 0; i < 40; i += 1) {
      await page.keyboard.press('Tab')
      const inside = await page.evaluate(() => document.activeElement?.closest('[data-sensitive]') != null)
      expect(inside, '焦点进入了被遮盖的敏感区').toBe(false)
    }
  }

  await page.getByRole('button', { name: UNCOVER_NAME, exact: true }).first().click()
  await expect.poll(async () => (await sensitiveState(page)).every((s) => s.ariaHidden !== 'true' && !s.inert))
    .toBe(true)
}

/** 外壳（[data-tier="chrome"]）的模糊：on 时含 blur(16px)，off 时为 none。 */
export async function expectGlass(page: Page, on: boolean): Promise<void> {
  const filters = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-tier="chrome"]')).map((el) => {
      const style = getComputedStyle(el) as CSSStyleDeclaration & { webkitBackdropFilter?: string }
      return style.backdropFilter || style.webkitBackdropFilter || 'none'
    }),
  )
  expect(filters.length, '页面上没有外壳层').toBeGreaterThan(0)
  for (const filter of filters) {
    if (on) expect(filter).toContain('blur(16px)')
    else expect(filter).toBe('none')
  }
}

/** 面板滑入停稳：data-entering 去掉、面板与遮罩上的过渡与动画都结束（量尺寸前要等它，否则量到的是半路的大小） */
export async function waitForSheet(page: Page): Promise<void> {
  const sheet = page.locator('.sheet')
  await expect(sheet).not.toHaveAttribute('data-entering', /.*/)
  await page.locator('.sheet-layer').evaluate((el) =>
    Promise.all(el.getAnimations({ subtree: true }).map((animation) => animation.finished)))
}

/**
 * 有模糊的外壳（页头玻璃层、底座、操作坞、面板）合计面积不超过视口的 40%（DESIGN.md 第十二节）。
 * 默认还要求确实有模糊；allowNone 时允许一层都没有（例如打开了实色的高面板，遮罩下的外壳也关了模糊）。
 */
export async function expectBlurBudget(page: Page, { allowNone = false }: { allowNone?: boolean } = {}): Promise<void> {
  const share = await page.evaluate(() => {
    const blurred = (style: CSSStyleDeclaration) => {
      const filter = style.backdropFilter || (style as CSSStyleDeclaration & { webkitBackdropFilter?: string }).webkitBackdropFilter
      return Boolean(filter) && filter !== 'none'
    }
    const visible = (top: number, bottom: number, width: number) =>
      Math.max(0, Math.min(bottom, innerHeight) - Math.max(top, 0)) * Math.min(width, innerWidth)
    let area = 0
    for (const el of Array.from(document.querySelectorAll('*'))) {
      const box = el.getBoundingClientRect()
      if (blurred(getComputedStyle(el))) area += visible(box.top, box.bottom, box.width)
      // 画在 ::before 上的玻璃层（吸顶页头）：按伪元素自己的位置与高度算
      const before = getComputedStyle(el, '::before')
      if (blurred(before) && before.opacity !== '0') {
        const top = box.top + (Number.parseFloat(before.top) || 0)
        const height = Number.parseFloat(before.height) || box.height
        area += visible(top, top + height, Number.parseFloat(before.width) || box.width)
      }
    }
    return area / (innerWidth * innerHeight)
  })
  if (!allowNone) expect(share, '模糊面积占视口').toBeGreaterThan(0)
  expect(share, '模糊面积占视口').toBeLessThanOrEqual(0.4)
}

/** 强制颜色模式的冒烟检查（只在 Chromium）：按钮有实线边框、导航当前项有描边、就医提示 3 像素边框。 */
export async function expectForcedColorsSmoke(page: Page): Promise<void> {
  if (page.context().browser()?.browserType().name() !== 'chromium') return
  await page.emulateMedia({ forcedColors: 'active' })
  try {
    const found = await page.evaluate(() => {
      const visible = (el: Element) => el.getBoundingClientRect().width > 0
      const buttons = Array.from(document.querySelectorAll('.btn')).filter(visible).map((el) => {
        const style = getComputedStyle(el)
        return { style: style.borderTopStyle, width: Number.parseFloat(style.borderTopWidth) }
      })
      const current = Array.from(document.querySelectorAll('.rnav a[aria-current="page"]')).filter(visible).map((el) => {
        const style = getComputedStyle(el, '::before')
        return { style: style.outlineStyle, width: Number.parseFloat(style.outlineWidth) }
      })
      const care = Array.from(document.querySelectorAll('.care')).filter(visible)
        .map((el) => Number.parseFloat(getComputedStyle(el).borderTopWidth))
      return { buttons, current, care }
    })
    expect(found.buttons.length + found.current.length + found.care.length, '页面上没有可检查的元素').toBeGreaterThan(0)
    for (const button of found.buttons) {
      expect(button.style, '.btn 在强制颜色下没有实线边框').toBe('solid')
      expect(button.width).toBeGreaterThan(0)
    }
    for (const item of found.current) {
      expect(item.style, '导航当前项在强制颜色下没有描边').not.toBe('none')
      expect(item.width).toBeGreaterThan(0)
    }
    for (const width of found.care) expect(width, '就医提示在强制颜色下不是 3 像素边框').toBe(3)
  } finally {
    await page.emulateMedia({ forcedColors: 'none' })
  }
}

/**
 * “本页有敏感区”：页面登记了自己（useSensitivePage），页面上的 Sensitive 正好是登记表（src/app/sensitiveAreas.ts）
 * 里这一页的区域。expected 是按数据才出现的区域的子集（默认全部）。
 */
export async function expectSensitiveAreas(page: Page, expected?: readonly SensitiveArea[]): Promise<void> {
  const { marker, present } = await page.evaluate(({ pageAttr, areaAttr, unnamed }) => ({
    marker: document.querySelector(`[${pageAttr}]`)?.getAttribute(pageAttr) ?? null,
    present: Array.from(document.querySelectorAll('[data-sensitive]')).map((el) => el.getAttribute(areaAttr) ?? unnamed),
  }), { pageAttr: SENSITIVE_PAGE_ATTR, areaAttr: SENSITIVE_AREA_ATTR, unnamed: UNNAMED_AREA })
  const result = compareSensitiveAreas(marker, present, expected)
  expect(result.page, '页面没有登记敏感区').not.toBeNull()
  expect({ missing: result.missing, unexpected: result.unexpected }, '敏感区与登记表不一致')
    .toEqual({ missing: [], unexpected: [] })
}
