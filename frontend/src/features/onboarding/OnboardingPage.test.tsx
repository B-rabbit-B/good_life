import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ProfileOut } from '../../api/types'
import { completeProfile } from '../../test/fixtures/core'
import { emptyProfile } from '../../test/fixtures/profile'
import { profileStore } from '../../test/msw/handlers/auth'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

type Router = ReturnType<typeof renderRoute>['router']

const landsOn = (router: Router, pathname: string) =>
  waitFor(() => expect(router.state.location.pathname).toBe(pathname))

function open(path: string, profile: ProfileOut) {
  const result = renderRoute(path)
  const store = profileStore(profile)
  server.use(...store.handlers)
  return { ...result, store }
}

/** 按标签文字找到整组字段（标签组的列表为空时没有可用的名字，所以从标签找） */
const fieldOf = (label: string) => screen.getByText(label, { selector: '.fld-l' }).closest('.fld') as HTMLElement

const basicsDone =(over: Partial<ProfileOut> = {}) =>
  emptyProfile({ gender: 'female', birth_year: 1996, height_cm: 162, weight_kg: 54, ...over })

describe('onboarding', () => {
  it('saves step one with gender, birth year, height and weight', async () => {
    const user = userEvent.setup()
    const { router, store } = open('/onboarding/1', emptyProfile())
    expect(await screen.findByRole('heading', { level: 1, name: '基本信息' })).toBeInTheDocument()
    const progress = screen.getByLabelText('建档进度，第 1 步，共 3 步')
    expect(within(progress).getByText('1 基本信息')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByText('用于估算能量需要，也决定是否显示经期记录。')).toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: '男' }))
    await user.selectOptions(screen.getByLabelText('出生年份'), '1993')
    screen.getByRole('slider', { name: '身高' }).focus()
    await user.keyboard('{ArrowRight}{ArrowRight}')
    screen.getByRole('slider', { name: '体重' }).focus()
    await user.keyboard('{ArrowLeft}')
    await user.click(screen.getByRole('button', { name: '下一步' }))

    await landsOn(router, '/onboarding/2')
    expect(store.patches).toEqual([{ gender: 'male', birth_year: 1993, height_cm: 167, weight_kg: 59.5 }])
    expect(await screen.findByRole('heading', { level: 1, name: '活动与目标' })).toBeInTheDocument()
  })

  it('resumes at the first incomplete step', async () => {
    const { router } = open('/onboarding/3', basicsDone({ activity_level: 'moderate' }))
    await landsOn(router, '/onboarding/2')
    expect(await screen.findByRole('heading', { level: 1, name: '活动与目标' })).toBeInTheDocument()
    // 已经填过的值带出来
    expect(screen.getByRole('radio', { name: /^中度/ })).toBeChecked()
    expect(screen.getByRole('button', { name: '下一步' })).toBeDisabled()
  })

  it('saves activity and goal on step two', async () => {
    const user = userEvent.setup()
    const { router, store } = open('/onboarding/2', basicsDone())
    expect(await screen.findByRole('heading', { level: 1, name: '活动与目标' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '轻度 每周运动 1 到 3 次' })).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /^活跃/ }))
    await user.click(screen.getByRole('radio', { name: '维持' }))
    await user.click(screen.getByRole('button', { name: '下一步' }))

    await landsOn(router, '/onboarding/3')
    expect(store.patches).toEqual([{ activity_level: 'active', goal: 'maintain' }])
    expect(await screen.findByRole('heading', { level: 1, name: '饮食偏好与忌口' })).toBeInTheDocument()
  })

  it('lets step three be skipped', async () => {
    const user = userEvent.setup()
    const { router, store } = open('/onboarding/3', completeProfile())
    expect(await screen.findByRole('heading', { level: 1, name: '饮食偏好与忌口' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '跳过这一步' }))
    await landsOn(router, '/chat')
    expect(store.patches).toEqual([])
  })

  it('saves tags and health conditions on step three', async () => {
    const user = userEvent.setup()
    const { router, store } = open('/onboarding/3', completeProfile())
    expect(await screen.findByRole('heading', { level: 1, name: '饮食偏好与忌口' })).toBeInTheDocument()
    expect(screen.getByLabelText('健康状况')).toHaveAccessibleDescription('只用于生成建议。医生的要求请到医嘱页录入，才会按约束执行。')

    const prefs = fieldOf('饮食偏好')
    await user.click(within(prefs).getByRole('button', { name: '添加' }))
    await user.type(screen.getByLabelText('添加饮食偏好'), '清淡{Enter}')
    const avoid = fieldOf('忌口')
    await user.click(within(avoid).getByRole('button', { name: '添加' }))
    await user.type(screen.getByLabelText('添加忌口'), '酒精{Enter}')
    await user.type(screen.getByLabelText('健康状况'), '膝关节半月板术后')
    await user.click(screen.getByRole('button', { name: '完成' }))

    await landsOn(router, '/chat')
    expect(store.patches).toEqual([{
      diet_preferences: ['清淡'], food_avoidances: ['酒精'], health_conditions: '膝关节半月板术后',
    }])
  })

  it('exposes the rulers as sliders with value text', async () => {
    open('/onboarding/1', emptyProfile())
    const height = await screen.findByRole('slider', { name: '身高' })
    expect(height).toHaveAttribute('aria-valuetext', '165 厘米')
    expect(height).toHaveAttribute('aria-valuemin', '50')
    expect(height).toHaveAttribute('aria-valuemax', '250')
    const weight = screen.getByRole('slider', { name: '体重' })
    expect(weight).toHaveAttribute('aria-valuetext', '60 千克')
    expect(weight).toHaveAttribute('aria-valuemin', '20')
    expect(weight).toHaveAttribute('aria-valuemax', '300')
    expect(weight).toHaveAccessibleDescription('左右拖动刻度，或点数字直接输入。')
  })
})
