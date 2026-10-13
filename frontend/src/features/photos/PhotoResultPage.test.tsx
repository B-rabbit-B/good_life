import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { qk } from '../../api/keys'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { addDays, todayISO } from '../../lib/dates'
import { REVIEW_REASON_LABELS } from '../../lib/labels'
import {
  ENGINE_DISCLAIMER, fish, liver, PHOTO_DISCLAIMER, recognition, REC_ID, rice, UNCHECKED_NOTICE,
} from '../../test/fixtures/photos'
import { photosHandlers, type PhotosOptions } from '../../test/msw/handlers/photos'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderResult(opts: PhotosOptions = { records: [recognition()] }) {
  const result = renderRoute(`/photos/${REC_ID}`)
  const photos = photosHandlers(opts)
  server.use(...photos.handlers)
  return { ...result, photos }
}

/** 一道菜所在的识别项 */
const itemOf = (name: string) => screen.getByText(name, { selector: '.item-n>span' }).closest('.item') as HTMLElement

/** 等识别记录读到、识别项画出来（页头在读取时就已经在了） */
const loaded = () => screen.findAllByText(/./, { selector: '.item-n>span' })

/** 未改动的项只带编号与菜名，原来有食物编号时再带上 */
const untouched = (item: ReturnType<typeof rice>) =>
  item.food_id ? { id: item.id, name: item.name, food_id: item.food_id } : { id: item.id, name: item.name }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('photo result page', () => {
  it('lists items with confidence, grams and review reasons', async () => {
    renderResult()
    await loaded()
    const riceRow = itemOf('杂粮饭')
    expect(riceRow).toHaveTextContent('207千卡')
    expect(riceRow).toHaveTextContent('一碗，180 克')
    expect(riceRow).toHaveTextContent('营养库：杂粮饭')
    expect(within(riceRow).getByRole('img', { name: '把握程度 0.91，高' })).toBeInTheDocument()
    expect(riceRow).not.toHaveClass('flag')

    const liverRow = itemOf('卤猪肝')
    expect(liverRow).toHaveClass('flag')
    expect(liverRow).toHaveTextContent('一小碟，80 克（估算）')
    expect(within(liverRow).getByRole('img', { name: '把握程度 0.58，低' })).toBeInTheDocument()
    expect(within(liverRow).getByText(REVIEW_REASON_LABELS.low_confidence)).toBeInTheDocument()
    expect(within(liverRow).getByText(REVIEW_REASON_LABELS.estimated_grams)).toBeInTheDocument()
    // 评价里这一项的结论
    expect(within(liverRow).getByText('不建议')).toHaveClass('vd-no')
    expect(within(liverRow).getByRole('button', { name: '修改' })).toBeInTheDocument()
    expect(within(liverRow).getByRole('button', { name: '删除这一项' })).toBeInTheDocument()

    const beefRow = itemOf('酸汤肥牛')
    expect(beefRow).toHaveTextContent('待确认')
    expect(within(beefRow).getByText(REVIEW_REASON_LABELS.needs_confirmation)).toBeInTheDocument()
    expect(within(beefRow).getByRole('radiogroup', { name: '选择酸汤肥牛对应的食物' })).toBeInTheDocument()

    expect(screen.getByText('有 2 项建议核对')).toBeInTheDocument()
    expect(screen.getByText('草稿')).toBeInTheDocument()
    expect(screen.getByText(/看图模型 qwen-vl-max/)).toBeInTheDocument()
    const totals = document.querySelector('.totals') as HTMLElement
    expect(totals).toHaveTextContent('567千卡')
    expect(totals).toHaveTextContent('61.4蛋白质 克')
    expect(totals).toHaveTextContent('1,012钠 毫克')
  })

  it('picks a candidate by sending its food_id', async () => {
    const user = userEvent.setup()
    const { photos } = renderResult()
    const group = await screen.findByRole('radiogroup', { name: '选择酸汤肥牛对应的食物' })
    await user.click(within(group).getByRole('radio', { name: '肥牛（火锅用）' }))
    await waitFor(() => expect(photos.updates).toHaveLength(1))
    expect(photos.updates[0]?.body).toEqual({
      items: [untouched(rice()), untouched(fish()), untouched(liver()), { id: 'item-beef', name: '酸汤肥牛', food_id: 'cfcd:beef_hotpot' }],
    })
    await waitFor(() => expect(itemOf('酸汤肥牛')).toHaveTextContent('营养库：肥牛（火锅用）'))
    expect(screen.getByRole('button', { name: '确认入库' })).toBeEnabled()
  })

  it('renames and deletes items through the full items list', async () => {
    const user = userEvent.setup()
    const { photos } = renderResult()
    await loaded()
    await user.click(within(itemOf('酸汤肥牛')).getByRole('button', { name: '改个名字' }))
    const sheet = await screen.findByRole('dialog', { name: '修改这一项' })
    const name = within(sheet).getByLabelText('菜名')
    expect(name).toHaveValue('酸汤肥牛')
    await user.clear(name)
    await user.type(name, '肥牛')
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(photos.updates).toHaveLength(1))
    expect(photos.updates[0]?.body.items).toEqual([
      untouched(rice()), untouched(fish()), untouched(liver()), { id: 'item-beef', name: '肥牛' },
    ])
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    await user.click(within(itemOf('卤猪肝')).getByRole('button', { name: '删除这一项' }))
    await waitFor(() => expect(photos.updates).toHaveLength(2))
    expect(photos.updates[1]?.body.items.map((item) => item.id)).toEqual(['item-rice', 'item-fish', 'item-beef'])
    await waitFor(() => expect(screen.queryByText('卤猪肝', { selector: '.item-n>span' })).not.toBeInTheDocument())
  })

  it('edits the grams of a flagged item and shows a field error from the backend', async () => {
    const user = userEvent.setup()
    const { photos } = renderResult()
    await loaded()
    await user.click(within(itemOf('卤猪肝')).getByRole('button', { name: '修改' }))
    const sheet = await screen.findByRole('dialog', { name: '修改这一项' })
    const grams = within(sheet).getByLabelText('克数')
    expect(grams).toHaveValue('80')
    await user.clear(grams)
    await user.type(grams, '60')
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(photos.updates).toHaveLength(1))
    expect(photos.updates[0]?.body.items[2]).toEqual({ id: 'item-liver', name: '卤猪肝', grams: 60, food_id: 'dish:braised_liver' })
    await waitFor(() => expect(itemOf('卤猪肝')).toHaveTextContent('一小碟，60 克'))
    expect(itemOf('卤猪肝')).not.toHaveTextContent('（估算）')

    server.use(http.put('/api/photos/recognitions/:id/items', () => HttpResponse.json({
      error: {
        code: 'validation_error', message: '请求参数不合法',
        details: [{ field: 'items.2.grams', message: '不能大于 3000', type: 'less_than_equal' }],
      },
    }, { status: 422 })))
    await user.click(within(itemOf('卤猪肝')).getByRole('button', { name: '修改' }))
    const again = await screen.findByRole('dialog', { name: '修改这一项' })
    await user.clear(within(again).getByLabelText('克数'))
    await user.type(within(again).getByLabelText('克数'), '5000')
    await user.click(within(again).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(within(again).getByLabelText('克数')).toHaveAccessibleDescription('不能大于 3000'))
    expect(screen.getByRole('dialog', { name: '修改这一项' })).toBeInTheDocument()
  })

  it('keeps confirm disabled while items need confirmation and counts them', async () => {
    renderResult()
    const confirm = await screen.findByRole('button', { name: '确认入库（还有 1 项待确认）' })
    expect(confirm).toBeDisabled()
  })

  it('routes back to editing on photo_items_need_confirmation', async () => {
    const user = userEvent.setup()
    const message = '还有待确认的菜品：请先从候选里选择对应的食物、改成营养库里有的名称，或删除这一项，再确认入库'
    renderResult({
      records: [recognition({ items: [rice(), liver()] })],
      confirmError: { status: 422, code: 'photo_items_need_confirmation', message },
    })
    await user.click(await screen.findByRole('button', { name: '确认入库' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    // 焦点回到第一个需要处理的项（这里是建议核对的卤猪肝）
    await waitFor(() => expect(document.activeElement).toBe(itemOf('卤猪肝')))
  })

  it('confirms with date and meal and opens that day', async () => {
    const user = userEvent.setup()
    const yesterday = addDays(todayISO(), -1)
    const { photos, router } = renderResult({ records: [recognition({ items: [rice(), fish()] })] })
    const date = await screen.findByLabelText('日期')
    expect(date).toHaveValue(todayISO())
    expect(date).toHaveAttribute('max', todayISO())
    fireEvent.change(date, { target: { value: yesterday } })
    await user.selectOptions(screen.getByLabelText('餐次'), 'lunch')
    await user.click(screen.getByRole('button', { name: '确认入库' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/records'))
    expect(photos.confirms).toEqual([{ id: REC_ID, body: { eaten_on: yesterday, meal_type: 'lunch' } }])
    expect(router.state.location.search).toBe(`?tab=diet&date=${yesterday}`)
  })

  it('shows the meal evaluation with a reference tag only for drafts', async () => {
    renderResult()
    const panel = await screen.findByRole('region', { name: '整餐评价' })
    expect(within(panel).getByText('仅供参考')).toBeInTheDocument()
    expect(within(panel).getByText('不建议', { selector: '.verdict b' })).toBeInTheDocument()
    expect(panel).toHaveTextContent('医嘱避免动物内脏与浓肉汤（高嘌呤）')
    expect(panel).toHaveTextContent('当日摄入加上这一餐，今天的钠预计 2,652 毫克，超过上限 2,000 毫克')
    expect(panel).toHaveTextContent('健身目标补足今天还差的蛋白质')
    expect(within(panel).getAllByText('猪肝（卤）')[0]).toHaveClass('vd-no')
  })

  it('shows a confirmed record read only without an evaluation', async () => {
    renderResult({
      records: [recognition({ status: 'confirmed', evaluation: null, eaten_on: todayISO(), meal_type: 'dinner', items: [rice()] })],
    })
    expect(await screen.findByText('已确认入库')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '整餐评价' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /确认入库/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '放弃这次识别' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看这天的饮食记录' }))
      .toHaveAttribute('href', `/records?tab=diet&date=${todayISO()}`)
  })

  it('shows the unchecked notice and both disclaimers verbatim', async () => {
    renderResult()
    expect(await screen.findByText(UNCHECKED_NOTICE)).toHaveClass('unchecked')
    expect(screen.getByText(PHOTO_DISCLAIMER)).toBeInTheDocument()
    expect(screen.getByText(ENGINE_DISCLAIMER)).toBeInTheDocument()
  })

  it('discards after confirming in a sheet', async () => {
    const user = userEvent.setup()
    const { photos, router } = renderResult()
    await user.click(await screen.findByRole('button', { name: '放弃这次识别' }))
    const sheet = await screen.findByRole('dialog', { name: '放弃这次识别' })
    await user.click(within(sheet).getByRole('button', { name: '放弃' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/photos/new'))
    expect(photos.discards).toEqual([REC_ID])
  })

  it('loads the image only when it was kept', async () => {
    const createObjectURL = vi.fn(() => 'blob:kept-photo')
    const revokeObjectURL = vi.fn()
    // 换成一个子类，不动全局的 URL 本身（afterEach 里 unstubAllGlobals 换回原来的）
    class TestURL extends URL {
      static override createObjectURL = createObjectURL
      static override revokeObjectURL = revokeObjectURL
    }
    vi.stubGlobal('URL', TestURL)

    const first = renderResult()
    await loaded()
    expect(screen.getByText('未保留', { exact: false })).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(first.photos.imageRequests).toEqual([])
    first.unmount()

    const kept = renderResult({ records: [recognition({ image_kept: true })] })
    expect(await screen.findByRole('img', { name: '这次识别保留的照片' })).toHaveAttribute('src', 'blob:kept-photo')
    expect(kept.photos.imageRequests).toEqual([REC_ID])
    kept.unmount()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:kept-photo')
  })

  it('wraps names, numbers and evaluation in sensitive regions', async () => {
    renderResult()
    await screen.findByRole('region', { name: '整餐评价' })
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'photoResult', missing: [], unexpected: [] })
    expect(itemOf('杂粮饭').closest('[data-sensitive-area="dishes"]')).not.toBeNull()
    expect((document.querySelector('.totals') as HTMLElement).closest('[data-sensitive-area="dishes"]')).not.toBeNull()
    expect(screen.getByRole('region', { name: '整餐评价' }).closest('[data-sensitive-area="evaluation"]')).not.toBeNull()
    // 页头右上角有遮盖按钮（没有底部导航的敏感页）
    expect(screen.getByRole('button', { name: '遮盖敏感内容' })).toBeInTheDocument()
  })

  it('shows a missing record with the backend message', async () => {
    renderResult({ records: [] })
    expect(await screen.findByRole('alert')).toHaveTextContent('记录不存在')
    expect(screen.getByText('错误码 not_found')).toBeInTheDocument()
  })

  it('confirms once on a double press', async () => {
    // 两次按下之间不让出事件循环：按钮的 isPending 来不及画出来（真机上快速双击就是这样）
    const user = userEvent.setup({ delay: null })
    const { photos, router } = renderResult({ records: [recognition({ items: [rice(), fish()] })] })
    await user.dblClick(await screen.findByRole('button', { name: '确认入库' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/records'))
    expect(photos.confirms).toHaveLength(1)
    expect(screen.queryByText(/不能再修改或确认/)).not.toBeInTheDocument()
  })

  it('deletes an item once on a double press', async () => {
    const user = userEvent.setup()
    const { photos } = renderResult()
    await loaded()
    await user.dblClick(within(itemOf('卤猪肝')).getByRole('button', { name: '删除这一项' }))
    await waitFor(() => expect(itemOf('杂粮饭')).toBeInTheDocument())
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(photos.updates).toHaveLength(1)
  })

  it('limits the dish name and the portion to the backend length', async () => {
    const user = userEvent.setup()
    renderResult()
    await loaded()
    await user.click(within(itemOf('卤猪肝')).getByRole('button', { name: '修改' }))
    const sheet = await screen.findByRole('dialog', { name: '修改这一项' })
    expect(within(sheet).getByLabelText('菜名')).toHaveAttribute('maxlength', '30')
    expect(within(sheet).getByLabelText('份量说法')).toHaveAttribute('maxlength', '30')
  })

  it('keeps the edit form fields under the cover', async () => {
    const user = userEvent.setup()
    renderResult()
    await loaded()
    await user.click(within(itemOf('卤猪肝')).getByRole('button', { name: '修改' }))
    const sheet = await screen.findByRole('dialog', { name: '修改这一项' })
    for (const label of ['菜名', '份量说法', '克数']) {
      expect(within(sheet).getByLabelText(label).closest('[data-sensitive-area="dishes"]'), label).not.toBeNull()
    }
    // 保存与取消在遮盖区外面：盖住时仍能关上面板
    expect(within(sheet).getByRole('button', { name: '取消' }).closest('[data-sensitive-area]')).toBeNull()
  })

  it('refreshes the other drafts but not the kept photos after confirming', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderResult({ records: [recognition({ items: [rice(), fish()] })] })
    queryClient.setQueryData(qk.recognition('other-draft'), recognition({ id: 'other-draft' }))
    queryClient.setQueryData(qk.recognitionImage('other-draft'), new Blob(['jpeg']))
    await user.click(await screen.findByRole('button', { name: '确认入库' }))
    await waitFor(() => expect(queryClient.getQueryState(qk.recognition('other-draft'))?.isInvalidated).toBe(true))
    expect(queryClient.getQueryState(qk.recognitionImage('other-draft'))?.isInvalidated).toBe(false)
  })

  it('deletes the recognition and its kept photo after confirming in a sheet', async () => {
    const user = userEvent.setup()
    const confirmed = recognition({
      status: 'confirmed', evaluation: null, eaten_on: todayISO(), meal_type: 'dinner', items: [rice()], image_kept: true,
    })
    const { photos, router, queryClient } = renderResult({ records: [confirmed] })
    await loaded()
    await user.click(screen.getByRole('button', { name: '删除这条识别（连同照片）' }))
    const sheet = await screen.findByRole('dialog', { name: '删除这条识别（连同照片）' })
    expect(within(sheet).getByRole('heading', { name: '删除这条识别（连同照片）' })).toHaveClass('sheet-h')
    expect(sheet).toHaveTextContent('这条识别记录与保留的照片一起删除')
    expect(sheet).toHaveTextContent('已经写入饮食记录的条目不受影响')
    expect(sheet).toHaveTextContent('删除后不能恢复')
    await user.click(within(sheet).getByRole('button', { name: '删除' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/photos/new'))
    expect(photos.deletes).toEqual([REC_ID])
    expect(await screen.findByText('已删除这条识别')).toBeInTheDocument()
    await waitFor(() => expect(queryClient.getQueryData(qk.recognition(REC_ID))).toBeUndefined())
    expect(queryClient.getQueryData(qk.recognitionImage(REC_ID))).toBeUndefined()
  })

  it('offers delete for a draft too and shows a backend error in the sheet', async () => {
    const user = userEvent.setup()
    const { router } = renderResult({
      records: [recognition()],
      deleteError: { status: 500, code: 'internal_error', message: '服务出了点问题，请稍后再试' },
    })
    await loaded()
    // 没有保留照片：标题不提照片
    expect(screen.queryByRole('button', { name: '删除这条识别（连同照片）' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '删除这条识别' }))
    const sheet = await screen.findByRole('dialog', { name: '删除这条识别' })
    expect(sheet).toHaveTextContent('这条识别记录被删除（这次没有保留照片）')
    await user.click(within(sheet).getByRole('button', { name: '删除' }))
    const alert = await within(sheet).findByRole('alert')
    expect(alert).toHaveTextContent('服务出了点问题，请稍后再试')
    expect(alert).toHaveTextContent('错误码 internal_error')
    expect(router.state.location.pathname).toBe(`/photos/${REC_ID}`)
  })

  it('says when the kept photo cannot be loaded', async () => {
    renderResult({
      records: [recognition({ image_kept: true })],
      imageError: { status: 404, code: 'photo_image_not_kept', message: '这次识别没有保留图片' },
    })
    expect(await screen.findByText('读取失败', { exact: false })).toBeInTheDocument()
  })
})
