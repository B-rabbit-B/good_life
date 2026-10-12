import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Checkbox } from './Checkbox'
import { DateField } from './DateField'
import { PasswordField } from './PasswordField'
import { RadioSegment } from './RadioSegment'
import { SelectField } from './SelectField'
import { Switch } from './Switch'
import { TagField } from './TagField'
import { TextField } from './TextField'

describe('form fields', () => {
  it('renders a filled text field with hint and backend error', async () => {
    const onChange = vi.fn()
    const view = render(<TextField label="用户名" value="zhou" onChange={onChange} hint="3 到 32 位，字母、数字或下划线" />)
    const input = screen.getByRole('textbox', { name: '用户名' })
    expect(input.closest('.fld-i')).not.toHaveClass('bad')
    expect(screen.getByText('3 到 32 位，字母、数字或下划线')).toHaveClass('fld-h')
    await userEvent.type(input, '_n')
    expect(onChange).toHaveBeenLastCalledWith('zhoun')
    view.rerender(<TextField label="用户名" value="zhou" onChange={onChange} error="用户名已被占用" />)
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input.closest('.fld-i')).toHaveClass('bad')
    expect(screen.getByText('用户名已被占用')).toBeInTheDocument()
  })

  it('renders a multiline field as a text area', () => {
    render(<TextField label="健康状况" value="" onChange={() => {}} multiline rows={3} maxLength={500} />)
    const area = screen.getByRole('textbox', { name: '健康状况' })
    expect(area.tagName).toBe('TEXTAREA')
    expect(area).toHaveClass('area')
    expect(area).toHaveAttribute('rows', '3')
    expect(area).toHaveAttribute('maxlength', '500')
  })

  it('shows and hides a password', async () => {
    render(<PasswordField label="密码" value="goodlife2026" onChange={() => {}} autoComplete="current-password" />)
    const input = screen.getByLabelText('密码')
    expect(input).toHaveAttribute('type', 'password')
    expect(input).toHaveAttribute('autocomplete', 'current-password')
    const toggle = screen.getByRole('button', { name: '显示密码' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(toggle)
    expect(input).toHaveAttribute('type', 'text')
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
  })

  it('removes and adds tags', async () => {
    function Tags() {
      const [tags, setTags] = useState(['清淡', '少油'])
      return <TagField label="饮食偏好" tags={tags} onChange={setTags} />
    }
    render(<Tags />)
    expect(screen.getByRole('grid', { name: '饮食偏好' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '移除清淡' }))
    expect(screen.queryByText('清淡')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '添加' }))
    const input = screen.getByRole('textbox', { name: '添加饮食偏好' })
    await userEvent.type(input, '高蛋白{Enter}')
    expect(screen.getByText('高蛋白')).toBeInTheDocument()
    expect(screen.getByText('少油')).toBeInTheDocument()
  })

  it('names each remove button by its tag alone', () => {
    render(<TagField label="饮食偏好" tags={['清淡', '少油']} onChange={() => {}} />)
    // getByRole 的 name 是整串精确匹配：React Aria 默认把删除键与整行一起命名成“移除清淡 清淡”
    expect(screen.getByRole('button', { name: '移除清淡' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '移除少油' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /清淡 清淡/ })).not.toBeInTheDocument()
  })

  it('uses native select and date inputs', () => {
    const onSelect = vi.fn()
    const onDate = vi.fn()
    render(
      <>
        <SelectField label="餐次" value="dinner" onChange={onSelect}
          options={[{ value: 'lunch', label: '午餐' }, { value: 'dinner', label: '晚餐' }]} />
        <DateField label="复查日期" value={null} onChange={onDate} min="2026-10-13" placeholder="不设" />
      </>,
    )
    const select = screen.getByRole('combobox', { name: '餐次' })
    expect(select).toHaveValue('dinner')
    expect(select.closest('.sel')).not.toBeNull()
    fireEvent.change(select, { target: { value: 'lunch' } })
    expect(onSelect).toHaveBeenCalledWith('lunch')
    const date = screen.getByLabelText('复查日期')
    expect(date).toHaveAttribute('type', 'date')
    expect(date).toHaveAttribute('min', '2026-10-13')
    expect(screen.getByText('不设')).toBeInTheDocument()
    fireEvent.change(date, { target: { value: '2026-11-12' } })
    expect(onDate).toHaveBeenCalledWith('2026-11-12')
  })

  it('reports a cleared date as null', () => {
    const onDate = vi.fn()
    render(<DateField label="预计结束" value="2026-10-25" onChange={onDate} />)
    const date = screen.getByLabelText('预计结束')
    expect(date).toHaveValue('2026-10-25')
    expect(screen.getByText('2026-10-25')).toHaveClass('n')
    fireEvent.change(date, { target: { value: '' } })
    expect(onDate).toHaveBeenCalledWith(null)
  })

  it('toggles a checkbox and a switch row', async () => {
    const onCheck = vi.fn()
    const onSwitch = vi.fn()
    render(
      <>
        <Checkbox isSelected={false} onChange={onCheck}>我已阅读并理解以上内容</Checkbox>
        <Switch label="打开应用时主动提问" description="每天最多问一个问题" isSelected onChange={onSwitch} />
      </>,
    )
    await userEvent.click(screen.getByRole('checkbox', { name: '我已阅读并理解以上内容' }))
    expect(onCheck).toHaveBeenCalledWith(true)
    const toggle = screen.getByRole('switch', { name: /打开应用时主动提问/ })
    expect(toggle).toBeChecked()
    expect(toggle.closest('.tg-row')).not.toBeNull()
    await userEvent.click(screen.getByText('每天最多问一个问题'))
    expect(onSwitch).toHaveBeenCalledWith(false)
  })

  it('picks one option in a segment', async () => {
    const onChange = vi.fn()
    render(<RadioSegment label="性别" value="female" onChange={onChange}
      options={[{ value: 'female', label: '女' }, { value: 'male', label: '男' }, { value: 'other', label: '其他' }]} />)
    const group = screen.getByRole('radiogroup', { name: '性别' })
    expect(group.querySelector('.opts')).not.toBeNull()
    expect(screen.getByRole('radio', { name: '女' })).toBeChecked()
    await userEvent.click(screen.getByText('男'))
    expect(onChange).toHaveBeenCalledWith('male')
  })

  it('puts a unit inside the box after the number', () => {
    render(<TextField label="身高" value="165" onChange={() => {}} inputMode="decimal" suffix="厘米" />)
    const input = screen.getByRole('textbox', { name: '身高' })
    expect(input).toHaveAttribute('inputmode', 'decimal')
    expect(input).toHaveClass('n')
    const unit = screen.getByText('厘米')
    expect(unit).toHaveClass('fld-suf')
    expect(input.closest('.fld-i')).toContainElement(unit)
  })

  it('reads the segment hint as its description', () => {
    render(<RadioSegment label="性别" value="" onChange={() => {}} hint="用于估算能量需要。"
      options={[{ value: 'female', label: '女' }, { value: 'male', label: '男' }]} />)
    expect(screen.getByRole('radiogroup', { name: '性别' })).toHaveAccessibleDescription('用于估算能量需要。')
    expect(screen.getByText('用于估算能量需要。')).toHaveClass('fld-h')
  })

  it('links a tag error to the tag list', () => {
    const view = render(<TagField label="忌口" tags={['酒精']} onChange={() => {}} />)
    const list = screen.getByRole('grid', { name: '忌口' })
    expect(list).not.toHaveAttribute('aria-invalid')
    expect(list).not.toHaveAttribute('aria-describedby')
    view.rerender(<TagField label="忌口" tags={['酒精']} onChange={() => {}} error="最多 32 个字符，请删减" />)
    expect(list).toHaveAttribute('aria-invalid', 'true')
    expect(list).toHaveAccessibleDescription('最多 32 个字符，请删减')
    view.rerender(<TagField label="忌口" tags={['酒精']} onChange={() => {}} />)
    expect(list).not.toHaveAttribute('aria-invalid')
    expect(list).not.toHaveAttribute('aria-describedby')
  })
})
