import { THEME_BY_JA_NAME, THEMES, type ThemeInfo } from '../data/themes'

export interface RankedTheme {
  rank: number
  theme: ThemeInfo
}

export interface ParseResult {
  ranking: RankedTheme[]
  isComplete: boolean
  missingRanks: number[]
  warnings: string[]
}

// Longest names first so a shorter name can never shadow a longer one
// that shares a prefix (defensive; no such collisions exist among the
// 34 official theme names today).
const NAME_ALTERNATION = THEMES.map((t) => t.nameJa)
  .sort((a, b) => b.length - a.length)
  .join('|')

const RANK_NAME_RE = new RegExp(`(\\d{1,2})\\s*[.\\uff0e]\\s*(${NAME_ALTERNATION})`, 'g')

function toHalfWidthDigits(text: string): string {
  return text.replace(/[０-９]/g, (d) => String.fromCharCode(d.charCodeAt(0) - 0xfee0))
}

/**
 * Parses a CliftonStrengths 34 personal ranking out of free-form text —
 * either text extracted from a Gallup PDF report or pasted directly by
 * the user. Looks for repeated "<rank>. <theme name>" occurrences (the
 * format Gallup reports use throughout) and keeps the first rank found
 * for each theme.
 */
export function parseRankingFromText(rawText: string): ParseResult {
  const text = toHalfWidthDigits(rawText)

  const byRank = new Map<number, ThemeInfo>()
  const warnings: string[] = []

  for (const match of text.matchAll(RANK_NAME_RE)) {
    const rank = Number(match[1])
    const theme = THEME_BY_JA_NAME.get(match[2])
    if (!theme || rank < 1 || rank > 34) continue

    const existing = byRank.get(rank)
    if (existing && existing.id !== theme.id) {
      warnings.push(
        `${rank}位の資質が複数候補で矛盾しました(${existing.nameJa} / ${theme.nameJa})。最初に見つかったものを採用しています。`,
      )
      continue
    }
    byRank.set(rank, theme)
  }

  const usedThemeIds = new Set(Array.from(byRank.values(), (t) => t.id))
  if (usedThemeIds.size !== byRank.size) {
    warnings.push('同じ資質が複数の順位に割り当てられています。結果をご確認ください。')
  }

  const ranking: RankedTheme[] = []
  const missingRanks: number[] = []
  for (let rank = 1; rank <= 34; rank++) {
    const theme = byRank.get(rank)
    if (theme) {
      ranking.push({ rank, theme })
    } else {
      missingRanks.push(rank)
    }
  }

  return {
    ranking,
    isComplete: missingRanks.length === 0 && usedThemeIds.size === 34,
    missingRanks,
    warnings,
  }
}
