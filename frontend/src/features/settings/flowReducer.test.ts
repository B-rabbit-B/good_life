import { describe, expect, it } from 'vitest'
import { flowReducer, initialFlow, stepForError, type FlowState } from './flowReducer'

const states = (flow: FlowState) => [1, 2, 3, 4].map((n) => flow.steps[n as 1 | 2 | 3 | 4].state)

describe('step for error', () => {
  it('puts key errors on the key field of step one', () => {
    expect(stepForError('llm_invalid_key', 'fetch')).toEqual({ step: 1, field: 'api_key', action: 'resave' })
    expect(stepForError('llm_key_required_for_new_url', 'save')).toEqual({ step: 1, field: 'api_key', action: 'resave' })
  })

  it('puts address and name errors on their fields of step one', () => {
    expect(stepForError('llm_invalid_url', 'save')).toEqual({ step: 1, field: 'base_url', action: 'resave' })
    expect(stepForError('llm_provider_exists', 'save')).toEqual({ step: 1, field: 'name', action: 'resave' })
  })

  it('sends bad addresses to step two with an edit address action', () => {
    expect(stepForError('llm_bad_url', 'fetch')).toEqual({ step: 2, action: 'editUrl' })
    expect(stepForError('llm_listing_unsupported_or_bad_url', 'fetch')).toEqual({ step: 2, action: 'editUrl' })
  })

  it('keeps other fetch errors on step two with a retry', () => {
    expect(stepForError('llm_timeout', 'fetch')).toEqual({ step: 2, action: 'retry' })
    expect(stepForError('network_error', 'fetch')).toEqual({ step: 2, action: 'retry' })
  })

  it('keeps other save errors on step one', () => {
    expect(stepForError('llm_too_many_providers', 'save')).toEqual({ step: 1, action: 'resave' })
  })

  it('puts every test error on step three with a retest', () => {
    for (const code of ['llm_timeout', 'llm_invalid_key', 'llm_bad_url', 'network_error']) {
      expect(stepForError(code, 'test')).toEqual({ step: 3, action: 'retest' })
    }
  })
})

describe('flow reducer', () => {
  it('advances on each success', () => {
    expect(states(initialFlow)).toEqual(['current', 'todo', 'todo', 'todo'])
    const saved = flowReducer(initialFlow, { type: 'saved', providerId: 'p1' })
    expect(saved.providerId).toBe('p1')
    expect(states(saved)).toEqual(['ok', 'current', 'todo', 'todo'])
    const fetched = flowReducer(saved, { type: 'fetched' })
    expect(states(fetched)).toEqual(['ok', 'ok', 'current', 'todo'])
    expect(states(flowReducer(fetched, { type: 'tested' }))).toEqual(['ok', 'ok', 'ok', 'current'])
  })

  it('marks the failing step and field with the backend message', () => {
    const saved = flowReducer(initialFlow, { type: 'saved', providerId: 'p1' })
    const failed = flowReducer(saved, { type: 'failed', phase: 'fetch', code: 'llm_invalid_key', message: '密钥不对' })
    expect(failed.providerId).toBe('p1')
    expect(failed.steps[1]).toEqual({ state: 'bad', field: 'api_key', code: 'llm_invalid_key', message: '密钥不对' })
    expect(states(failed)).toEqual(['bad', 'todo', 'todo', 'todo'])

    const timeout = flowReducer(flowReducer(saved, { type: 'fetched' }), {
      type: 'failed', phase: 'test', code: 'llm_timeout', message: '超时了',
    })
    expect(states(timeout)).toEqual(['ok', 'ok', 'bad', 'todo'])
    expect(timeout.steps[3]).toEqual({ state: 'bad', code: 'llm_timeout', message: '超时了' })
  })

  it('moves a bad address back to the address field', () => {
    const saved = flowReducer(initialFlow, { type: 'saved', providerId: 'p1' })
    const failed = flowReducer(saved, { type: 'failed', phase: 'fetch', code: 'llm_bad_url', message: '地址不对' })
    expect(states(failed)).toEqual(['ok', 'bad', 'todo', 'todo'])
    const back = flowReducer(failed, { type: 'editUrl' })
    expect(states(back)).toEqual(['bad', 'todo', 'todo', 'todo'])
    expect(back.steps[1]).toEqual({ state: 'bad', field: 'base_url', code: 'llm_bad_url', message: '地址不对' })
  })

  it('clears a step on retry', () => {
    const fetched = flowReducer(flowReducer(initialFlow, { type: 'saved', providerId: 'p1' }), { type: 'fetched' })
    const failed = flowReducer(fetched, { type: 'failed', phase: 'test', code: 'llm_timeout', message: '超时了' })
    expect(flowReducer(failed, { type: 'retry', step: 3 }).steps[3]).toEqual({ state: 'current' })
  })
})
