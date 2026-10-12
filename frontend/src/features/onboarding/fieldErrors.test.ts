import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/errors'
import { errorsOf, FORM_ERROR, fieldErrors, otherErrors } from './fieldErrors'

describe('field errors', () => {
  it('puts each validation detail under the last segment of its field', () => {
    const error = new ApiError(422, 'validation_error', '请求参数不合法', [
      { field: 'username', message: 'String should have at least 3 characters' },
      { field: 'profile.height_cm', message: 'Input should be less than or equal to 250' },
    ])
    expect(fieldErrors(error)).toEqual({
      username: 'String should have at least 3 characters',
      height_cm: 'Input should be less than or equal to 250',
    })
  })

  it('skips list indexes so a bad tag lands on its list', () => {
    const error = new ApiError(422, 'validation_error', '请求参数不合法', [
      { field: 'food_avoidances.2', message: 'String should have at most 32 characters' },
    ])
    expect(fieldErrors(error)).toEqual({ food_avoidances: 'String should have at most 32 characters' })
  })

  it('keeps the first message when a field has several', () => {
    const error = new ApiError(422, 'validation_error', '请求参数不合法', [
      { field: 'password', message: '第一条' },
      { field: 'password', message: '第二条' },
    ])
    expect(fieldErrors(error)).toEqual({ password: '第一条' })
  })

  it('puts a detail without a field and a validation error without details on the form', () => {
    expect(fieldErrors(new ApiError(422, 'validation_error', '请求参数不合法', [{ field: '', message: '请求体不对' }])))
      .toEqual({ [FORM_ERROR]: '请求体不对' })
    expect(fieldErrors(new ApiError(422, 'validation_error', '请求参数不合法'))).toEqual({ [FORM_ERROR]: '请求参数不合法' })
  })

  it('puts username_taken on the username and invalid_credentials on the form', () => {
    expect(fieldErrors(new ApiError(409, 'username_taken', '该用户名已被注册，请换一个')))
      .toEqual({ username: '该用户名已被注册，请换一个' })
    expect(fieldErrors(new ApiError(401, 'invalid_credentials', '用户名或密码错误')))
      .toEqual({ [FORM_ERROR]: '用户名或密码错误' })
  })

  it('puts any other error on the form with the backend message', () => {
    expect(fieldErrors(new ApiError(0, 'network_error', '网络连接失败，请检查网络后重试')))
      .toEqual({ [FORM_ERROR]: '网络连接失败，请检查网络后重试' })
  })

  it('wraps an unknown error and lists the errors no field shows', () => {
    expect(errorsOf(null)).toEqual({})
    expect(Object.keys(errorsOf(new Error('boom')))).toEqual([FORM_ERROR])
    expect(otherErrors({ height_cm: '太高', goal: '不对', [FORM_ERROR]: '出错了' }, ['height_cm']))
      .toEqual(['不对', '出错了'])
    expect(otherErrors({ goal: '不对', [FORM_ERROR]: '出错了' }, [], { goal: '目标' })).toEqual(['目标：不对', '出错了'])
  })
})
