import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { setPendingPhoto, takePendingPhoto } from '../../lib/photoHandoff'
import { gate } from '../../test/chat'
import { recognition, REC_ID } from '../../test/fixtures/photos'
import { photosHandlers, type PhotosOptions } from '../../test/msw/handlers/photos'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const photo = () => new File(['jpeg-bytes'], 'dinner.jpg', { type: 'image/jpeg' })

function renderPhotoNew(opts: PhotosOptions = {}) {
  const result = renderRoute('/photos/new')
  const photos = photosHandlers(opts)
  server.use(...photos.handlers)
  return { ...result, photos }
}

/** 从相册选一张（相册的 input 没有 capture） */
async function pickFromGallery(user: ReturnType<typeof userEvent.setup>, file: File = photo()) {
  await screen.findByRole('button', { name: '从相册选' })
  const input = document.querySelector<HTMLInputElement>('input[type="file"]:not([capture])')
  if (!input) throw new Error('没有相册的 input')
  await user.upload(input, file)
}

describe('photo new page', () => {
  it('starts at once with a handed over photo', async () => {
    const held = gate()
    setPendingPhoto(photo())
    const { photos } = renderPhotoNew({ hold: held.promise, create: recognition() })
    expect(await screen.findByRole('list', { name: '识别进度' })).toBeInTheDocument()
    await waitFor(() => expect(photos.creates).toHaveLength(1))
    expect(takePendingPhoto()).toBeNull()
    expect(screen.queryByRole('button', { name: '拍照' })).not.toBeInTheDocument()
    held.open()
  })

  it('offers camera and gallery inputs and keeps the photo only when asked', async () => {
    renderPhotoNew()
    expect(await screen.findByRole('button', { name: '拍照' })).toBeInTheDocument()
    const inputs = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="file"]'))
    expect(inputs).toHaveLength(2)
    expect(inputs[0]?.getAttribute('capture')).toBe('environment')
    expect(inputs[1]?.hasAttribute('capture')).toBe(false)
    expect(inputs[0]?.accept).toBe('image/jpeg,image/png,image/webp')
    expect(screen.getByRole('checkbox', { name: '保留照片（加密保存，可随时删除）' })).not.toBeChecked()
  })

  it('shows three progress steps while recognising', async () => {
    const user = userEvent.setup()
    const held = gate()
    renderPhotoNew({ hold: held.promise, create: recognition() })
    await pickFromGallery(user)
    const steps = within(await screen.findByRole('list', { name: '识别进度' })).getAllByRole('listitem')
    expect(steps).toHaveLength(3)
    expect(steps[1]).toHaveTextContent('正在认菜和份量')
    expect(steps[2]).toHaveTextContent('按营养库计算热量与营养')
    expect(screen.getByText('你选的照片（不保留，识别后丢弃）')).toBeInTheDocument()
    expect(screen.getByText('可以离开这一页，识别完成后可在拍照页的“未处理的草稿”里继续。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '取消识别' })).toBeInTheDocument()
    held.open()
  })

  it('says the photo is kept when the box is ticked', async () => {
    const user = userEvent.setup()
    const held = gate()
    renderPhotoNew({ hold: held.promise, create: recognition({ image_kept: true }) })
    await user.click(await screen.findByRole('checkbox', { name: '保留照片（加密保存，可随时删除）' }))
    await pickFromGallery(user)
    expect(await screen.findByText('你选的照片（加密保留）')).toBeInTheDocument()
    held.open()
  })

  it('goes to the result page on success', async () => {
    const user = userEvent.setup()
    const { router } = renderPhotoNew({ create: recognition() })
    await pickFromGallery(user)
    await waitFor(() => expect(router.state.location.pathname).toBe(`/photos/${REC_ID}`))
    expect(await screen.findByRole('heading', { name: '识别结果', level: 1 })).toBeInTheDocument()
    // 识别页被替换掉了：返回不会回到“识别中”
    expect(router.state.historyAction).toBe('REPLACE')
  })

  it('shows the not food state with the backend message and code', async () => {
    const user = userEvent.setup()
    renderPhotoNew({ create: { status: 422, code: 'photo_not_food', message: '没有识别到食物，请对准饭菜重拍' } })
    await pickFromGallery(user)
    expect(await screen.findByRole('heading', { name: '没有认出食物' })).toBeInTheDocument()
    expect(screen.getByText('没有识别到食物，请对准饭菜重拍')).toBeInTheDocument()
    expect(screen.getByText('错误码 photo_not_food。这次没有产生识别记录。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重拍' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '从相册换一张' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '手动记一餐' })).toHaveAttribute('href', '/records/meals/new')
    expect(screen.queryByRole('button', { name: '重试识别' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '去设置' })).not.toBeInTheDocument()
    const tips = screen.getByRole('region', { name: '拍照小提示' })
    expect(within(tips).getAllByRole('listitem')).toHaveLength(3)
    expect(tips).toHaveTextContent('只支持 JPEG、PNG、WebP，不超过 8 MB。')
  })

  it('titles an unclear photo and other failures by their code', async () => {
    const user = userEvent.setup()
    renderPhotoNew({ create: { status: 422, code: 'photo_unclear', message: '图片太模糊或太暗，请在光线充足处对准饭菜重拍' } })
    await pickFromGallery(user)
    expect(await screen.findByRole('heading', { name: '照片看不清' })).toBeInTheDocument()
    expect(screen.getByText('图片太模糊或太暗，请在光线充足处对准饭菜重拍')).toBeInTheDocument()
  })

  it('shows a format error verbatim', async () => {
    const user = userEvent.setup()
    const message = '暂不支持 HEIC 格式，请改成 JPEG 再上传（相机设置里可选“兼容性最佳”）'
    renderPhotoNew({ create: { status: 415, code: 'photo_type_not_allowed', message } })
    // 文件选择框只收 JPEG、PNG、WebP，所以用一个 JPEG 类型的文件触发后端的格式说明（后端按文件头判断格式）
    await pickFromGallery(user, new File(['ftypheic'], 'IMG_0001.jpg', { type: 'image/jpeg' }))
    expect(await screen.findByRole('heading', { name: '这次没有识别完成' })).toBeInTheDocument()
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(screen.getByText('错误码 photo_type_not_allowed。这次没有产生识别记录。')).toBeInTheDocument()
  })

  it('offers retry and settings for a model failure', async () => {
    const user = userEvent.setup()
    const message = '还没有设置看图识别用的模型，请先到设置页添加模型服务并选择看图模型'
    const { photos } = renderPhotoNew({ create: { status: 409, code: 'llm_not_configured', message } })
    await pickFromGallery(user)
    expect(await screen.findByRole('heading', { name: '这次没有识别完成' })).toBeInTheDocument()
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '去设置' })).toHaveAttribute('href', '/settings/models')
    await user.click(screen.getByRole('button', { name: '重试识别' }))
    await waitFor(() => expect(photos.creates).toHaveLength(2))
    expect(await screen.findByRole('heading', { name: '这次没有识别完成' })).toBeInTheDocument()
  })

  it('lists unfinished drafts', async () => {
    renderPhotoNew({
      records: [
        recognition(),
        recognition({ id: '00000000-0000-4000-8000-0000000000a2', status: 'confirmed', evaluation: null }),
      ],
    })
    const drafts = await screen.findByRole('region', { name: '未处理的草稿' })
    const links = await within(drafts).findAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', `/photos/${REC_ID}`)
    expect(links[0]).toHaveTextContent('4 项')
    // 这一页不在遮盖范围里，所以列表不写菜名
    expect(drafts).not.toHaveTextContent('杂粮饭')
  })

  it('cancels the upload', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { router } = renderPhotoNew({ hold: held.promise, create: recognition() })
    await pickFromGallery(user)
    await user.click(await screen.findByRole('button', { name: '取消识别' }))
    expect(await screen.findByRole('button', { name: '拍照' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: '识别进度' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    held.open()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(router.state.location.pathname).toBe('/photos/new')
  })
})
