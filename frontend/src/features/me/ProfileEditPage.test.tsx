import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { completeProfile } from '../../test/fixtures/core'
import { profileStore } from '../../test/msw/handlers/auth'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

/** 按标签文字找到整组字段（标签组的列表为空时没有可用的名字，所以从标签找） */
const fieldOf = (label: string) => screen.getByText(label, { selector: '.fld-l' }).closest('.fld') as HTMLElement

describe('profile edit page', () => {
  it('patches only changed fields', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/me/profile')
    const store = profileStore(completeProfile({ food_avoidances: ['动物内脏'], updated_at: '2026-10-02T08:00:00Z' }))
    server.use(...store.handlers)
    const weight = await screen.findByLabelText('体重')
    expect(weight).toHaveValue('54')
    expect(screen.getByLabelText('身高')).toHaveValue('162')
    expect(screen.getByText('出生年份 1996，性别 女；上次更新 2026-10-02')).toBeInTheDocument()
    expect(sensitiveAreaMismatch(document, ['profile'])).toEqual({ page: 'profileEdit', missing: [], unexpected: [] })

    await user.clear(weight)
    await user.type(weight, '55.5')
    const avoid = fieldOf('忌口')
    await user.click(within(avoid).getByRole('button', { name: '添加' }))
    await user.type(screen.getByLabelText('添加忌口'), '酒精{Enter}')
    await user.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/me'))
    expect(store.patches).toEqual([{ weight_kg: 55.5, food_avoidances: ['动物内脏', '酒精'] }])
    expect(await screen.findByText('已保存')).toBeInTheDocument()
  })

  it('shows field errors from the backend', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/me/profile')
    server.use(http.patch('/api/profile', () => HttpResponse.json({
      error: {
        code: 'validation_error',
        message: '请求参数不合法',
        details: [
          { field: 'height_cm', message: 'Input should be less than or equal to 250' },
          { field: 'food_avoidances.0', message: 'String should have at most 32 characters' },
        ],
      },
    }, { status: 422 })))
    const height = await screen.findByLabelText('身高')
    await user.clear(height)
    await user.type(height, '300')
    await user.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => expect(screen.getByLabelText('身高')).toHaveAccessibleDescription(/Input should be less than or equal to 250/))
    expect(screen.getByLabelText('身高')).toHaveAttribute('aria-invalid', 'true')
    const avoid = fieldOf('忌口')
    expect(within(avoid).getByText('String should have at most 32 characters')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/me/profile')
  })

  it('has a cover button in the header', async () => {
    renderRoute('/me/profile')
    expect(await screen.findByRole('heading', { level: 1, name: '个人档案' })).toBeInTheDocument()
    const cover = screen.getByRole('button', { name: '遮盖敏感内容' })
    expect(cover.closest('header')).not.toBeNull()
    expect(screen.getByRole('button', { name: '返回' })).toBeInTheDocument()
  })
})
