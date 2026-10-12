import { describe, expect, it } from 'vitest'
import { compressImage, targetSize } from './compress'

describe('target size', () => {
  it('scales a long edge of 4032 down to 2048', () => {
    expect(targetSize(4032, 3024)).toEqual({ width: 2048, height: 1536 })
  })

  it('scales a portrait photo by its height', () => {
    expect(targetSize(3024, 4032)).toEqual({ width: 1536, height: 2048 })
  })

  it('keeps a small photo as it is', () => {
    expect(targetSize(1280, 960)).toEqual({ width: 1280, height: 960 })
    expect(targetSize(2048, 1000)).toEqual({ width: 2048, height: 1000 })
  })

  it('takes another long edge limit', () => {
    expect(targetSize(1000, 500, 500)).toEqual({ width: 500, height: 250 })
  })
})

describe('compress image', () => {
  it('returns the file itself when it cannot be decoded', async () => {
    const file = new File(['not an image'], 'meal.heic', { type: 'image/heic' })
    await expect(compressImage(file)).resolves.toBe(file)
  })
})
