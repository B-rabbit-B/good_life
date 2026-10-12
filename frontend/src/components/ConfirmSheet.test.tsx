import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/errors'
import { ConfirmSheet } from './ConfirmSheet'

const ACK = '我知道解除后不能撤销，需要重新录入才能恢复这条约束'
const WILL = [
  { text: '这条医嘱从“生效中”变为“已解除”。' },
  { text: '解除不能撤销。以后需要时，请重新录入。', irreversible: true },
]

function renderSheet(props: Partial<Parameters<typeof ConfirmSheet>[0]> = {}) {
  const onConfirm = props.onConfirm ?? vi.fn(() => Promise.resolve())
  render(
    <ConfirmSheet
      isOpen
      onClose={() => {}}
      titleKey="resolveSheet"
      quote={<p>膝关节术后六周内避免跑跳</p>}
      will={WILL}
      confirmLabel="确认解除"
      confirmVariant="danger"
      note="医嘱只能在这里确认或解除，对话里无法完成。"
      onConfirm={onConfirm}
      {...props}
    />,
  )
  return { onConfirm }
}

describe('ConfirmSheet', () => {
  it('keeps confirm disabled until the acknowledgement is checked', async () => {
    const { onConfirm } = renderSheet({ ack: ACK })
    const confirm = screen.getByRole('button', { name: '确认解除' })
    expect(confirm).toHaveClass('btn', 'btn-dng', 'btn-blk')
    expect(confirm).toBeDisabled()
    await userEvent.click(confirm)
    expect(onConfirm).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('checkbox', { name: ACK }))
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(screen.getByText('确认后会发生：')).toBeInTheDocument()
    expect(screen.getByText('解除不能撤销。以后需要时，请重新录入。')).toHaveClass('irrev')
  })

  it('ignores repeated presses while confirming', async () => {
    let finish: () => void = () => {}
    const onConfirm = vi.fn(() => new Promise<void>((resolve) => { finish = resolve }))
    renderSheet({ onConfirm, confirmVariant: 'primary', confirmLabel: '确认生效' })
    const confirm = screen.getByRole('button', { name: '确认生效' })
    expect(confirm).toHaveClass('btn-pri')
    await userEvent.click(confirm)
    await userEvent.click(confirm)
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(confirm).toHaveAttribute('aria-disabled', 'true')
    finish()
    await vi.waitFor(() => expect(confirm).not.toHaveAttribute('aria-disabled'))
  })

  it('announces the result assertively', () => {
    renderSheet({ resultText: '已解除：膝关节术后六周内避免跑跳。审计已记录。' })
    const live = screen.getByText('已解除：膝关节术后六周内避免跑跳。审计已记录。')
    expect(live).toHaveAttribute('aria-live', 'assertive')
    expect(screen.queryByText('医嘱只能在这里确认或解除，对话里无法完成。')).not.toBeInTheDocument()
  })

  it('shows the backend message and code on failure', () => {
    renderSheet({ error: new ApiError(409, 'item_state_conflict', '这条医嘱已经不是生效中，请刷新后再试。') })
    expect(screen.getByText('这条医嘱已经不是生效中，请刷新后再试。')).toBeInTheDocument()
    expect(screen.getByText('错误码 item_state_conflict')).toBeInTheDocument()
  })

  it('runs the secondary action', async () => {
    const onPress = vi.fn()
    renderSheet({ secondary: { label: '不解除，撤销这条建议', onPress } })
    await userEvent.click(screen.getByRole('button', { name: '不解除，撤销这条建议' }))
    expect(onPress).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: '取消' })).not.toBeInTheDocument()
  })

  it('offers cancel when there is no secondary action', async () => {
    const onClose = vi.fn()
    renderSheet({ onClose })
    await userEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(onClose).toHaveBeenCalled()
  })
})
