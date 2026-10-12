// 自写断言本身的回归测试：故意做一个太小的标签，检查必须失败（不需要后端数据，直接写页面内容）。
import { expectSensitiveAreas, expectTouchTargets } from '../support/a11y'
import { expect, test } from '../support/test'

// React Aria 1.22 的做法：原生控件放在 1 × 1、overflow:hidden 的外层里，手指点的是外面的 label
const hiddenRadio = (labelStyle: string) => `
  <label style="display:flex;align-items:center;${labelStyle}">
    <span style="position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap">
      <input type="radio" name="g">
    </span>女
  </label>`

test('a hidden control with a tiny label fails the touch target check', async ({ page }) => {
  await page.setContent(`<body style="margin:0;font-size:16px">${hiddenRadio('width:30px;height:20px')}</body>`)
  await expect(expectTouchTargets(page)).rejects.toThrow(/的标签 <label>：30\.0×20\.0/)
})

test('a hidden control with a 44 label passes the touch target check', async ({ page }) => {
  await page.setContent(`<body style="margin:0;font-size:16px">${hiddenRadio('width:120px;min-height:44px')}</body>`)
  await expectTouchTargets(page)
})

test('a hidden control without a label fails the touch target check', async ({ page }) => {
  await page.setContent(`<body style="margin:0">
    <span style="position:absolute;width:1px;height:1px;overflow:hidden"><input type="checkbox" aria-label="同意"></span>
  </body>`)
  await expect(expectTouchTargets(page)).rejects.toThrow(/隐藏的控件没有可点的可见标签/)
})

const profilePage = (extra: string) => `<main data-sensitive-page="me">
  <div data-sensitive data-sensitive-area="profile">身高</div>
  <div data-sensitive data-sensitive-area="switches">开关</div>${extra}
</main>`

test('the sensitive area check passes when the page matches its registration', async ({ page }) => {
  await page.setContent(profilePage(''))
  await expectSensitiveAreas(page)
})

test('the sensitive area check fails on an unregistered or missing area', async ({ page }) => {
  await page.setContent(profilePage('<div data-sensitive>没有名字</div>'))
  await expect(expectSensitiveAreas(page)).rejects.toThrow(/敏感区与登记表不一致/)
  await page.setContent('<main data-sensitive-page="me"><div data-sensitive data-sensitive-area="profile"></div></main>')
  await expect(expectSensitiveAreas(page)).rejects.toThrow(/敏感区与登记表不一致/)
  await expectSensitiveAreas(page, ['profile'])
})
