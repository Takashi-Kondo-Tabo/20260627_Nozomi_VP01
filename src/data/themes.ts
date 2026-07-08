export type Domain =
  | 'strategic-thinking'
  | 'influencing'
  | 'relationship-building'
  | 'executing'

export interface DomainInfo {
  id: Domain
  labelJa: string
  color: string
}

// Colors follow the coach's hand-drawn graphic-recording legend
// (red / orange / blue / purple), not Gallup's official palette.
export const DOMAINS: Record<Domain, DomainInfo> = {
  'strategic-thinking': { id: 'strategic-thinking', labelJa: '戦略的思考力', color: '#e0342b' },
  influencing: { id: 'influencing', labelJa: '影響力', color: '#f2994a' },
  'relationship-building': { id: 'relationship-building', labelJa: '人間関係構築力', color: '#2d6cdf' },
  executing: { id: 'executing', labelJa: '実行力', color: '#7c3aed' },
}

export interface ThemeInfo {
  /** Slug used for illustration file lookup, e.g. /illustrations-svg/strategic.svg */
  id: string
  nameJa: string
  nameEn: string
  domain: Domain
}

// Canonical CliftonStrengths 34 themes, independent of any individual's
// personal ranking. Source: Gallup CliftonStrengths 34 report,
// "CliftonStrengths 34資質の順序" section.
export const THEMES: ThemeInfo[] = [
  { id: 'strategic', nameJa: '戦略性', nameEn: 'Strategic', domain: 'strategic-thinking' },
  { id: 'maximizer', nameJa: '最上志向', nameEn: 'Maximizer', domain: 'influencing' },
  { id: 'relator', nameJa: '親密性', nameEn: 'Relator', domain: 'relationship-building' },
  { id: 'responsibility', nameJa: '責任感', nameEn: 'Responsibility', domain: 'executing' },
  { id: 'ideation', nameJa: '着想', nameEn: 'Ideation', domain: 'strategic-thinking' },
  { id: 'learner', nameJa: '学習欲', nameEn: 'Learner', domain: 'strategic-thinking' },
  { id: 'significance', nameJa: '自我', nameEn: 'Significance', domain: 'influencing' },
  { id: 'deliberative', nameJa: '慎重さ', nameEn: 'Deliberative', domain: 'executing' },
  { id: 'input', nameJa: '収集心', nameEn: 'Input', domain: 'strategic-thinking' },
  { id: 'individualization', nameJa: '個別化', nameEn: 'Individualization', domain: 'relationship-building' },
  { id: 'achiever', nameJa: '達成欲', nameEn: 'Achiever', domain: 'executing' },
  { id: 'belief', nameJa: '信念', nameEn: 'Belief', domain: 'executing' },
  { id: 'futuristic', nameJa: '未来志向', nameEn: 'Futuristic', domain: 'strategic-thinking' },
  { id: 'self-assurance', nameJa: '自己確信', nameEn: 'Self-Assurance', domain: 'influencing' },
  { id: 'arranger', nameJa: 'アレンジ', nameEn: 'Arranger', domain: 'executing' },
  { id: 'focus', nameJa: '目標志向', nameEn: 'Focus', domain: 'executing' },
  { id: 'developer', nameJa: '成長促進', nameEn: 'Developer', domain: 'relationship-building' },
  { id: 'communication', nameJa: 'コミュニケーション', nameEn: 'Communication', domain: 'influencing' },
  { id: 'analytical', nameJa: '分析思考', nameEn: 'Analytical', domain: 'strategic-thinking' },
  { id: 'activator', nameJa: '活発性', nameEn: 'Activator', domain: 'influencing' },
  { id: 'intellection', nameJa: '内省', nameEn: 'Intellection', domain: 'strategic-thinking' },
  { id: 'command', nameJa: '指令性', nameEn: 'Command', domain: 'influencing' },
  { id: 'connectedness', nameJa: '運命思考', nameEn: 'Connectedness', domain: 'relationship-building' },
  { id: 'discipline', nameJa: '規律性', nameEn: 'Discipline', domain: 'executing' },
  { id: 'consistency', nameJa: '公平性', nameEn: 'Consistency', domain: 'executing' },
  { id: 'adaptability', nameJa: '適応性', nameEn: 'Adaptability', domain: 'relationship-building' },
  { id: 'woo', nameJa: '社交性', nameEn: 'Woo', domain: 'influencing' },
  { id: 'empathy', nameJa: '共感性', nameEn: 'Empathy', domain: 'relationship-building' },
  { id: 'positivity', nameJa: 'ポジティブ', nameEn: 'Positivity', domain: 'relationship-building' },
  { id: 'includer', nameJa: '包含', nameEn: 'Includer', domain: 'relationship-building' },
  { id: 'harmony', nameJa: '調和性', nameEn: 'Harmony', domain: 'relationship-building' },
  { id: 'restorative', nameJa: '回復志向', nameEn: 'Restorative', domain: 'executing' },
  { id: 'competition', nameJa: '競争性', nameEn: 'Competition', domain: 'influencing' },
  { id: 'context', nameJa: '原点思考', nameEn: 'Context', domain: 'strategic-thinking' },
]

export const THEME_BY_JA_NAME: ReadonlyMap<string, ThemeInfo> = new Map(
  THEMES.map((t) => [t.nameJa, t]),
)

if (THEMES.length !== 34) {
  throw new Error(`THEMES must contain exactly 34 entries, got ${THEMES.length}`)
}
