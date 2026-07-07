import { describe, expect, it } from 'vitest'
import { THEMES } from '../../data/themes'
import { parseRankingFromText } from '../parseRanking'

// A synthetic (fictional) 34-item ranking, unrelated to any real client
// report: rank N is assigned THEMES[34 - N], i.e. the master list reversed.
const SYNTHETIC_RANKING = [...THEMES].reverse()

function buildSampleReportText(): string {
  const lines = SYNTHETIC_RANKING.map((theme, index) => `${index + 1}. ${theme.nameJa} `)
  return ['強化する', ...lines.slice(0, 10), '確認する', ...lines.slice(10), 'GALLUP | CliftonStrengths'].join(
    '\n',
  )
}

describe('parseRankingFromText', () => {
  it('parses a complete 34-item ranking from Gallup-style report text', () => {
    const result = parseRankingFromText(buildSampleReportText())

    expect(result.isComplete).toBe(true)
    expect(result.missingRanks).toEqual([])
    expect(result.warnings).toEqual([])
    expect(result.ranking).toHaveLength(34)
    expect(result.ranking[0]).toEqual({ rank: 1, theme: SYNTHETIC_RANKING[0] })
    expect(result.ranking[33]).toEqual({ rank: 34, theme: SYNTHETIC_RANKING[33] })
  })

  it('is tolerant of the same list repeating later in the document', () => {
    const text = buildSampleReportText()
    const result = parseRankingFromText(text + '\n' + text)

    expect(result.isComplete).toBe(true)
    expect(result.ranking).toHaveLength(34)
  })

  it('reports missing ranks when the input is incomplete', () => {
    const lines = SYNTHETIC_RANKING.slice(0, 20).map((theme, index) => `${index + 1}. ${theme.nameJa}`)
    const result = parseRankingFromText(lines.join('\n'))

    expect(result.isComplete).toBe(false)
    expect(result.ranking).toHaveLength(20)
    expect(result.missingRanks).toEqual(
      Array.from({ length: 14 }, (_, i) => i + 21),
    )
  })

  it('ignores unrelated numbers such as dates', () => {
    const result = parseRankingFromText('隆 近藤 | 04-20-2013\n1. 戦略性')

    expect(result.ranking).toEqual([{ rank: 1, theme: expect.objectContaining({ id: 'strategic' }) }])
  })

  it('converts full-width digits before matching', () => {
    const result = parseRankingFromText('１２. 信念')

    expect(result.ranking).toEqual([{ rank: 12, theme: expect.objectContaining({ id: 'belief' }) }])
  })

  it('returns an empty, incomplete result for unrelated text', () => {
    const result = parseRankingFromText('This PDF has nothing to do with CliftonStrengths.')

    expect(result.isComplete).toBe(false)
    expect(result.ranking).toEqual([])
    expect(result.missingRanks).toHaveLength(34)
  })
})
