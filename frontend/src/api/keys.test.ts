import { describe, expect, it } from 'vitest'
import { qk } from './keys'

describe('query keys', () => {
  it('keeps the unfiltered audits apart from a client named all', () => {
    expect(qk.audits()).toEqual(['agent-grants', 'audits', null])
    expect(qk.audits('all')).toEqual(['agent-grants', 'audits', 'all'])
    expect(qk.audits()).not.toEqual(qk.audits('all'))
  })
})
