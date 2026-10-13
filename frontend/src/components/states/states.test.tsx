import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/errors'
import { Button } from '../Button'
import { AuthNeededState } from './AuthNeededState'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { InsufficientState } from './InsufficientState'
import { LoadingState } from './LoadingState'

describe('state components', () => {
  it('shows a skeleton with a status line while loading', () => {
    for (const variant of ['diary', 'list', 'page'] as const) {
      const { unmount, container } = render(<LoadingState variant={variant} text="正在读取今天的记录" />)
      expect(screen.getByRole('status')).toHaveTextContent('正在读取今天的记录')
      expect(container.querySelectorAll('.sk').length).toBeGreaterThan(2)
      expect(container.querySelector('.ld')).toHaveAttribute('aria-busy', 'true')
      unmount()
    }
  })

  it('shows the backend message and code when loading fails', async () => {
    const onRetry = vi.fn()
    const error = new ApiError(504, 'llm_timeout', 'DeepSeek 在 30 秒内没有回应。可以重试，或到设置里换一个对话模型。')
    render(
      <ErrorState
        titleKey="modelFailed" error={error} onRetry={onRetry}
        actions={<Button variant="quiet" onPress={() => {}}>去设置</Button>}
        note="你刚才发的话已保留，重试不用重新输入。"
      />,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('DeepSeek 在 30 秒内没有回应。可以重试，或到设置里换一个对话模型。')
    expect(screen.getByRole('heading', { name: '没能连上模型服务' })).toHaveClass('st-h')
    expect(screen.getByText('错误码 llm_timeout')).toHaveClass('st-code')
    expect(screen.getByRole('button', { name: '去设置' })).toBeInTheDocument()
    expect(screen.getByText('你刚才发的话已保留，重试不用重新输入。')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('uses the default title and no retry when none is given', () => {
    render(<ErrorState error={new ApiError(500, 'internal_error', '服务出错了。')} />)
    expect(screen.getByRole('heading', { name: '没能读取' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument()
  })

  it('explains an empty day with its actions', () => {
    render(
      <EmptyState
        titleKey="emptyDiary" body="拍一张饭菜，或者手动记一餐。"
        actions={<Button variant="primary" icon="camera" onPress={() => {}}>拍照记录</Button>}
      />,
    )
    const region = screen.getByRole('region', { name: '这天没有饮食记录' })
    expect(region).toHaveTextContent('拍一张饭菜，或者手动记一餐。')
    expect(screen.getByRole('button', { name: '拍照记录' })).toBeInTheDocument()
  })

  it('shows what is missing and the progress when data is insufficient', () => {
    render(
      <InsufficientState
        titleKey="cycleInsufficient"
        notes={['预测至少需要 2 个完整周期，目前记录了 1 个。', '下次经期开始时记一笔即可。']}
        progressText="1 / 2 个周期"
        actions={<Button variant="quiet" onPress={() => {}}>记录经期开始</Button>}
      />,
    )
    const region = screen.getByRole('region', { name: '还不能预测下次经期' })
    expect(region).toHaveTextContent('预测至少需要 2 个完整周期，目前记录了 1 个。')
    expect(screen.getByText('1 / 2 个周期')).toBeInTheDocument()
    expect(region.querySelectorAll('.prog i')).toHaveLength(2)
    expect(region.querySelectorAll('.prog i.on')).toHaveLength(1)
    expect(screen.getByRole('button', { name: '记录经期开始' })).toBeInTheDocument()
  })

  it('asks for what is needed before going on', () => {
    render(
      <AuthNeededState
        titleKey="noModel" body="对话和拍照识别都需要先添加一个模型服务。"
        actions={<Button variant="primary" onPress={() => {}}>去添加模型服务</Button>}
      />,
    )
    const region = screen.getByRole('region', { name: '还没有可用的对话模型' })
    expect(region).toHaveTextContent('对话和拍照识别都需要先添加一个模型服务。')
    expect(screen.getByRole('button', { name: '去添加模型服务' })).toBeInTheDocument()
  })
})
