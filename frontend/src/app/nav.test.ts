import { describe, expect, it } from 'vitest'
import type { Capabilities } from '../api/types'
import { healthSegments, navItems, recordSegments } from './nav'

const caps = (over: Partial<Capabilities> = {}): Capabilities => ({
  cycle: true, medical: true, nutrition: true, fitness: true, ...over,
})

const labels = (c: Capabilities) => navItems(c).map((item) => item.label)

describe('capability driven navigation', () => {
  it('shows four items for a female user', () => {
    expect(labels(caps())).toEqual(['对话', '记录', '健康', '我的'])
    expect(navItems(caps()).map((item) => [item.key, item.to])).toEqual([
      ['chat', '/chat'], ['records', '/records'], ['health', '/health'], ['me', '/me'],
    ])
  })

  it('shows health for a male user because medical is open', () => {
    expect(labels(caps({ cycle: false }))).toEqual(['对话', '记录', '健康', '我的'])
  })

  it('drops health when neither cycle nor medical is open', () => {
    expect(labels(caps({ cycle: false, medical: false }))).toEqual(['对话', '记录', '我的'])
  })

  it('keeps records while either nutrition or fitness is open', () => {
    expect(labels(caps({ nutrition: false }))).toContain('记录')
    expect(labels(caps({ fitness: false }))).toContain('记录')
    expect(labels(caps({ nutrition: false, fitness: false }))).toEqual(['对话', '健康', '我的'])
  })

  it('lists the health segments in order', () => {
    expect(healthSegments(caps())).toEqual(['cycle', 'medical'])
    expect(healthSegments(caps({ cycle: false }))).toEqual(['medical'])
    expect(healthSegments(caps({ medical: false }))).toEqual(['cycle'])
    expect(healthSegments(caps({ cycle: false, medical: false }))).toEqual([])
  })

  it('lists the record segments in order', () => {
    expect(recordSegments(caps())).toEqual(['diet', 'training'])
    expect(recordSegments(caps({ nutrition: false }))).toEqual(['training'])
    expect(recordSegments(caps({ fitness: false }))).toEqual(['diet'])
    expect(recordSegments(caps({ nutrition: false, fitness: false }))).toEqual([])
  })
})
